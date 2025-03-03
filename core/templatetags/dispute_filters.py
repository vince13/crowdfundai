from django import template

register = template.Library()

@register.filter
def filter_status(disputes, statuses):
    """Filter disputes by a comma-separated list of statuses."""
    if not disputes:
        return []
    status_list = [s.strip() for s in statuses.split(',')]
    return [d for d in disputes if d.status in status_list] 