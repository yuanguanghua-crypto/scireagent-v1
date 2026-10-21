import os
from .base import *

DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True

# SQLite fallback for local development / CI without PostgreSQL
if os.getenv('DB_ENGINE', 'postgres') == 'sqlite':
    # ★ 2026-10-21：允许用环境变量覆盖 sqlite 文件路径。
    #   用途：① 起第二套后端（空库）验证「CI 最小种子能否让 E2E 子集跑绿」而不碰开发库；
    #         ② CI 里可显式指定库路径。**仅 development settings 生效**，生产用 base.py，不受影响。
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('SCIREAGENT_DB_NAME') or (BASE_DIR / 'db.sqlite3'),
            'TEST': {
                'NAME': os.getenv('SCIREAGENT_TEST_DB_NAME') or str(BASE_DIR / 'test_db.sqlite3'),
            },
        }
    }
    # Remove postgres-specific apps that require psycopg2
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.postgres']

# Disable throttling in development/testing to avoid rate limit interference
DISABLE_THROTTLE = True
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}
