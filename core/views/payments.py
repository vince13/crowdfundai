from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from django.conf import settings
from django.shortcuts import get_object_or_404
from ..models import (
    AppListing, User, ShareOwnership, ShareTransfer, 
    Investment, EscrowTransaction, Notification
)
from ..services.payments import PaymentService
import json
import hmac
import hashlib
import requests
from django.utils import timezone
from decimal import Decimal
from ..utils import convert_currency, get_exchange_rate
from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect
from ..models.investment_receipt import InvestmentCertificate
from ..services.certificate_generator import CertificateGenerator
from django.db import transaction
import logging
import traceback
from django.contrib.auth.decorators import login_required
from ..services.revenue.tracking import RevenueTrackingService
from ..services.revenue.distribution import RevenueDistributionService

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Handle Paystack webhook events."""
    logger.info("Received Paystack webhook")
    payload = request.body
    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    
    logger.info(f"Webhook headers: {dict(request.headers)}")
    
    if not signature:
        logger.error("No Paystack signature in webhook request")
        return JsonResponse({'error': 'Missing signature'}, status=400)

    # Verify Paystack signature
    computed_hmac = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()

    if computed_hmac != signature:
        logger.error(f"Invalid webhook signature. Expected {signature}, got {computed_hmac}")
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    try:
        event = json.loads(payload)
        logger.info(f"Webhook event: {json.dumps(event, indent=2)}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode webhook payload: {payload}")
        return JsonResponse({'error': 'Invalid payload'}, status=400)

    if event.get('event') == 'charge.success':
        reference = event['data']['reference']
        logger.info(f"Processing successful charge for reference: {reference}")
        
        # Check if investment already exists
        existing_investment = Investment.objects.filter(transaction_id=reference).first()
        if existing_investment:
            logger.info(f"Investment already exists for reference {reference}")
            return JsonResponse({'status': 'success', 'message': 'Investment already processed'})
            
        try:
            handle_successful_payment(reference, PaymentService.PaymentGateway.PAYSTACK)
            logger.info(f"Successfully processed payment for reference: {reference}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Failed to process payment for reference {reference}: {str(e)}")
            logger.error(traceback.format_exc())
            return JsonResponse({'error': 'Payment processing failed'}, status=500)

    return JsonResponse({'status': 'success'})

def handle_successful_payment(reference, gateway):
    """Handle successful payment from any gateway."""
    logger.info(f"Verifying payment {reference} from gateway {gateway}")
    
    # Verify payment with the gateway
    verification = PaymentService.verify_payment(reference, gateway)
    if not verification['success']:
        error_msg = f"Payment verification failed for reference {reference}: {verification.get('error')}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    metadata = verification.get('metadata', {})
    logger.info(f"Payment metadata for {reference}: {metadata}")
    
    # Handle different payment types
    payment_type = metadata.get('payment_type')
    logger.info(f"Payment type for {reference}: {payment_type}")
    
    try:
        if payment_type == 'investment':
            result = handle_investment_payment(verification, metadata, gateway, reference)
            # Record revenue for the app from investment
            if result and hasattr(result, 'app'):
                tracking_service = RevenueTrackingService()
                tracking_service.record_revenue(
                    app=result.app,
                    amount=verification['amount'],
                    source='ONE_TIME',
                    description=f"Investment payment - {percentage_amount}% ownership",
                    period_start=timezone.now(),
                    period_end=timezone.now() + timezone.timedelta(days=365)  # 1 year period
                )
            return result
            
        elif payment_type == 'share_transfer':
            result = handle_transfer_payment(verification, metadata, gateway, reference)
            # Record revenue for the app from share transfer
            if result and hasattr(result, 'app'):
                tracking_service = RevenueTrackingService()
                tracking_service.record_revenue(
                    app=result.app,
                    amount=verification['amount'],
                    source='ONE_TIME',
                    description=f"Share transfer payment",
                    period_start=timezone.now(),
                    period_end=timezone.now() + timezone.timedelta(days=365)  # 1 year period
                )
            return result
            
        elif payment_type == 'subscription':
            # Handle subscription payments
            app = get_object_or_404(AppListing, id=metadata.get('app_id'))
            tracking_service = RevenueTrackingService()
            revenue = tracking_service.record_revenue(
                app=app,
                amount=verification['amount'],
                source='SUBSCRIPTION',
                description=metadata.get('description', 'Subscription payment'),
                period_start=timezone.now(),
                period_end=timezone.now() + timezone.timedelta(days=30)  # 30 day subscription
            )
            return revenue
            
        elif payment_type == 'api_usage':
            # Handle API usage payments
            app = get_object_or_404(AppListing, id=metadata.get('app_id'))
            tracking_service = RevenueTrackingService()
            revenue = tracking_service.record_revenue(
                app=app,
                amount=verification['amount'],
                source='API_USAGE',
                description=metadata.get('description', 'API usage payment'),
                period_start=metadata.get('period_start', timezone.now()),
                period_end=metadata.get('period_end', timezone.now() + timezone.timedelta(days=30))
            )
            return revenue
            
        else:
            error_msg = f"Unknown payment type: {payment_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def handle_investment_payment(verification, metadata, gateway, reference):
    """Handle successful investment payment."""
    logger.info(f"Processing investment payment for reference {reference}")
    logger.info(f"Raw metadata: {metadata}")
    investment = None
    try:
        with transaction.atomic():
            # Extract metadata from custom fields if present
            metadata_dict = {}
            if 'custom_fields' in metadata:
                metadata_dict = {
                    field['variable_name']: field['value']
                    for field in metadata['custom_fields']
                }
                logger.info(f"Extracted metadata from custom fields: {metadata_dict}")
            else:
                metadata_dict = metadata
                logger.info(f"Using direct metadata: {metadata_dict}")

            # Validate required metadata
            required_fields = ['app_id', 'user_id', 'percentage_amount']
            missing_fields = [field for field in required_fields if not metadata_dict.get(field)]
            if missing_fields:
                error_msg = f"Missing required metadata fields: {', '.join(missing_fields)}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            try:
                # Lock the app for update to prevent race conditions
                app = AppListing.objects.select_for_update().get(id=metadata_dict['app_id'])
                investor = User.objects.get(id=metadata_dict['user_id'])
            except (AppListing.DoesNotExist, User.DoesNotExist) as e:
                logger.error(f"Invalid app_id or user_id in metadata: {str(e)}")
                raise ValueError(f"Invalid app_id or user_id: {str(e)}")

            percentage_amount = Decimal(str(metadata_dict['percentage_amount']))
            logger.info(f"Extracted percentage amount: {percentage_amount}")
            amount = verification['amount']
            currency = verification['currency']

            # Sync remaining percentage before validation
            app.sync_remaining_percentage()
            logger.info(f"Current remaining percentage: {app.remaining_percentage}%")

            # Validate percentage amount against remaining percentage
            if percentage_amount > app.remaining_percentage:
                error_msg = f"Requested percentage {percentage_amount}% exceeds remaining percentage {app.remaining_percentage}%"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if percentage_amount < app.min_investment_percentage:
                error_msg = f"Investment percentage {percentage_amount}% is below minimum {app.min_investment_percentage}%"
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info(f"Creating escrow transaction for {amount} {currency}")
            # Create escrow transaction
            transaction_obj = PaymentService.create_escrow_transaction(
                app=app,
                investor=investor,
                amount=amount,
                currency=currency,
                payment_gateway=gateway,
                gateway_reference=reference
            )

            logger.info(f"Creating investment record for {percentage_amount}%")
            # Create Investment record with percentage
            investment = Investment.objects.create(
                investor=investor,
                app=app,
                percentage_bought=percentage_amount,
                amount_paid=amount,
                transaction_id=reference,
            )

            logger.info(f"Updating share ownership for user {investor.id}")
            # Update share ownership
            ownership, created = ShareOwnership.objects.get_or_create(
                user=investor,
                app=app,
                defaults={'percentage_owned': Decimal('0')}
            )
            ownership.percentage_owned += percentage_amount
            ownership.save()

            logger.info(f"Updating app remaining percentage from {app.remaining_percentage}%")
            # Update app's remaining percentage considering all investments
            app.sync_remaining_percentage()
            if app.remaining_percentage <= Decimal('0'):
                app.status = AppListing.Status.FUNDED
                app.project_status = AppListing.Status.FUNDED
                app.save(update_fields=['remaining_percentage', 'status', 'project_status'])
            else:
                app.save(update_fields=['remaining_percentage'])

            logger.info("Completing escrow transaction")
            # Complete the escrow transaction
            PaymentService.complete_escrow_transaction(transaction_obj)

            # Create success notification (only once)
            Notification.objects.create(
                user=investor,
                type=Notification.Type.INVESTMENT,
                title="Investment Successful",
                message=f"Your investment of {percentage_amount}% in {app.name} has been processed successfully.",
                link=f"/apps/{app.id}/"
            )

            logger.info(f"Investment successfully created: {investment.id}")

        # Generate certificate outside the transaction
        try:
            logger.info("Creating investment certificate")
            certificate = InvestmentCertificate.objects.create(
                investor=investor,
                app=app,
                percentage_owned=percentage_amount,
                transaction_hash=reference,
                amount_invested=amount
            )
            
            # Generate PDF certificate
            CertificateGenerator.generate_certificate(certificate)
        except Exception as cert_error:
            logger.error(f"Error generating certificate: {str(cert_error)}")
            # Don't raise the error - the investment is still valid
            
        return investment

    except Exception as e:
        logger.error(f"Error processing investment payment: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def handle_transfer_payment(verification, metadata, gateway, reference):
    """Handle successful share transfer payment."""
    try:
        transfer = ShareTransfer.objects.get(id=metadata['transfer_id'])
        amount = verification['amount']
        currency = verification['currency']

        # Create escrow transaction
        transaction = PaymentService.create_escrow_transaction(
            app=transfer.app,
            investor=transfer.buyer,
            amount=amount,
            currency=currency,
            payment_gateway=gateway,
            gateway_reference=reference
        )

        # Complete the transfer
        transfer.complete_transfer()

        # Complete the escrow transaction
        PaymentService.complete_escrow_transaction(transaction)

    except ShareTransfer.DoesNotExist as e:
        # Log error and handle accordingly
        print(f"Error processing transfer payment: {str(e)}")

@login_required
@csrf_protect
@require_POST
def create_payment_intent(request):
    """Create a payment intent for Paystack."""
    try:
        data = json.loads(request.body)
        amount = data.get('amount', 0)
        currency = data.get('currency', 'NGN')
        
        # Validate required fields
        required_fields = ['app_id', 'percentage_amount']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return JsonResponse({
                'success': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }, status=400)
        
        metadata = {
            'payment_type': 'investment',  # Explicitly set for investments
            'app_id': str(data['app_id']),  # Ensure string format
            'user_id': str(request.user.id),  # Always use the authenticated user's ID
            'email': request.user.email,
            'percentage_amount': str(data['percentage_amount']),  # Ensure string format
            'custom_fields': [  # Add custom fields for better webhook handling
                {'variable_name': 'payment_type', 'value': 'investment'},
                {'variable_name': 'app_id', 'value': str(data['app_id'])},
                {'variable_name': 'user_id', 'value': str(request.user.id)},
                {'variable_name': 'percentage_amount', 'value': str(data['percentage_amount'])}
            ]
        }
        
        logger.info(f"Creating payment with metadata: {json.dumps(metadata, indent=2)}")
        
        result = PaymentService.create_payment(amount, currency, metadata)
        
        if not result['success']:
            logger.error(f"Payment creation failed: {result['error']}")
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=400)
        
        logger.info(f"Payment created successfully: {result['reference']}")
        return JsonResponse({
            'success': True,
            'authorization_url': result['authorization_url'],
            'access_code': result['access_code'],
            'reference': result['reference']
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'error': 'Invalid request format'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def verify_payment(request):
    """Verify a payment and update investment status"""
    # Get reference from request parameters
    reference = request.GET.get('reference')
    if not reference:
        logger.error("No payment reference provided")
        return redirect('core:portfolio')
        
    logger.info(f"Payment verification request received for reference: {reference}")
    
    try:
        # Check if investment already exists
        if Investment.objects.filter(transaction_id=reference).exists():
            logger.info(f"Investment already exists for reference {reference}")
            return redirect('core:portfolio')
        
        # Verify payment with gateway
        payment_data = PaymentService.verify_payment(reference, PaymentService.PaymentGateway.PAYSTACK)
        if not payment_data.get('success'):
            logger.error(f"Payment verification failed for reference {reference}")
            Notification.objects.create(
                user=request.user,
                type=Notification.Type.SYSTEM,
                title="Payment Failed",
                message="Payment verification failed. Please try again or contact support.",
                link="/support/"
            )
            return redirect('core:portfolio')
        
        # Create investment
        investment = handle_successful_payment(reference, PaymentService.PaymentGateway.PAYSTACK)
        return redirect('core:portfolio')
        
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        Notification.objects.create(
            user=request.user,
            type=Notification.Type.SYSTEM,
            title="Payment Error",
            message="An error occurred while verifying your payment. Please contact support.",
            link="/support/"
        )
        return redirect('core:portfolio')

@csrf_exempt
@require_POST
def payment_webhook(request):
    """Handle payment webhooks from payment gateway"""
    # Verify webhook signature
    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    if not PaymentService.verify_signature(request.body, signature):
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    
    try:
        # Parse webhook data
        event = json.loads(request.body)
        event_type = event.get('event')
        
        # Handle different event types
        if event_type == 'charge.success':
            data = event.get('data', {})
            reference = data.get('reference')
            
            # Process the successful payment
            handle_successful_payment(reference, PaymentService.PaymentGateway.PAYSTACK)
            
            return JsonResponse({'status': 'success', 'message': 'Payment processed'})
            
        elif event_type == 'transfer.success':
            data = event.get('data', {})
            reference = data.get('reference')
            
            # Handle successful transfer (e.g., revenue distribution)
            distribution_service = RevenueDistributionService()
            distribution_service.handle_successful_transfer(reference)
            
            return JsonResponse({'status': 'success', 'message': 'Transfer processed'})
            
        elif event_type == 'subscription.create':
            data = event.get('data', {})
            customer = data.get('customer', {})
            plan = data.get('plan', {})
            
            # Record subscription revenue
            app_id = plan.get('metadata', {}).get('app_id')
            if app_id:
                app = AppListing.objects.get(id=app_id)
                tracking_service = RevenueTrackingService()
                tracking_service.record_revenue(
                    app=app,
                    amount=plan.get('amount', 0),
                    source='SUBSCRIPTION',
                    description=f"New subscription - {plan.get('name')}",
                    period_start=timezone.now(),
                    period_end=timezone.now() + timezone.timedelta(days=30)
                )
            
            return JsonResponse({'status': 'success', 'message': 'Subscription processed'})
            
        else:
            # Log unknown event types
            logger.info(f"Received unhandled webhook event: {event_type}")
            return JsonResponse({'status': 'success', 'message': 'Event acknowledged'})
            
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500) 