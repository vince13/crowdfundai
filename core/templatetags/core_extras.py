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
def get_attr(obj, attr):
    """Get attribute from object by string name"""
    return getattr(obj, attr, False) 

@register.filter
def get_range(value):
    """
    Filter - returns a list containing range made from given value
    Usage (in template): {% for i in total_pages|get_range %}
    """
    return range(1, int(value) + 1) 