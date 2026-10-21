#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置一致性闸门 —— 把「只有生产踩坑才会发现的配置差异」变成可跑的检查

## 为什么需要它（这是本项目最贵的教训）
回看所有生产级事故，一半以上的根因**不在功能代码里**，而在配置差异：
  · `ALLOWED_HOSTS` 不含测试 Host ⇒ 全部端点返回 **400**（性能首测"8ms 极快"的真相）
  · `DEBUG` 默认 `True` ⇒ 误部署时匿名请求可拿到 ~71KB traceback 页
  · `wsgi.py` 默认指向 `development` ⇒ 裸跑 `gunicorn` 就是 dev 配置上生产
  · 单文件 bind mount 不跟随 inode ⇒ 宿主机改了、容器内没变
  · sqlite 下 `select_for_update` 是 no-op ⇒ 并发测试假红
这些坑，旧测试框架（7 维 × 7 层）**一个都覆盖不到**。

## 设计取舍
1. **静态检查（读文件文本），不导入 Django**
   - 快（毫秒级）、无副作用、可在 CI 任意阶段跑
   - 更重要的是：导入 Django 会受**当前环境变量**影响，测出来的不是"文件里怎么写的"，
     而是"此刻环境解析成什么" —— 而这里要查的恰恰是"**文件里有没有显式写对**"。
2. **区分 FAIL 与 WARN**
   - FAIL：真隐患，没有任何兜底
   - WARN：有已知兜底（例如 base 的 DEBUG 默认 True，但 production 硬写 False）
     本项目允许"已知不测/已知有风险"存在，但必须被记录 —— 见 FAILURE_MODES.md
3. **不修改任何文件**，只报告

## 用法
```bash
python scripts/config_parity.py            # 检查（CI / 发版前）
python scripts/config_parity.py --verbose  # 额外打印通过项
```
退出码：0 = 无 FAIL；1 = 有 FAIL
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SETTINGS = os.path.join(REPO, 'backend', 'config', 'settings')
BASE = os.path.join(SETTINGS, 'base.py')
DEV = os.path.join(SETTINGS, 'development.py')
PROD = os.path.join(SETTINGS, 'production.py')
WSGI = os.path.join(REPO, 'backend', 'config', 'wsgi.py')
ASGI = os.path.join(REPO, 'backend', 'config', 'asgi.py')
DOCKERFILE = os.path.join(REPO, 'backend', 'Dockerfile')
REQUIREMENTS = os.path.join(REPO, 'backend', 'requirements.txt')
NGINX = os.path.join(REPO, 'deploy', 'nginx.conf')
DOCKERIGNORE_CANDIDATES = [
    os.path.join(REPO, 'backend', '.dockerignore'),
    os.path.join(REPO, '.dockerignore'),
]

OK, WARN, FAIL = 'OK', 'WARN', 'FAIL'


def _read(path: str) -> str:
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            return f.read()
    except OSError:
        return ''


def _find_dockerignore() -> str:
    for p in DOCKERIGNORE_CANDIDATES:
        if os.path.exists(p):
            return p
    return ''


# ── 每项检查：返回 (状态, 说明) ─────────────────────────────────────────
def check_no_default_permission_classes():
    """base 不得设置一个"放行一切"的默认权限（本项目曾因此让 SKU 匿名可写）。"""
    text = _read(BASE)
    m = re.search(r'DEFAULT_PERMISSION_CLASSES\s*:\s*\[(.*?)\]', text, re.S)
    if not m:
        return OK, '未设置 DEFAULT_PERMISSION_CLASSES（每个视图必须显式声明，有守卫测试兜住）'
    body = m.group(1)
    if 'AllowAny' in body:
        return FAIL, 'DEFAULT_PERMISSION_CLASSES 含 AllowAny ⇒ 忘写权限的端点会匿名放行'
    return OK, f'已设置：{body.strip()[:60]}'


def check_base_debug_default():
    """base 里 DEBUG 的**默认值**不能是 True（环境变量漏配时就是它兜底）。"""
    text = _read(BASE)
    m = re.search(r"DEBUG\s*=\s*os\.getenv\(\s*['\"]DEBUG['\"]\s*,\s*['\"]([^'\"]*)['\"]", text)
    if not m:
        if re.search(r'^DEBUG\s*=\s*False', text, re.M):
            return OK, 'base 硬写 False'
        return WARN, 'DEBUG 的取值方式未能识别，请人工确认默认值不为 True'
    default = m.group(1).strip().lower()
    if default == 'true':
        return WARN, ("base 默认 DEBUG=True（环境变量漏配即开调试页，泄露 traceback/settings）。"
                      "**有兜底**：production.py 硬写 False；但裸跑 wsgi 时会中招")
    return OK, f'base 默认 DEBUG={default}'


def check_prod_debug_hardcoded():
    """production 必须**硬写** DEBUG=False，不能依赖环境变量。"""
    text = _read(PROD)
    if re.search(r'^DEBUG\s*=\s*False\s*$', text, re.M):
        return OK, 'production 硬写 DEBUG=False'
    if re.search(r'^DEBUG\s*=', text, re.M):
        return FAIL, 'production 的 DEBUG 不是硬写 False（可能被环境变量打开）'
    return FAIL, 'production 未显式设置 DEBUG ⇒ 继承 base 的默认值'


def check_allowed_hosts():
    """`ALLOWED_HOSTS` 必须从环境读取，且默认值不得是通配符。

    ★ 本项第一版要求"production 必须自己定义"，跑出来 FAIL —— **是检查项错了，不是配置错了**：
    本项目在 `base.py:19` 定义（`os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')`），
    production 直接继承。这是**合理的**（两处重复定义才会漂移）。
    真正该拦的是两件事：
      ① 谁都没定义 ⇒ 生产必然 400
      ② 默认值含 `*` ⇒ 任意 Host 都接受，Host 头攻击面全开
    """
    found = []
    for path, name in ((BASE, 'base'), (PROD, 'production')):
        text = _read(path)
        m = re.search(
            r"ALLOWED_HOSTS\s*=\s*os\.getenv\(\s*['\"]ALLOWED_HOSTS['\"]\s*,\s*['\"]([^'\"]*)['\"]",
            text)
        if m:
            found.append((name, m.group(1)))
        elif re.search(r'ALLOWED_HOSTS\s*=\s*\[', text):
            found.append((name, '<字面量列表>'))

    if not found:
        return FAIL, 'base 与 production 均未定义 ALLOWED_HOSTS ⇒ 生产必然 400（本项目踩过）'

    name, default = found[0]
    if '*' in default:
        return FAIL, f'{name}.ALLOWED_HOSTS 的默认值含通配符 *（任意 Host 都接受，不能用于生产）'
    return OK, (f'{name}.ALLOWED_HOSTS 从环境读取，默认 {default!r}（保守）'
                f'⇒ 生产须由 .env 提供，否则会退化成 localhost 而全部 400')


def check_env_example():
    """部署示例文件必须提醒 ALLOWED_HOSTS 与 SECRET_KEY，否则漏配 = 400 / 启动直接失败。"""
    for p in (os.path.join(REPO, 'deploy', '.env.example'),
              os.path.join(REPO, 'backend', '.env.example')):
        text = _read(p)
        if not text:
            continue
        missing = [k for k in ('ALLOWED_HOSTS', 'SECRET_KEY') if k not in text]
        if missing:
            return FAIL, f'{os.path.relpath(p, REPO)} 未提及：{", ".join(missing)}'
        return OK, f'{os.path.relpath(p, REPO)} 有 ALLOWED_HOSTS / SECRET_KEY 指引'
    return WARN, '未找到 .env.example（部署漏配风险需人工确认）'


def check_prod_security_headers():
    """生产必须显式开这几个（base 未设时依赖 Django 默认，不够明确）。"""
    text = _read(PROD)
    missing = []
    for key in ('SECURE_CONTENT_TYPE_NOSNIFF', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE'):
        if not re.search(rf'{key}\s*=\s*True', text):
            missing.append(key)
    if missing:
        return FAIL, f'production 未显式开启：{", ".join(missing)}'
    return OK, 'nosniff / secure cookie 均已显式开启'


def check_prod_cors_not_open():
    text = _read(PROD)
    if re.search(r'CORS_ALLOW_ALL_ORIGINS\s*=\s*True', text):
        return FAIL, 'production 打开了 CORS_ALLOW_ALL_ORIGINS'
    return OK, 'production 未放开 CORS'


def check_wsgi_defaults_to_production():
    """wsgi/asgi 的默认 settings 若是 development，裸跑就是 dev 配置上生产。"""
    bad = []
    for path, name in ((WSGI, 'wsgi.py'), (ASGI, 'asgi.py')):
        text = _read(path)
        if 'config.settings.development' in text:
            bad.append(name)
    if bad:
        return WARN, (f'{", ".join(bad)} 默认指向 development。'
                      '**有兜底**：Dockerfile 里显式设 DJANGO_SETTINGS_MODULE=production；'
                      '但裸跑 gunicorn 会中招')
    return OK, 'wsgi/asgi 未默认指向 development'


def check_dockerfile_settings():
    text = _read(DOCKERFILE)
    if not text:
        return WARN, '未找到 backend/Dockerfile'
    if 'config.settings.production' in text:
        return OK, 'Dockerfile 显式指定 production settings'
    return FAIL, 'Dockerfile 未指定 production settings ⇒ 容器内可能用 dev 配置'


def check_dockerignore_env():
    """.env 若进镜像 = 密钥外泄（SECRET_KEY / DB_PASSWORD / LLM API KEY）。"""
    path = _find_dockerignore()
    if not path:
        return FAIL, '未找到 .dockerignore ⇒ Dockerfile 的 COPY . . 会把 .env 打进镜像'
    text = _read(path)
    if re.search(r'^\s*\.env\s*$', text, re.M) or '*.env' in text or '.env' in text.split('\n'):
        return OK, f'{os.path.relpath(path, REPO)} 已排除 .env'
    return FAIL, f'{os.path.relpath(path, REPO)} 未排除 .env ⇒ 密钥可能进镜像'


def check_nginx_nosniff():
    text = _read(NGINX)
    if not text:
        return WARN, '未找到 deploy/nginx.conf'
    if 'X-Content-Type-Options' not in text:
        return FAIL, 'nginx 未设置 X-Content-Type-Options ⇒ /media/ 直出文件可被当 HTML 执行'
    return OK, 'nginx 已设置 X-Content-Type-Options'


def check_timezone_consistent():
    """base 定义时区，dev/prod 不应各自覆盖成不同值。"""
    base_tz = re.search(r"TIME_ZONE\s*=\s*['\"]([^'\"]+)['\"]", _read(BASE))
    if not base_tz:
        return WARN, 'base 未找到 TIME_ZONE'
    tz = base_tz.group(1)
    overrides = []
    for path, name in ((DEV, 'development'), (PROD, 'production')):
        m = re.search(r"TIME_ZONE\s*=\s*['\"]([^'\"]+)['\"]", _read(path))
        if m and m.group(1) != tz:
            overrides.append(f'{name}={m.group(1)}')
    if overrides:
        return FAIL, f'时区不一致：base={tz}，{", ".join(overrides)}'
    return OK, f'时区一致：{tz}'


def check_requirements_present():
    if not os.path.exists(REQUIREMENTS):
        return FAIL, '未找到 backend/requirements.txt'
    text = _read(DOCKERFILE)
    if 'requirements.txt' not in text:
        return WARN, 'Dockerfile 未引用 requirements.txt（依赖安装方式需人工确认）'
    return OK, 'Dockerfile 通过 requirements.txt 安装依赖'


CHECKS = [
    ('base.DEFAULT_PERMISSION_CLASSES', check_no_default_permission_classes),
    ('base.DEBUG 默认值', check_base_debug_default),
    ('production.DEBUG 硬写', check_prod_debug_hardcoded),
    ('ALLOWED_HOSTS 定义与环境读取', check_allowed_hosts),
    ('.env.example 指引', check_env_example),
    ('production 安全响应头', check_prod_security_headers),
    ('production CORS', check_prod_cors_not_open),
    ('wsgi/asgi 默认 settings', check_wsgi_defaults_to_production),
    ('Dockerfile settings', check_dockerfile_settings),
    ('.dockerignore 排除 .env', check_dockerignore_env),
    ('nginx X-Content-Type-Options', check_nginx_nosniff),
    ('时区一致性', check_timezone_consistent),
    ('依赖清单', check_requirements_present),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true', help='额外打印通过项')
    args = ap.parse_args()

    print('=' * 84)
    print('配置一致性闸门（静态检查；对应 FAILURE_MODES.md 第 6 类）')
    print('=' * 84)

    results = []
    for name, fn in CHECKS:
        try:
            status, detail = fn()
        except Exception as exc:                       # noqa: BLE001
            status, detail = FAIL, f'检查自身报错：{exc!r}'
        results.append((name, status, detail))

    icon = {OK: '✅', WARN: '⚠️ ', FAIL: '❌'}
    for name, status, detail in results:
        if status == OK and not args.verbose:
            continue
        print(f'{icon[status]} [{status:<4}] {name}')
        print(f'           {detail}')

    n_ok = sum(1 for _, s, _ in results if s == OK)
    n_warn = sum(1 for _, s, _ in results if s == WARN)
    n_fail = sum(1 for _, s, _ in results if s == FAIL)

    print('-' * 84)
    print(f'通过 {n_ok}｜警告 {n_warn}｜失败 {n_fail}（共 {len(results)} 项）')
    if n_warn and not args.verbose:
        print('（警告项有已知兜底，明细见 FAILURE_MODES.md；加 --verbose 看通过项）')

    if n_fail:
        print('\n❌ 存在配置隐患，见上。')
        return 1
    print('\n✅ 无 FAIL。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
