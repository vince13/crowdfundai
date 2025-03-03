from django import template
import json

register = template.Library()

@register.filter(is_safe=True)
def to_json(value):
    """Convert a value to JSON string"""
    return json.dumps(value)

@register.filter
def pluck(value, key):
    """Extract a list of values for a given key from a list of dictionaries"""
    return [item[key] for item in value] if value else [] 