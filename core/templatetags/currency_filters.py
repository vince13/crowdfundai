from django import template
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def currency(value, currency_code=None):
    if value is None:
        return 'N/A'
    
    try:
        value = float(value)
    except (ValueError, TypeError):
        return value
    
    if currency_code == 'NGN':
        return f'₦{floatformat(value, 2)}'
    elif currency_code == 'USD':
        return f'${floatformat(value, 2)}'
    elif currency_code == 'EUR':
        return f'€{floatformat(value, 2)}'
    else:
        return f'{floatformat(value, 2)}' 