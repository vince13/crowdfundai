from django import template
import json

register = template.Library()

@register.filter
def json_pretty(value):
    """Format JSON with indentation"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    return json.dumps(value, indent=2)

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary"""
    return dictionary.get(key, []) 