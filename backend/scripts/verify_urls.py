"""Verify all API URL endpoints are correctly registered.

Usage:
    DB_ENGINE=sqlite python scripts/verify_urls.py
"""
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['DB_ENGINE'] = 'sqlite'

import django
django.setup()

from django.urls import get_resolver


def get_all_urls(resolver=None, prefix=''):
    """Recursively collect all URL patterns."""
    if resolver is None:
        resolver = get_resolver()
    urls = []
    for pattern in resolver.url_patterns:
        if hasattr(pattern, 'url_patterns'):
            # Include path — recurse
            urls.extend(get_all_urls(pattern, prefix + str(pattern.pattern)))
        else:
            urls.append(prefix + str(pattern.pattern))
    return urls


def main():
    all_urls = get_all_urls()
    api_urls = sorted(set(u for u in all_urls if 'api/v1' in u))

    print(f'\n{"="*60}')
    print(f'  API v1 Endpoints ({len(api_urls)} found)')
    print(f'{"="*60}\n')

    for url in api_urls:
        print(f'  /api/v1/{url}')

    print(f'\n{"="*60}')
    print(f'  Summary')
    print(f'{"="*60}')

    # Group by app
    apps = {}
    for url in api_urls:
        parts = url.split('/')
        app_key = parts[0] if parts else 'root'
        apps.setdefault(app_key, []).append(url)

    for app, endpoints in sorted(apps.items()):
        print(f'  {app}: {len(endpoints)} endpoints')

    print(f'\n  Total: {len(api_urls)} API endpoints')
    print()


if __name__ == '__main__':
    main()
