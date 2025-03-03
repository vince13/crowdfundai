from django import template

register = template.Library()

@register.simple_tag
def is_feature_enabled(feature_name):
    """Check if a feature is enabled"""
    DISABLED_FEATURES = ['ads']  # Add more features here as needed
    return feature_name not in DISABLED_FEATURES 