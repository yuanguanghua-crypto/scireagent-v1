import os
from .base import *

DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

# SQLite fallback for local development / CI without PostgreSQL
if os.getenv('DB_ENGINE', 'postgres') == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    # Remove postgres-specific apps that require psycopg2
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.postgres']

# Disable throttling in development/testing to avoid rate limit interference
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}
