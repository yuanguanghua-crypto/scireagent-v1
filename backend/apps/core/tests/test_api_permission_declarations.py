"""★ API 权限声明守卫（2026-09-24 立）。

## 为什么要这条守卫

项目**未设** `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`（`config/settings/base.py`）⇒
DRF 落到默认 `AllowAny`。而 view 定义**散落在 28 个模块**（`views.py` / `*_views.py` /
`basket_views.py` / `faq_views.py` / `categories.py` …）⇒ 只要某个类忘了写 `permission_classes`，
它就**静默变成匿名可读写**，且**没有任何测试或工具会报警**。

2026-09-24 审计实测（判据必须用 **own class attr**：DRF 的 `APIView.permission_classes` 默认就是
`[AllowAny]`，用 `getattr` 无法区分"显式写了 AllowAny"与"根本没写"）：
显式 `[AllowAny]` 13 个（有意公开）· 显式 `[]` 1 个（询价提交，注释说明有意）·
`get_permissions` 重写 1 个 · 显式其他权限 55 个 · **真·隐式 10 个**。

本守卫把"隐式"这一族**堵死**：任何 view 类若既没有**自己声明** `permission_classes`，
也没有重写 `get_permissions()` ⇒ **红灯**。

## `_PENDING_FIX` 是什么

10 个真·隐式里，`CategoryTreeView` 已确认为"有意公开"并显式化；其余 **9 个**是待收口项，
每项在 2026-09-24 审计里有明确归属与计划（收紧 / 修 500 / 删死代码）⇒ 暂列白名单。
**白名单是燃尽清单**：收口完成后应清空 —— 清空后本守卫即无豁免。
"""
import importlib
import os
import re

import pytest

pytestmark = pytest.mark.django_db


# ── 待收口的 9 个（真·隐式；每一项都有明确计划，不是"永久豁免"） ────────────────
_PENDING_FIX = {
    # commerce：后台主数据/文档 —— 前端对这些**只有 GET** ⇒ 可安全收紧为 IsAdminOrReadOnly
    'apps.commerce.api.v1.views:SKUViewSet',
    'apps.commerce.api.v1.views:ProductClassViewSet',
    'apps.commerce.api.v1.views:CatalogGroupViewSet',
    'apps.commerce.api.v1.views:ProductDocumentViewSet',   # 含不可逆 DELETE /documents/{id}
    'apps.commerce.api.v1.views:ProductDetailAPIView',
    # transactions：订单/询价/收藏/购物车
    'apps.transactions.api.v1.views:OrderViewSet',          # 前端不用 POST /orders/（走 /checkout/）
    'apps.transactions.api.v1.views:QuoteViewSet',
    'apps.transactions.api.v1.views:WishlistViewSet',       # 匿名 POST 必 500（模型 user 非空）
    'apps.transactions.api.v1.views:BasketViewSet',         # 未被路由（死代码）
}

_APPS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _discover_view_classes():
    """返回 {(模块:类名): cls}，覆盖 apps 下所有可能定义 view 的模块。

    ⚠️ 只做**文本预筛**（含 `APIView`/`ViewSet` 字样）再 import，避免 import 全仓模块；
    但**候选模块 import 失败必须显式报错** —— 否则"import 炸了"会静默漏掉里面的 view。
    """
    from rest_framework.views import APIView
    from rest_framework.viewsets import ViewSetMixin

    found, import_errors = {}, []
    for root, dirs, files in os.walk(_APPS_DIR):
        dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
        for fn in files:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding='utf-8') as fh:
                    text = fh.read()
            except OSError:
                continue
            if 'APIView' not in text and 'ViewSet' not in text:
                continue
            rel = os.path.relpath(path, os.path.dirname(_APPS_DIR))
            module = re.sub(r'\.py$', '', rel.replace(os.sep, '.'))
            try:
                mod = importlib.import_module(module)
            except Exception as exc:            # noqa: BLE001 — 显式上报，不静默
                import_errors.append('%s: %s: %s' % (module, type(exc).__name__, exc))
                continue
            for name, obj in vars(mod).items():
                if not isinstance(obj, type) or getattr(obj, '__module__', None) != module:
                    continue
                if issubclass(obj, APIView) or issubclass(obj, ViewSetMixin):
                    found['%s:%s' % (module, name)] = obj
    return found, import_errors


class TestApiPermissionDeclarations:
    """每个 view 类都必须**自己**声明权限（或重写 `get_permissions`）。"""

    def test_candidate_modules_all_importable(self):
        """候选模块必须都能 import：否则该模块里的 view 会被静默漏检。"""
        _, errors = _discover_view_classes()
        assert not errors, '以下模块 import 失败，权限守卫无法覆盖：\n  ' + '\n  '.join(errors)

    def test_every_view_declares_permissions_explicitly(self):
        found, _ = _discover_view_classes()
        assert len(found) > 60, '发现的 view 类过少（%d），守卫可能没生效' % len(found)

        undeclared = sorted(
            key for key, cls in found.items()
            if 'permission_classes' not in cls.__dict__ and 'get_permissions' not in cls.__dict__
        )
        unexpected = [k for k in undeclared if k not in _PENDING_FIX]
        assert not unexpected, (
            '以下 view 类**没有显式声明** `permission_classes`/`get_permissions` ⇒ '
            '会落到 DRF 默认 `AllowAny`（匿名可读写）。请显式声明（有意公开就写 `AllowAny`）：\n  '
            + '\n  '.join(unexpected)
        )

    def test_pending_fix_list_does_not_rot(self):
        """燃尽清单里的每一项都必须仍然存在 —— 收口后请一并删除对应条目。"""
        found, _ = _discover_view_classes()
        gone = sorted(k for k in _PENDING_FIX if k not in found)
        assert not gone, '燃尽清单已失效（类不存在），请清理 `_PENDING_FIX`：\n  ' + '\n  '.join(gone)
