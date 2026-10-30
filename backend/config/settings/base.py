import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECRET_KEY: Required in production, fallback only for development/testing
# ★ 2026-10-30（B 方案阶段 2）：应用↔方法读路径开关。
#   '1'（默认）= 读 ApplicationMethod 桥；'0' = 读旧的 Method.application FK。
#   出问题改环境变量即可回滚，不必重新部署代码。
APP_METHOD_READ_FROM_BRIDGE = os.getenv('APP_METHOD_READ_FROM_BRIDGE', '1') != '0'

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if os.getenv('DB_ENGINE') == 'sqlite' or 'test' in sys.argv:
        SECRET_KEY = 'dev-secret-key-for-testing-only'
    else:
        raise ValueError('SECRET_KEY environment variable is required')

DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# ── 破坏性迁移守卫（2026-10-28 立，同日实测校正）────────────────────────────
# 背景：`commerce`/`knowledge` 的 5 个模型里，`search_vector` 与 GIN/trgm 索引是
# `if _USE_POSTGRES:` 条件声明的（PG 专属）。迁移 state 里**有**这些对象（靠
# state-only 迁移补齐的），sqlite 下模型里**没有** ⇒ 在 sqlite 环境跑
# `makemigrations` 会生成「RemoveField search_vector + RemoveIndex *_search_gin/
# *_trgm」的破坏性迁移，一旦提交并部署，会连根拔掉商品/方法/协议/文献的全文检索
# 与相似度索引（生产 5 列 / 5 GIN / 4 trgm / 5 触发器全没了，且搜索只是"返回空"
# 不报错 —— 最难发现的失效方式）。
#
# ★ 2026-10-28 实测矩阵（`makemigrations --check --dry-run`，别再凭推理猜）：
#     DB_ENGINE=sqlite                          → 本守卫 RuntimeError（正确）
#     DB_ENGINE=django.db.backends.postgresql   → No changes detected（安全）
#     DB_ENGINE=django.db.backends.sqlite3      → No changes detected（makemigrations
#        安全，但这是**半 sqlite 状态**：`_USE_POSTGRES` 判的是 `!= 'sqlite'`，
#        所以模型按 PG 加载、连接按 sqlite 建立 ⇒ migrate/搜索会炸。别用这个值，
#        sqlite 请**恰好**写 `sqlite`。）
#   ⇒ 结论：会生成破坏性迁移的只有 `DB_ENGINE=sqlite` 这一种。但守卫不能因此写成
#     「等于 sqlite 才拦」的黑名单 —— 将来 `_USE_POSTGRES` 的判据一改就漏。
#     所以写成**白名单**：只有确认是 PG 才放行生成迁移。
#
# 为什么用"直接拒绝"而不是"提示一下"：这条命令的破坏性产物是**可提交的文件**，
# 提示会被忽略；而拒绝的代价只是"换个环境再跑一次"。
# 配套的第二道闸门：`scripts/check_migrations_safe.py`（静态扫迁移文件里的
# RemoveField/RemoveIndex/DeleteModel/RunSQL DROP，CI 里是 `migration-state-check`
# job 的一步）。两道闸门职责不同：本守卫管"生成时"，脚本管"提交的产物里"。
_PG_ENGINES = frozenset({
    '',  # 未设 ⇒ base.py:106 默认 django.db.backends.postgresql
    'postgres',
    'postgresql',
    'django.db.backends.postgresql',
    'django.db.backends.postgresql_psycopg2',
})
_GENERATING_MIGRATIONS = any(
    str(a).startswith('makemigrations') for a in sys.argv)
if _GENERATING_MIGRATIONS and os.getenv('DB_ENGINE', '').strip().lower() not in _PG_ENGINES:
    raise RuntimeError(
        '禁止在非 PostgreSQL 环境下生成迁移（当前 DB_ENGINE=%r）：模型中的 PG '
        '专属字段（search_vector / GinIndex）在该环境下不存在，会生成'
        '「删列 + 删 GIN/trgm 索引」的破坏性迁移，部署后会静默摧毁全文检索。\n'
        '请改为：① bash scripts/dev_db.sh start  ② backend/.env 设 '
        'DB_ENGINE=django.db.backends.postgresql，然后重跑。\n'
        '（sqlite 保底写法必须是恰好 `sqlite` 三个字母；写成 '
        'django.db.backends.sqlite3 会进入"模型按 PG 加载、连接按 sqlite"的半瘫状态。）'
        % (os.getenv('DB_ENGINE'),)
    )
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
    'apps.documents',
    'apps.inventory',
    'apps.notifications',
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
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'scireagent'),
        'USER': os.getenv('DB_USER', 'scireagent'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# SQLite dev/test: raise busy timeout so concurrent writers serialize instead
# of raising "database table is locked" (select_for_update is a no-op on sqlite).
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 30

# ── Cache：数据源结果缓存（cache-aside）──────────────────────────────────────
# 有 REDIS_URL 走 Redis（跨进程、生产推荐）；无则 fallback LocMem（开发/测试）
# 用途：PubChem/Bioz 等外部 API 查询结果缓存，见 docs/DATASOURCE_RELIABILITY.md
REDIS_URL = os.getenv('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'scireagent-default',
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
# ★ 2026-10-13：**改为可从环境变量配置**（默认 'UTC'，与改动前行为一致 ⇒ 向后兼容）。
#   背景：客户在美国时，发票日期与 Net30 到期日按 UTC 计算，跨零点前后可能**相差一天**。
#   如需按美东时区显示，在 `.env` 设 TIME_ZONE=America/New_York 即可，无需改代码。
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

# ★ 业务时区：所有"按日历日"判断的业务语义（逾期、账龄、对账日、NET 天数等）必须用它，
#   **不能**用 settings.TIME_ZONE，也不能用 timezone.localdate()。
#   原因：生产 TIME_ZONE='UTC'，此时 localdate() 退化成 UTC 日期；而 due_date 存的是
#   业务日历日（东八区），东八区 00:00-08:00 这段时间内两者正好差一天，会误判逾期。
#   与 TIME_ZONE 解耦：改 TIME_ZONE 只影响展示/日志格式化，不影响业务逾期判定。
BUSINESS_TIME_ZONE = os.getenv('BUSINESS_TIME_ZONE', 'Asia/Shanghai')

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Auth redirects
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/login/'

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
        'apps.accounts.authentication.XAuthTokenAuthentication',
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
    # Global rate limiting (anonymous users: 100/hr, authenticated: no global limit)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
    },
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
            # ── Dashboard (researcher home) ──
            {
                "title": "Dashboard",
                "icon": "dashboard",
                "items": [
                    {"title": "Dashboard", "link": "/admin/dashboard/", "icon": "home"},
                ],
            },
            # ── Researcher-visible (all staff users) ──
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
                    {"title": "Compatibility Rules", "link": "/admin/knowledge/compatibility/", "icon": "rule"},
                    {"title": "Knowledge Import", "link": "/admin/knowledge-import/", "icon": "upload_file"},
                ],
            },
            # ── Admin-only (superuser required) ──
            {
                "title": "Operations",
                "icon": "shopping_cart",
                "permission": lambda request: request.user.is_superuser,
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
                "permission": lambda request: request.user.is_superuser,
                "items": [
                    {"title": "Users", "link": "/admin/accounts/user/", "icon": "person"},
                    {"title": "Organizations", "link": "/admin/accounts/organization/", "icon": "business"},
                ],
            },
            {
                "title": "System",
                "icon": "settings",
                "permission": lambda request: request.user.is_superuser,
                "items": [
                    {"title": "Tokens", "link": "/admin/authtoken/tokenproxy/", "icon": "key"},
                    {"title": "Groups", "link": "/admin/auth/group/", "icon": "group_work"},
                    {"title": "PDF Files", "link": "/admin/assets/pdffile/", "icon": "picture_as_pdf"},
                    {"title": "PDF Uploads", "link": "/api/v1/pdf-files/", "icon": "upload_file"},
                    {"title": "Basket", "link": "/admin/transactions/basket/", "icon": "shopping_basket"},
                    {"title": "Wishlist", "link": "/admin/transactions/wishlist/", "icon": "favorite"},
                ],
            },
        ],
    },
}

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[{asctime}] {levelname} {name}:{lineno} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ── Email / Outbox (django-anymail) ──
# Secrets (ANYMAIL_API_KEY etc.) are supplied via .env; never committed.
MAILGUN_API_KEY = os.getenv('ANYMAIL_MAILGUN_API_KEY', '')
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@scireagent.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Email backend selection (no outbound SMTP ports required):
#   优先级：Resend → Mailgun → console 降级。
#   - Resend / Mailgun 都走 HTTP API，云主机常封 25/465/587，API 路径完全绕开。
#   - 都不可用时退 console：邮件只打日志，此时 `email_delivery_is_unavailable()`
#     会返回 True，注册流程自动放行、投递任务自动空转（不会伪造 SENT）。
if RESEND_API_KEY:
    ANYMAIL = {'RESEND_API_KEY': RESEND_API_KEY}
    EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'
elif MAILGUN_API_KEY:
    ANYMAIL = {'MAILGUN_API_KEY': MAILGUN_API_KEY}
    EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'
else:
    ANYMAIL = {}
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Email verification link lifetime (hours) and the frontend base URL used to
# build the verification link embedded in the email.
try:
    EMAIL_VERIFICATION_EXPIRE_HOURS = int(os.getenv('EMAIL_VERIFICATION_EXPIRE_HOURS', '24'))
except (TypeError, ValueError):
    EMAIL_VERIFICATION_EXPIRE_HOURS = 24
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'https://scireagent.com')

# 密码重置链接有效期（小时）。比邮箱验证短得多：重置链接一旦被转发/滞留，
# 窗口越长风险越大；1 小时足够正常用户操作。
try:
    PASSWORD_RESET_EXPIRE_HOURS = int(os.getenv('PASSWORD_RESET_EXPIRE_HOURS', '1'))
except (TypeError, ValueError):
    PASSWORD_RESET_EXPIRE_HOURS = 1

# 运营侧收件人：新询价 / 内部提醒发到这里（逗号分隔，留空则不发内部通知）。
# 与业务数据解耦，避免把某个人的邮箱硬编码进代码。
# 文档发布（COA/SDS）是否通知买过该 SKU/产品的客户。
# 默认关闭：一个 SKU 可能有几十个历史客户，每次修订都群发会变成骚扰、伤发信声誉。
# 运营确认要发时再开：.env 里设 DOC_NOTIFY_CUSTOMERS=true
DOC_NOTIFY_CUSTOMERS = os.getenv('DOC_NOTIFY_CUSTOMERS', 'false').strip().lower() in (
    '1', 'true', 'yes', 'on'
)
try:
    DOC_NOTIFY_WINDOW_DAYS = int(os.getenv('DOC_NOTIFY_WINDOW_DAYS', '365'))
except (TypeError, ValueError):
    DOC_NOTIFY_WINDOW_DAYS = 365

RFQ_NOTIFICATION_EMAILS = [
    e.strip() for e in os.getenv('RFQ_NOTIFICATION_EMAILS', '').split(',') if e.strip()
]

# ── 数据源健壮性：全局 socket 超时兜底 ──────────────────────────────────────
# pubchempy 内部 urlopen 未传 timeout，慢响应时 enrich 接口会挂死占满 worker。
# 此处设全局默认超时兜底，防止任何遗漏的裸 urlopen 调用无限挂起。
# 外部 HTTP API 均应在 30s 内返回；自建客户端层仍应显式传更短 timeout。
# 详见 docs/DATASOURCE_RELIABILITY.md §4.1
import socket
socket.setdefaulttimeout(30)
