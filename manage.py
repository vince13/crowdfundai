#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Check if we're running locally
    if 'PYTHONANYWHERE_SITE' not in os.environ:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crowdfund_ai.local_settings')
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crowdfund_ai.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
