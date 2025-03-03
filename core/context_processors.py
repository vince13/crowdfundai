from .utils import get_exchange_rate, convert_currency
from forex_python.converter import CurrencyRates
import logging
from django.conf import settings
from .models import ProjectRequest, DeveloperPaymentInfo

logger = logging.getLogger(__name__)

def currency_context(request):
    """Add currency information to the context."""
    try:
        user_currency = 'NGN'  # Default to NGN
        return {
            'user_currency': user_currency,
            'currency_symbol': '₦',
        }
    except Exception as e:
        logger.error(f"Error in currency_context: {e}")
        return {
            'user_currency': 'NGN',
            'currency_symbol': '₦',
        }

def paystack_settings(request):
    """Add Paystack settings to the template context."""
    key = settings.PAYSTACK_PUBLIC_KEY
    print(f"Debug - Paystack Public Key: {key}")  # Debug print
    return {
        'paystack_public_key': key
    }

def admin_counts(request):
    """Add admin-related counts to the template context"""
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
        
    return {
        'new_project_requests_count': ProjectRequest.objects.filter(
            status=ProjectRequest.Status.NEW
        ).count(),
        'unverified_payment_accounts_count': DeveloperPaymentInfo.objects.filter(
            verification_status__in=['pending', 'under_review']
        ).count(),
    }

def subscription_context(request):
    subscription = None
    if request.user.is_authenticated:
        try:
            subscription = getattr(request.user, 'subscription', None)
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            subscription = None
    
    return {
        'user_subscription': subscription,
        'has_subscription': bool(subscription)
    } 