import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local apps
    'apps.accounts',
    'apps.knowledge',
    'apps.commerce',
    'apps.bridges',
    'apps.transactions',
    'apps.quotes',
    'apps.assets',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'scireagent'),
        'USER': os.getenv('DB_USER', 'scireagent'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'scireagent_dev_2026'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')

# DRF
REST_FRAMEWORK = {
    'FORMAT_SUFFIX_KWARG': None,  # Disable format suffix to avoid converter registration conflict
    'DEFAULT_RENDERER_CLASSES': [
        'core.renderers.EnvelopeRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# drf-spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'SciReagent API',
    'DESCRIPTION': 'LabPro Global - AI-Native Scientific Reagent Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Django Unfold admin theme
UNFOLD = {
    "SITE_TITLE": "SciReagent Admin",
    "SITE_HEADER": "SciReagent",
    "SITE_SYMBOL": "science",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "240 253 244",
            "100": "220 252 231",
            "200": "187 247 208",
            "300": "134 239 172",
            "400": "74 222 128",
            "500": "34 197 94",
            "600": "22 163 74",
            "700": "21 128 61",
            "800": "22 101 52",
            "900": "20 83 45",
            "950": "5 46 22",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Products",
                "icon": "inventory_2",
                "items": [
                    {"title": "Products", "link": "/admin/commerce/product/", "icon": "science"},
                    {"title": "Product Classes", "link": "/admin/commerce/productclass/", "icon": "category"},
                    {"title": "Product Documents", "link": "/admin/commerce/productdocument/", "icon": "description"},
                ],
            },
            {
                "title": "Knowledge",
                "icon": "school",
                "items": [
                    {"title": "Research Goals", "link": "/admin/knowledge/researchgoal/", "icon": "flag"},
                    {"title": "Applications", "link": "/admin/knowledge/application/", "icon": "biotech"},
                    {"title": "Methods", "link": "/admin/knowledge/method/", "icon": "psychology"},
                    {"title": "Protocols", "link": "/admin/knowledge/protocol/", "icon": "lab_research"},
                    {"title": "References", "link": "/admin/knowledge/reference/", "icon": "menu_book"},
                ],
            },
            {
                "title": "Relationships",
                "icon": "hub",
                "items": [
                    {"title": "Product ↔ Method", "link": "/admin/bridges/productmethod/", "icon": "link"},
                    {"title": "Product ↔ Product", "link": "/admin/bridges/productproduct/", "icon": "sync_alt"},
                    {"title": "Product Compatibility", "link": "/admin/bridges/productcompatibility/", "icon": "verified"},
                    {"title": "Compatibility Rules", "link": "/admin/knowledge/compatibility/", "icon": "rule"},
                ],
            },
            {
                "title": "Commerce",
                "icon": "shopping_cart",
                "items": [
                    {"title": "Orders", "link": "/admin/transactions/order/", "icon": "receipt_long"},
                    {"title": "Quotes", "link": "/admin/transactions/quote/", "icon": "request_quote"},
                    {"title": "Quote Requests", "link": "/admin/quotes/quoterequest/", "icon": "help_outline"},
                    {"title": "Invoices", "link": "/admin/transactions/invoice/", "icon": "payments"},
                    {"title": "Payments", "link": "/admin/transactions/paymentrecord/", "icon": "account_balance"},
                    {"title": "Shipping", "link": "/admin/transactions/shippingrecord/", "icon": "local_shipping"},
                ],
            },
            {
                "title": "Accounts",
                "icon": "group",
                "items": [
                    {"title": "Users", "link": "/admin/accounts/user/", "icon": "person"},
                    {"title": "Organizations", "link": "/admin/accounts/organization/", "icon": "business"},
                ],
            },
            {
                "title": "System",
                "icon": "settings",
                "items": [
                    {"title": "Tokens", "link": "/admin/authtoken/tokenproxy/", "icon": "key"},
                    {"title": "Groups", "link": "/admin/auth/group/", "icon": "group_work"},
                    {"title": "PDF Files", "link": "/admin/assets/pdffile/", "icon": "picture_as_pdf"},
                    {"title": "SKU Management", "link": "/admin/commerce/sku/", "icon": "sell"},
                    {"title": "Basket", "link": "/admin/transactions/basket/", "icon": "shopping_basket"},
                    {"title": "Wishlist", "link": "/admin/transactions/wishlist/", "icon": "favorite"},
                ],
            },
        ],
    },
}
