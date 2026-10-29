# -*- coding: utf-8 -*-
"""SKU 取价 —— **全站唯一入口**（2026-10-29）。

## 为什么必须收敛到一处

改造前 `sku.price` 被 6 处各自读取：购物车行、结账小计、订单行落库、PO 提交覆盖、
产品列表 min/max、首页起价。只要有一处漏改，就会出现**前端显示 $90、实际扣 $100**
这种"报价与实际不一致"的问题 —— 而且它不会报错，只会在客户对账时爆出来。

所以规矩是：**任何需要单价的地方都调 `resolve_unit_price()`，不许再直接读 `sku.price`。**

## 优先级（2026-10-29 产品确认）

    报价单价  >  阶梯价  >  SKU 目录价

- **报价单价**：目前 `QuoteRequest` 只有整单 `quoted_total`，**没有逐行报价**
  （`QuoteRequestItem` 无 `quoted_unit_price`）⇒ 该优先级现在只能传入、还不能自动取。
  等报价单加了逐行报价再接通。这一层先留好形参，不要假装已支持。
- **阶梯价**：按**单个 SKU 的数量**匹配（不是订单内所有产品合计，与行业惯例一致）。
- **目录价**：兜底。保证"没配阶梯价的 SKU"行为与改造前完全一致。

## 阶梯价是价目表，不是折扣

返回的是**该档的单价**，不是折扣率。展示与计算用同一个数，避免"先算折后价再四舍五入"
和"直接取档位价"两种算法给出不同结果。
"""
from decimal import Decimal

from apps.commerce.models import SkuPriceTier


def build_tier_map(skus) -> dict:
    """一次查库，返回 `{sku_id: [tier, ...]}`（按 min_qty 升序）。

    批量场景（订单有多行、产品列表有多 SKU）必须用它，否则 6 处取价点会各自
    退化成 N+1 查询。
    """
    ids = [s.pk for s in skus if s is not None and s.pk]
    out = {i: [] for i in ids}
    if not ids:
        return out
    for t in (SkuPriceTier.objects
              .filter(sku_id__in=ids)
              .order_by('sku_id', 'min_qty')):
        out.setdefault(t.sku_id, []).append(t)
    return out


def resolve_unit_price(sku, quantity, *, tiers=None,
                       quote_unit_price=None) -> Decimal:
    """取该 SKU 在 `quantity` 下的单价。

    参数：
      tiers             预取的档位列表（`build_tier_map` 出来的），不传则现查一次。
      quote_unit_price  报价单给的行级单价。**目前无调用方**（报价单还没有逐行报价），
                        形参先留着，避免以后改签名波及 6 个调用点。
    """
    if quote_unit_price is not None:
        return Decimal(str(quote_unit_price))

    if sku is None:
        return Decimal('0')

    qty = int(quantity or 0)
    if qty > 0:
        rows = tiers if tiers is not None else list(
            sku.price_tiers.all().order_by('min_qty'))
        best = None
        for t in rows:
            # 取「min_qty <= 数量」里最大的那一档；升序遍历时不断覆盖即可
            if t.min_qty <= qty and (best is None or t.min_qty > best.min_qty):
                best = t
        if best is not None:
            return best.unit_price

    return sku.price or Decimal('0')


def start_price(sku, *, tiers=None) -> Decimal:
    """最低可售价 —— 用于「From $X」起价展示。

    为什么不是直接取 `sku.price`：配了阶梯价的 SKU，最低档单价通常低于 1 件价，
    首页/列表若显示 1 件价，客户会以为"买多也不便宜"，阶梯价就白配了。
    """
    if sku is None:
        return Decimal('0')
    rows = tiers if tiers is not None else list(sku.price_tiers.all())
    prices = [sku.price or Decimal('0')] + [t.unit_price for t in rows]
    return min(prices)


def tier_segments(tiers) -> list:
    """把档位转成给前端展示的分段表（含每档的 max，最后一档为 None）。

    `max_qty` 由下一档的 `min_qty - 1` 推算，前端不需要自己算（避免各页算法不一致）。
    价格输出字符串：DRF 的 Decimal 序列化在某些配置下会带尾随零差异，统一 str 更稳。
    """
    rows = sorted(tiers or [], key=lambda t: t.min_qty)
    out = []
    for i, t in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        out.append({
            'min_qty': t.min_qty,
            'max_qty': (nxt.min_qty - 1) if nxt else None,
            'unit_price': f'{t.unit_price:.2f}',
        })
    return out
