from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def split(value, delimiter=','):
    """
    Returns the string split by delimiter.
    Example: {{ value|split:"," }}
    """
    return [x.strip() for x in value.split(delimiter)]

@register.filter
def strip(value):
    """
    Strips whitespace from the beginning and end of a string.
    Example: {{ value|strip }}
    """
    return str(value).strip() 