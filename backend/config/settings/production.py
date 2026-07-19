from .base import *

DEBUG = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# 反代 HTTPS：让 Django 自身识别原始请求为 HTTPS（gunicorn 22 默认据 X-Forwarded-Proto 置 https，
# 此处声明使 Django 不依赖 gunicorn 行为，为 CSRF referer/origin 校验提供正确的安全上下文）。
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# admin 登录 CSRF referer/origin 校验所需的可信源（条目必须带 https:// 协议前缀）。
CSRF_TRUSTED_ORIGINS = ['https://scireagent.com', 'https://www.scireagent.com']
