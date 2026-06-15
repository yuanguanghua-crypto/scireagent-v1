"""manage.py wrapper that patches DRF converter registration."""
import os, sys

# Patch register_converter to be idempotent BEFORE Django setup
import django.urls.converters as conv
_orig = conv.register_converter
def _safe_register(converter, type_name):
    try:
        _orig(converter, type_name)
    except ValueError:
        pass
conv.register_converter = _safe_register

# Now run normal manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
