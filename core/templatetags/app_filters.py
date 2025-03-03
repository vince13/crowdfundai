from django import template
from decimal import Decimal
import decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0

@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except (ValueError, TypeError, decimal.InvalidOperation, decimal.DivisionByZero):
        return 0

@register.filter
def percentage_value(ownership, app_valuation):
    """Calculate the current value of an investment based on percentage ownership and app valuation"""
    try:
        if not app_valuation:
            return 0
        percentage = Decimal(str(ownership))
        valuation = Decimal(str(app_valuation))
        return (percentage * valuation) / Decimal('100')
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0

@register.filter
def is_list(value):
    """Check if a value is a list"""
    return isinstance(value, (list, tuple))

@register.filter
def is_dict(value):
    """Check if a value is a dictionary"""
    return isinstance(value, dict)

@register.filter
def get_type(value):
    """Get the type of a value"""
    return type(value).__name__ 