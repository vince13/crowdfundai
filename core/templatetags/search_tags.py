from django import template

register = template.Library()

@register.filter
def get_range(value):
    """
    Filter - returns a list containing range made from given value
    Usage (in template): {% for i in total_pages|get_range %}
    """
    return range(1, int(value) + 1) 