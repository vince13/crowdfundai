# This will ensure the app is always loaded when Django starts
default_app_config = 'core.apps.CoreConfig'

def ready():
    # Import signals only when the app is ready
    from . import signals 