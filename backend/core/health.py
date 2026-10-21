# -*- coding: utf-8 -*-
"""健康检查端点 —— 让「服务是否可用」变成机器可轮询的答案

## 为什么需要（对应 FAILURE_MODES 7.2 / 7.3 两条实质空白）
此前：
  · **DB 挂掉** ⇒ 请求直接 500 或 nginx 502。监控和人**都分不清**这是"服务整体挂了"
    还是"这一个请求恰好出错"，也没法自动摘流量。
  · **磁盘满** ⇒ 没有任何主动信号，直到某次上传/写文件失败才发现。
这两条在清单里原本是 B 类，但兜底写的是"无" —— 按定义 §4.1 已降级为**空白**。
本端点就是它们的兜底载体。

## 设计取舍
1. **匿名可访问**：监控系统通常没有业务 token。
   但正因如此，**只返回 `ok|error`，不返回任何具体数值**
   —— 磁盘余量、DB 版本、缓存后端这些属于运维细节，不该给匿名者。
   详细原因只回给 `is_staff`。
2. **DB 挂时返回 503 而不是 500**：503 是"暂时不可用"的标准语义，LB 会据此摘流量；
   500 会被误读成"代码有 bug"。
3. **显式 `@renderer_classes([JSONRenderer])` 绕开全局信封**（★ 踩过两次）：
   项目有全局 `EnvelopeRenderer`，会把 DRF 响应包成 `{success,data,meta}` ——
   503 时 `{status, checks}` 会被塞进 `meta.error`，监控端拿不到 `status` 字段。
   第一版改用纯 Django `JsonResponse` 绕开，结果 `force_authenticate`（DRF 机制）
   对纯 Django 视图无效，staff 判定永远 False。
   ⇒ 正解：**保留 DRF 视图（认证走 DRF），只替换 renderer**。
4. **自身绝不抛异常**：每项检查各自 try/except，**外层再套一层 `_safe`**
   —— 因为"检查函数自己抛异常"和"检查函数返回失败"是两件事，
   第一版只做了内层捕获，实测被 patch 成抛异常时端点直接 500。健康检查自己崩掉就没意义。
"""
import logging
import os
import shutil

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

logger = logging.getLogger(__name__)

#: 磁盘余量低于此值判 degraded。1GB 是"还能写，但该处理了"的经验阈值。
MIN_DISK_FREE_BYTES = 1024 ** 3


def _check_db():
    """最轻的连通性探针。返回 (ok, 错误类型名)。"""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return True, ''
    except Exception as exc:                      # noqa: BLE001
        # 只记异常类型 —— 不要把 DSN / 用户 / 主机写进响应
        return False, type(exc).__name__


def _check_cache():
    """写-读回环。LocMem 与 Redis 都适用。"""
    try:
        key = '__health_probe__'
        cache.set(key, '1', 5)
        ok = cache.get(key) == '1'
        return (True, '') if ok else (False, 'roundtrip_mismatch')
    except Exception as exc:                      # noqa: BLE001
        return False, type(exc).__name__


def _check_disk():
    """看媒体目录所在盘的余量（上传都写那里）。目录不存在则退到 BASE_DIR。"""
    try:
        target = str(getattr(settings, 'MEDIA_ROOT', '') or settings.BASE_DIR)
        if not os.path.isdir(target):
            target = str(settings.BASE_DIR)
        free = shutil.disk_usage(target).free
        if free < MIN_DISK_FREE_BYTES:
            return False, 'low_disk'
        return True, ''
    except Exception as exc:                      # noqa: BLE001
        return False, type(exc).__name__


def _safe(name, fn):
    """外层兜底：检查函数**自己抛异常**时也转成 (False, 类型名)。

    为什么需要两层：`_check_db` 内部有 try/except，但那只覆盖它预期的失败
    （连接错误等）。如果它本身有 bug（或被替换/被 patch 成抛异常），
    内层捕获不到 —— 第一版就因此让端点 500，被测试抓到。
    """
    try:
        return fn()
    except Exception as exc:                      # noqa: BLE001
        logger.warning('health check %r raised: %r', name, exc)
        return False, type(exc).__name__


@api_view(['GET'])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])       # 裸 JSON，不套 EnvelopeRenderer
def health_check(request):
    """GET /api/v1/health/ — 200 = 全部正常；503 = 有检查项失败。

    响应（匿名）：
        {"status": "ok"|"degraded", "checks": {"db":"ok","cache":"ok","disk":"ok"}}
    staff 追加 `details`，说明哪一项为什么失败。
    """
    results = {
        'db': _safe('db', _check_db),
        'cache': _safe('cache', _check_cache),
        'disk': _safe('disk', _check_disk),
    }
    checks = {name: ('ok' if ok else 'error') for name, (ok, _err) in results.items()}
    healthy = all(v == 'ok' for v in checks.values())

    payload = {
        'status': 'ok' if healthy else 'degraded',
        'checks': checks,
    }

    # 详细原因只给内部人员：匿名者拿到 "db=error" 就够判断了，
    # 具体异常类型/磁盘数值属于运维信息。
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_staff', False):
        payload['details'] = {n: err for n, (ok, err) in results.items() if not ok}

    return Response(payload, status=200 if healthy else 503)
