import os

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
# ★ 2026-10-13：**改为可从环境变量配置**（逗号分隔）。原为**写死的示例域名** —— 部署方一旦使用
#   自己的域名（无论 HTTP 还是 HTTPS），Django 的 CSRF referer/origin 校验就会拒绝**所有表单 POST**
#   （后台登录、产品新建、下单、PO 提交等一律 403）。改为读 env `CSRF_TRUSTED_ORIGINS` 后，
#   部署方只需改 `.env` 即可，无需改代码；未设置时保持原有默认值（向后兼容）。
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'https://scireagent.com,https://www.scireagent.com',
    ).split(',')
    if origin.strip()
]
