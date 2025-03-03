import requests
from django.conf import settings
from decimal import Decimal
from django.http import JsonResponse

def error_response(message, status=400):
    """Return a JSON error response with the given message and status code."""
    return JsonResponse({
        'status': 'error',
        'message': str(message)
    }, status=status)

def get_user_currency(request):
    """Get the user's preferred currency."""
    return 'NGN'  # Default to NGN for now

def get_currency_symbol(currency_code):
    """Get the symbol for a currency code."""
    symbols = {
        'NGN': '₦',
        'USD': '$',
        'EUR': '€',
        'GBP': '£'
    }
    return symbols.get(currency_code, currency_code)

def get_currency_format(currency_code):
    """Get the format for displaying a currency amount."""
    return '{symbol}{amount:,.2f}'

def format_currency(amount, currency_code):
    """Format an amount in the specified currency."""
    if amount is None:
        return '-'
    symbol = get_currency_symbol(currency_code)
    return f"{symbol}{float(amount):,.2f}"

class PaystackAPI:
    """Utility class for interacting with Paystack API"""
    
    BASE_URL = 'https://api.paystack.co'
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        self.transaction = PaystackTransactionAPI(self)

class PaystackTransactionAPI:
    """Handles Paystack transaction-related operations"""
    
    def __init__(self, api):
        self.api = api
    
    def initialize(self, email, amount, callback_url, metadata=None):
        """Initialize a payment transaction
        
        Args:
            email (str): Customer's email
            amount (int): Amount in kobo (multiply Naira amount by 100)
            callback_url (str): URL to redirect to after payment
            metadata (dict, optional): Additional data to store with transaction
        
        Returns:
            dict: Response from Paystack API containing authorization URL
        """
        endpoint = f"{self.api.BASE_URL}/transaction/initialize"
        payload = {
            'email': email,
            'amount': amount,
            'callback_url': callback_url
        }
        if metadata:
            payload['metadata'] = metadata
            
        response = requests.post(
            endpoint,
            headers=self.api.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def verify(self, reference):
        """Verify a transaction using its reference
        
        Args:
            reference (str): Transaction reference to verify
            
        Returns:
            dict: Transaction verification details
        """
        endpoint = f"{self.api.BASE_URL}/transaction/verify/{reference}"
        response = requests.get(
            endpoint,
            headers=self.api.headers
        )
        response.raise_for_status()
        return response.json()

def get_exchange_rate(from_currency, to_currency):
    """Get exchange rate between two currencies
    
    Currently only supports USD to NGN conversion using rate from settings
    
    Args:
        from_currency (str): Source currency code (e.g. 'USD')
        to_currency (str): Target currency code (e.g. 'NGN')
        
    Returns:
        Decimal: Exchange rate from source to target currency
    """
    if from_currency == 'USD' and to_currency == 'NGN':
        return Decimal(str(settings.USD_TO_NGN_RATE))
    elif from_currency == 'NGN' and to_currency == 'USD':
        return Decimal('1') / Decimal(str(settings.USD_TO_NGN_RATE))
    raise ValueError(f"Conversion from {from_currency} to {to_currency} not supported")

def convert_currency(amount, from_currency, to_currency):
    """Convert an amount between currencies
    
    Args:
        amount (Decimal): Amount to convert
        from_currency (str): Source currency code
        to_currency (str): Target currency code
        
    Returns:
        Decimal: Converted amount in target currency
    """
    if amount is None:
        return None
        
    rate = get_exchange_rate(from_currency, to_currency)
    return Decimal(str(amount)) * rate 