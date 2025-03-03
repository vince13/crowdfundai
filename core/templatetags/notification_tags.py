from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr):
    """Get attribute from object"""
    return getattr(obj, attr, False) 