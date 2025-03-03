from django import template
from ..utils import convert_currency, get_exchange_rate
from django.utils.safestring import mark_safe
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def convert_to_ngn(value):
    """Convert amount to NGN"""
    if value is None:
        return None
    return convert_currency(value, 'USD', 'NGN')

@register.simple_tag
def get_ngn_rate():
    """Get NGN exchange rate"""
    return get_exchange_rate('USD', 'NGN')

@register.simple_tag
def dual_currency(amount, primary_currency, secondary_currency, exchange_rate):
    """Display amount in NGN with proper formatting"""
    try:
        # Convert exchange_rate to Decimal if it's a string
        rate = Decimal(str(exchange_rate))
        amount_ngn = amount * rate
        return mark_safe(f"₦{amount_ngn:,.2f}")
    except (TypeError, ValueError, InvalidOperation):
        # Fallback to just showing the amount
        return mark_safe(f"₦{amount:,.2f}") 