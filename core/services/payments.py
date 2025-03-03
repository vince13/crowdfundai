from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import logging
from ..models import EscrowTransaction, AppListing, PlatformFeeTransaction
from ..utils import convert_currency, get_exchange_rate
from enum import Enum
import traceback
from django.db import transaction
from ..services.notifications import NotificationService
import uuid

logger = logging.getLogger(__name__)

class PaymentService:
    """Service for handling Paystack payments"""
    
    class PaymentGateway(str, Enum):
        PAYSTACK = 'PAYSTACK'
       
    
    def __init__(self):
        self.base_url = settings.PAYMENT_GATEWAY_URL
        self.api_key = settings.PAYMENT_GATEWAY_API_KEY
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _make_request(self, method, endpoint, data=None):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers)
            else:
                response = self.session.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the error and raise a custom exception
            print(f"Payment gateway error: {str(e)}")
            raise Exception("Payment processing failed")

    @classmethod
    def create_payment(cls, amount, currency, metadata=None):
        """Create a Paystack payment"""
        logger.info(f"Creating payment - Amount: {amount} {currency}, Metadata: {metadata}")
        
        if not isinstance(amount, (int, float, Decimal)) or float(amount) <= 0:
            logger.error(f"Invalid amount: {amount}")
            raise ValueError("Invalid amount")
            
        # Convert amount to kobo/cents
        amount_in_subunit = int(float(amount) * 100)
            
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
            
        # Store metadata both directly and in custom fields for consistency
        custom_fields = [
            {
                'display_name': "Payment Type",
                'variable_name': "payment_type",
                'value': metadata.get('payment_type', 'investment')
            },
            {
                'display_name': "App ID",
                'variable_name': "app_id",
                'value': metadata.get('app_id', '')
            },
            {
                'display_name': "User ID",
                'variable_name': "user_id",
                'value': metadata.get('user_id', '')
            },
            {
                'display_name': "Percentage Amount",
                'variable_name': "percentage_amount",
                'value': metadata.get('percentage_amount', '')
            }
        ]
            
        # Prepare the request data with all required fields
        data = {
            'amount': amount_in_subunit,
            'currency': currency,
            'email': metadata.get('email') if metadata else None,
            'callback_url': f"{settings.SITE_URL}/payments/verify/",
            'channels': ['card', 'bank', 'ussd', 'qr', 'mobile_money', 'bank_transfer'],
            'metadata': {
                **metadata,  # Include direct metadata
                'custom_fields': custom_fields  # And custom fields
            }
        }

        if not data['email']:
            logger.error("Email is required for payment")
            return {
                'success': False,
                'error': 'Email is required for payment'
            }
        
        try:
            logger.info(f"Sending payment request to Paystack: {json.dumps(data)}")
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Payment initialization failed: {error_data}")
                return {
                    'success': False,
                    'error': error_data.get('message', 'Payment initialization failed'),
                    'details': error_data
                }
            
            result = response.json()
            if result['status']:
                logger.info(f"Payment initialized successfully: {result['data']['reference']}")
                return {
                    'success': True,
                    'authorization_url': result['data']['authorization_url'],
                    'access_code': result['data']['access_code'],
                    'reference': result['data']['reference']
                }
            logger.error(f"Payment initialization failed: {result}")
            return {
                'success': False,
                'error': result.get('message', 'Payment initialization failed')
            }
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @classmethod
    def verify_payment(cls, reference, gateway=None):
        """Verify payment from any supported payment gateway."""
        if gateway is None or gateway == cls.PaymentGateway.PAYSTACK:
            return cls._verify_paystack_payment(reference)
        raise ValueError(f"Unsupported payment gateway: {gateway}")

    @classmethod
    def _verify_paystack_payment(cls, reference):
        """Verify Paystack payment"""
        logger.info(f"Verifying Paystack payment: {reference}")
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            logger.info(f"Paystack API Response Status: {response.status_code}")
            logger.info(f"Paystack API Response: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"Payment verification failed - HTTP {response.status_code}")
                return {
                    'success': False,
                    'error': f"Payment verification failed with status {response.status_code}"
                }
            
            result = response.json()
            logger.info(f"Payment verification result: {result}")
            
            if not result.get('status'):
                logger.error(f"Payment verification failed - API error: {result.get('message')}")
                return {
                    'success': False,
                    'error': result.get('message', 'Payment verification failed')
                }
            
            data = result.get('data', {})
            if data.get('status') != 'success':
                logger.error(f"Payment verification failed - Payment status: {data.get('status')}")
                return {
                    'success': False,
                    'error': f"Payment status is {data.get('status')}"
                }
            
            # Extract metadata from both direct and custom fields
            metadata = data.get('metadata', {})
            if metadata and 'custom_fields' in metadata:
                # Convert custom fields to direct metadata
                for field in metadata['custom_fields']:
                    metadata[field['variable_name']] = field['value']
            
            logger.info(f"Payment verified successfully: {reference}")
            return {
                'success': True,
                'amount': Decimal(str(data.get('amount', 0) / 100)),  # Convert from kobo to naira
                'currency': data.get('currency', 'NGN'),
                'metadata': metadata,
                'customer': {
                    'email': data.get('customer', {}).get('email')
                }
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Payment verification request failed: {str(e)}")
            return {
                'success': False,
                'error': f"Payment verification request failed: {str(e)}"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            logger.error(f"Response text: {response.text}")
            return {
                'success': False,
                'error': "Invalid response from payment gateway"
            }
        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    def process_payment(self, amount, currency, user_id, description):
        data = {
            'amount': str(amount),
            'currency': currency,
            'user_id': str(user_id),
            'description': description
        }
        return self._make_request('POST', 'payments/process', data)
        
    def get_payment_status(self, payment_id):
        return self._make_request('GET', f'payments/{payment_id}/status')
        
    def refund_payment(self, payment_id, amount=None):
        data = {'payment_id': payment_id}
        if amount:
            data['amount'] = str(amount)
        return self._make_request('POST', 'payments/refund', data)
        
    def create_escrow(self, amount, currency, sender_id, receiver_id, description):
        data = {
            'amount': str(amount),
            'currency': currency,
            'sender_id': str(sender_id),
            'receiver_id': str(receiver_id),
            'description': description
        }
        response = self._make_request('POST', 'escrow/create', data)
        
        # Create local escrow record
        EscrowTransaction.objects.create(
            amount=amount,
            currency=currency,
            sender_id=sender_id,
            receiver_id=receiver_id,
            description=description,
            escrow_id=response['escrow_id'],
            status='pending'
        )
        return response
        
    def release_escrow(self, escrow_id):
        return self._make_request('POST', f'escrow/{escrow_id}/release')
        
    def cancel_escrow(self, escrow_id):
        return self._make_request('POST', f'escrow/{escrow_id}/cancel')

    @classmethod
    def create_escrow_transaction(cls, app, investor, amount, currency, payment_gateway, gateway_reference):
        """Create an escrow transaction record."""
        logger.info(f"Creating escrow transaction - App: {app.id}, Investor: {investor.id}, Amount: {amount} {currency}")
        
        try:
            transaction = EscrowTransaction.objects.create(
                app=app,
                investor=investor,
                amount=amount,
                currency=currency,
                transaction_type=EscrowTransaction.Type.DEPOSIT,
                payment_gateway=payment_gateway,
                gateway_reference=gateway_reference,
                status=EscrowTransaction.Status.PENDING
            )
            logger.info(f"Created escrow transaction {transaction.id} for reference {gateway_reference}")
            return transaction
        except Exception as e:
            logger.error(f"Failed to create escrow transaction: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Failed to create escrow transaction: {str(e)}")

    @classmethod
    def complete_escrow_transaction(cls, transaction):
        """Complete an escrow transaction."""
        logger.info(f"Completing escrow transaction {transaction.id}")
        
        try:
            transaction.status = EscrowTransaction.Status.COMPLETED
            transaction.completed_at = timezone.now()
            transaction.save()
            logger.info(f"Completed escrow transaction {transaction.id}")
        except Exception as e:
            logger.error(f"Failed to complete escrow transaction {transaction.id}: {str(e)}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Failed to complete escrow transaction: {str(e)}")

    @classmethod
    def handle_funding_completion(cls, app):
        """Handle the completion of funding and fee collection"""
        try:
            with transaction.atomic():
                # Check if platform fee transaction already exists
                existing_fee = PlatformFeeTransaction.objects.filter(
                    app=app,
                    status__in=['PENDING', 'COMPLETED']
                ).first()
                
                if existing_fee:
                    logger.info(f"Platform fee transaction already exists for app {app.id}")
                    platform_fee = existing_fee.amount
                    platform_fee_txn = existing_fee
                else:
                    # Calculate platform fee
                    platform_fee = app.calculate_platform_fee()
                    
                    # Create platform fee transaction record
                    fee_reference = f"PLATFEE-{app.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    platform_fee_txn = PlatformFeeTransaction.objects.create(
                        app=app,
                        amount=platform_fee,
                        transaction_reference=fee_reference,
                        status='COMPLETED',
                        completed_at=timezone.now()
                    )
                
                # Calculate developer's final amount
                developer_amount = app.get_raised_amount() - platform_fee
                
                # Release funds to developer minus platform fee
                cls.release_funds_to_developer(
                    app=app,
                    amount=developer_amount,
                    fee_transaction=platform_fee_txn
                )
                
                # Update app status
                app.status = AppListing.Status.COMPLETED
                app.save()
                
                # Log success
                logger.info(f"Successfully processed funding completion for app {app.id}")
                logger.info(f"Platform fee: {platform_fee}, Developer amount: {developer_amount}")
                
        except Exception as e:
            logger.error(f"Error processing funding completion for app {app.id}: {str(e)}")
            raise

    @classmethod
    def release_funds_to_developer(cls, app, amount, fee_transaction):
        """Release funds to developer after deducting platform fee"""
        try:
            logger.info(f"Releasing {amount} to developer for app {app.id}")
            
            # Create escrow release transaction
            release_reference = f"REL-{app.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            EscrowTransaction.objects.create(
                app=app,
                investor=app.developer,
                transaction_type=EscrowTransaction.Type.RELEASE,
                amount=amount,
                currency=app.currency,
                payment_gateway='PAYSTACK',
                gateway_reference=release_reference,
                status=EscrowTransaction.Status.COMPLETED,
                completed_at=timezone.now()
            )
            
            logger.info(f"Successfully released funds for app {app.id}")
            
        except Exception as e:
            logger.error(f"Error releasing funds to developer: {str(e)}")
            raise

    @staticmethod
    def get_bank_list():
        """Get list of banks from Paystack"""
        # Define fallback list of common Nigerian banks with current Paystack codes
        fallback_banks = [
            {'code': '001', 'name': 'Access Bank'},
            {'code': '023', 'name': 'Citibank Nigeria'},
            {'code': '050', 'name': 'Ecobank Nigeria'},
            {'code': '011', 'name': 'First Bank of Nigeria'},
            {'code': '214', 'name': 'First City Monument Bank'},
            {'code': '058', 'name': 'Guaranty Trust Bank'},
            {'code': '076', 'name': 'Polaris Bank'},
            {'code': '221', 'name': 'Stanbic IBTC Bank'},
            {'code': '232', 'name': 'Sterling Bank'},
            {'code': '032', 'name': 'Union Bank of Nigeria'},
            {'code': '033', 'name': 'United Bank For Africa'},
            {'code': '215', 'name': 'Unity Bank'},
            {'code': '035', 'name': 'Wema Bank'},
            {'code': '057', 'name': 'Zenith Bank'}
        ]
        
        try:
            url = "https://api.paystack.co/bank"
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Add timeout to prevent hanging
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data['status']:
                    # Filter for Nigerian banks only
                    banks = [
                        {'code': bank['code'], 'name': bank['name']}
                        for bank in data['data']
                        if bank['country'] == 'Nigeria'
                    ]
                    return sorted(banks, key=lambda x: x['name'])
            
            logger.warning("Failed to fetch banks from Paystack API, using fallback list")
            return fallback_banks
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching bank list: {str(e)}")
            logger.info("Using fallback bank list")
            return fallback_banks

    @staticmethod
    def resolve_account(account_number, bank_code):
        """Resolve account number with bank before creating recipient"""
        try:
            url = "https://api.paystack.co/bank/resolve"
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            
            params = {
                'account_number': account_number,
                'bank_code': bank_code
            }
            
            logger.info(f"Resolving account: {account_number} with bank code: {bank_code}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('status'):
                logger.info("Successfully resolved account")
                return response_data
            else:
                error_msg = response_data.get('message', 'Could not verify account number')
                logger.error(f"Failed to resolve account: {error_msg}")
                return {
                    'status': False,
                    'message': 'Invalid account number or bank details. Please verify and try again.'
                }
                
        except requests.exceptions.Timeout:
            logger.error("Timeout while resolving account")
            return {
                'status': False,
                'message': 'Connection timed out. Please try again.'
            }
        except requests.exceptions.ConnectionError:
            logger.error("Connection error while resolving account")
            return {
                'status': False,
                'message': 'Unable to connect to payment service. Please try again later.'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error resolving account: {str(e)}")
            return {
                'status': False,
                'message': 'Network error. Please check your connection and try again.'
            }
        except Exception as e:
            logger.error(f"Unexpected error resolving account: {str(e)}")
            return {
                'status': False,
                'message': 'An unexpected error occurred. Please try again later.'
            }

    @staticmethod
    def create_transfer_recipient(name, email, account_number, bank_code):
        """Create a transfer recipient on Paystack"""
        try:
            # First resolve the account
            resolve_result = PaymentService.resolve_account(account_number, bank_code)
            if not resolve_result.get('status'):
                return resolve_result
            
            # If account is resolved, create the recipient
            url = "https://api.paystack.co/transferrecipient"
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Use the resolved account name from the bank
            account_name = resolve_result['data']['account_name']
            
            data = {
                'type': 'nuban',
                'name': account_name,  # Use bank's account name
                'account_number': account_number,
                'bank_code': bank_code,
                'currency': 'NGN',
                'email': email
            }
            
            logger.info(f"Creating transfer recipient with resolved account: {account_name}")
            response = requests.post(url, json=data, headers=headers, timeout=10)
            response_data = response.json()
            
            if response.status_code == 201 and response_data.get('status'):
                logger.info("Successfully created transfer recipient")
                # Add resolved account name to response
                response_data['data']['account_name'] = account_name
                return response_data
            else:
                error_msg = response_data.get('message', 'Unknown error')
                logger.error(f"Failed to create Paystack recipient: {error_msg}")
                return {
                    'status': False,
                    'message': error_msg,
                    'data': response_data
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error creating transfer recipient: {str(e)}"
            logger.error(error_msg)
            return {'status': False, 'message': error_msg}
        except Exception as e:
            error_msg = f"Unexpected error creating transfer recipient: {str(e)}"
            logger.error(error_msg)
            return {'status': False, 'message': error_msg}

    @staticmethod
    def verify_transfer_recipient(recipient_code):
        """Verify a transfer recipient on Paystack"""
        try:
            url = f"https://api.paystack.co/transferrecipient/{recipient_code}"
            headers = {
                'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                'Content-Type': 'application/json'
            }
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to verify Paystack recipient: {response.text}")
                return {'status': False, 'message': 'Failed to verify recipient'}
                
        except Exception as e:
            logger.error(f"Error verifying transfer recipient: {str(e)}")
            return {'status': False, 'message': str(e)}

    @classmethod
    def create_subscription_payment(cls, user, plan, amount, currency='NGN'):
        """Create a subscription payment"""
        logger.info(f"Creating subscription payment - Plan: {plan}, Amount: {amount} {currency}")
        
        if not isinstance(amount, (int, float, Decimal)) or float(amount) <= 0:
            logger.error(f"Invalid amount: {amount}")
            raise ValueError("Invalid amount")
        
        # Generate unique reference for subscription payment
        reference = f"sub_{uuid.uuid4().hex[:16]}"
        
        # Convert amount to kobo/cents
        amount_in_subunit = int(float(amount) * 100)
        
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Prepare metadata
        metadata = {
            'payment_type': 'subscription',
            'plan': plan,
            'user_id': str(user.id),
            'custom_fields': [
                {
                    'display_name': "Payment Type",
                    'variable_name': "payment_type",
                    'value': 'subscription'
                },
                {
                    'display_name': "Plan",
                    'variable_name': "plan",
                    'value': plan
                },
                {
                    'display_name': "User ID",
                    'variable_name': "user_id",
                    'value': str(user.id)
                }
            ]
        }
        
        data = {
            'amount': amount_in_subunit,
            'currency': currency,
            'email': user.email,
            'callback_url': f"{settings.SITE_URL}/subscriptions/process-payment/",
            'reference': reference,
            'metadata': metadata
        }
        
        try:
            logger.info(f"Sending subscription payment request to Paystack: {json.dumps(data)}")
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Subscription payment initialization failed: {error_data}")
                return {
                    'success': False,
                    'error': error_data.get('message', 'Payment initialization failed'),
                    'details': error_data
                }
            
            result = response.json()
            if result['status']:
                logger.info(f"Subscription payment initialized successfully: {reference}")
                return {
                    'success': True,
                    'authorization_url': result['data']['authorization_url'],
                    'access_code': result['data']['access_code'],
                    'reference': reference
                }
            
            logger.error(f"Subscription payment initialization failed: {result}")
            return {
                'success': False,
                'error': result.get('message', 'Payment initialization failed')
            }
            
        except Exception as e:
            logger.error(f"Subscription payment creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def verify_subscription_payment(cls, reference):
        """Verify a subscription payment"""
        logger.info(f"Verifying subscription payment: {reference}")
        
        verification = cls._verify_paystack_payment(reference)
        
        if verification.get('success'):
            metadata = verification.get('metadata', {})
            if metadata.get('payment_type') != 'subscription':
                logger.error(f"Invalid payment type for subscription: {metadata.get('payment_type')}")
                return {
                    'success': False,
                    'error': 'Invalid payment type'
                }
            
            return {
                'success': True,
                'amount': verification['amount'],
                'currency': verification['currency'],
                'plan': metadata.get('plan'),
                'user_id': metadata.get('user_id')
            }
        
        return verification