"""订单列表过滤器（服务端筛选）。

★ 2026-11-20（S5 P-2）：新增 `status__in`。

## 为什么加
两个运营台（Shipment Desk / Invoicing Desk）此前都是
`getOrders({ page_size: 200 })` **拉一页、再在客户端按状态筛**。
`filterset_fields` 的 `status` 是**精确匹配**，一次只能筛一个状态，
所以当时只能整页拉回来自己筛 —— 于是埋了一个静默漏单：

本地 dev 库只读实测（`Order` 全库 1124 条）：
    confirmed 全库 94、最新 200 条内 24 ⇒ **被挤出 200 的 70 单**
既进不了待发货队列、也进不了待开票队列，**页面还不会提示"只显示最近 200 单"**。
只要历史累计单量越过 `page_size` 就开始漏，而且**越用越漏**。

## 怎么修
队列语义交回服务端：一次请求按状态集合筛（`?status__in=confirmed,shipped`），
配合翻页把该队列**取全**。前端不再猜"哪一页里有什么"。

## 为什么还要加 `has_documents`（同日补）

下载中心（`PoDownloadCenter.vue`）此前同样是「拉一页 + 客户端筛」：
`getOrders({ page_size: 100 })` 回来后用 `o.invoice || o.attachments.length` 过滤。
本地只读实测（全库 1124 单）：**有发票的共 267 单**，而最新的 100 单里只有一小部分，
⇒ 客户越早的发票/PO 附件**在下载中心根本不出现**，页面还显示 "No downloadable
documents yet"（看起来像"确实没有文档"）。

修法与上面同源：把「有没有文档」交回服务端判定。
⚠️ 这个参数**只是显示层筛选**，不改变 `get_queryset()` 的可见范围
（客户仍只在自己订单里筛，过滤发生在其**之上**），不构成提权面。

## 为什么不用 `BaseInFilter` + `ChoiceFilter` 混血
实测过，**不行**：`BaseCSVField` 的 docstring 写明"逐值校验由二级基类完成"，
而 `ChoiceField.clean()` 拿到的是**整串列表**，会判成
`confirmed is not one of the available choices`（4 条用例当场红）。见本文件下方
`ChoiceListField` 的写法：解析与逐值校验都自己做，且必须在**字段层**完成 ——
django-filter 只在 `filterset.is_valid()` 成功时才走 `qs`，
在 `filter()` 里抛异常会绕过它、变成 500 而不是 400。
"""
import django_filters
from django import forms
from django.db.models import Q

from apps.transactions.models import Order


class ChoiceListField(forms.Field):
    """逗号分隔的多值 Choice 字段：`?status__in=confirmed,shipped`。

    ★ 逐值校验是刻意的：拼错的状态值必须 400 立刻暴露。
      若静默返回空列表，运营会以为"队列里没单了" —— 而这正是本次要修的
      「队列看起来正常、其实漏了单」那种误导。
    """

    default_error_messages = {
        'invalid': 'Invalid value(s): %(values)s',
    }

    def __init__(self, *, choices=(), **kwargs):
        self.choices = dict(choices)
        super().__init__(**kwargs)

    def to_python(self, value):
        if value is None or value == '' or value == [] or value == ():
            return []
        raw = value if isinstance(value, (list, tuple)) else str(value).split(',')
        accepted, rejected = [], []
        for item in raw:
            token = str(item).strip()
            if not token:
                continue
            if token in self.choices:
                accepted.append(token)
            else:
                rejected.append(token)
        if rejected:
            raise forms.ValidationError(
                self.error_messages['invalid']
                % {'values': ', '.join(sorted(set(rejected)))},
                code='invalid',
            )
        return accepted


class StatusInFilter(django_filters.Filter):
    """按状态集合过滤（`?status__in=a,b`）。"""

    field_class = ChoiceListField

    def filter(self, qs, value):
        if not value:
            return qs
        return qs.filter(status__in=value)


class StrictBooleanField(forms.Field):
    """严格布尔查询参数：只认 `1/0/true/false/yes/no/on/off`，其余 400。

    ★ 为什么不用 `forms.BooleanField`（实测，见 `2026-11-20.md`）
    `BooleanField` 的默认 widget 是 `CheckboxInput`，而它的
    `value_from_datadict()` 在**丢给 `to_python` 之前**就做了 `bool(value)`：

        raw='0'   -> cleaned True    ← bool('0') is True
        raw='abc' -> cleaned True    ← bool('abc') is True
        raw 缺失   -> cleaned False   ← 与"显式传 0"无法区分

    ⇒ 后果是：`?has_documents=0` 与 `=1` **行为相同**，拼错的值静默当成 True，
    而"不传参数"被当成"筛没文档的单"（列表被莫名收窄）。
    这三条都不是理论风险，是本文件首版测试当场红掉的三条断言。
    """

    default_error_messages = {
        'invalid': "Expected one of 1/0/true/false (got '%(value)s')",
    }

    TRUE_VALUES = {'1', 'true', 'yes', 'on'}
    FALSE_VALUES = {'0', 'false', 'no', 'off'}

    def to_python(self, value):
        if value is None:
            return None
        token = str(value).strip().lower()
        if not token:
            return None
        if token in self.TRUE_VALUES:
            return True
        if token in self.FALSE_VALUES:
            return False
        raise forms.ValidationError(
            self.error_messages['invalid'] % {'value': token}, code='invalid',
        )


class HasDocumentsFilter(django_filters.Filter):
    """只返回**有发票或有 PO 附件**的订单（`?has_documents=1`）。

    - `invoice` 是 OneToOne（反向单值）、`attachments` 是反向 FK（可多条）
      ⇒ 必须 `distinct()`，否则带 2 个附件的订单会出现 2 行。
    - 不传该参数 ⇒ `None` ⇒ 不筛（既有列表契约不变）。
    - 非法值在**字段层**拒掉 ⇒ 400，与 `status` / `status__in` 一致
      （不接受静默降级成"没筛"，那会把没文档的单也列出来）。
    """

    field_class = StrictBooleanField

    def filter(self, qs, value):
        if value is None:
            return qs
        if value:
            return qs.filter(
                Q(invoice__isnull=False) | Q(attachments__isnull=False)
            ).distinct()
        return qs.filter(invoice__isnull=True, attachments__isnull=True)


class OrderFilter(django_filters.FilterSet):
    """订单列表过滤器。

    ⚠️ 只**声明**额外过滤器，其余三个（`status` / `organization` /
    `organization_id`）继续交给 `Meta.fields` 自动生成 —— 这样它们的类与校验行为
    与改造前**完全一致**（尤其 `status` 仍是 ChoiceFilter，非法值 400），
    不会因为"顺手统一写法"而改变既有契约。
    """

    status__in = StatusInFilter(field_name='status', choices=Order.Status.choices)
    has_documents = HasDocumentsFilter()

    class Meta:
        model = Order
        fields = ['status', 'organization', 'organization_id']
