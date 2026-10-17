"""业务日历日（BUSINESS_TIME_ZONE）共享助手。

背景：生产 `TIME_ZONE='UTC'`，而逾期/账龄/交付下限/单号日切等"按日历日"的
业务语义必须按 `settings.BUSINESS_TIME_ZONE`（默认 `Asia/Shanghai`）判定。
生产环境两者相差 8 小时 ⇒**东八区 00:00-07:59 之间，UTC 日期与业务日期整整差一天**。
任何用 `timezone.localdate()` / `date.today()` 的实现都会在这个窗口产生错误。

放在 `core/` 而非某个业务 app：多个 app（transactions / documents ...）都需要它，
`core` 是它们共同的基座，跨 app 直接 import 会造成不必要的耦合与循环依赖风险。

历史：`business_today()` 原先定义在 `apps.transactions.models`，现已下沉到此处；
`apps.transactions.models.business_today` 保留为同名转发，已有引用（含测试）无需改动。
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def business_timezone() -> ZoneInfo:
    """业务时区（settings.BUSINESS_TIME_ZONE，默认东八区）。"""
    return ZoneInfo(settings.BUSINESS_TIME_ZONE)


def business_today():
    """业务日历日（settings.BUSINESS_TIME_ZONE，默认东八区）。

    逾期/账龄等"按日历日"的业务判断必须用它，**不能**用 timezone.localdate()：
    生产 TIME_ZONE='UTC' 时 localdate() 等于 UTC 日期，与业务日历日差一天。
    """
    return timezone.now().astimezone(ZoneInfo(settings.BUSINESS_TIME_ZONE)).date()


def business_day_bounds(day=None):
    """返回某个业务日历日 [day 00:00, 次日 00:00) 对应的 aware datetime 区间。

    用于 ORM 过滤：`Model.objects.filter(created_at__gte=start, created_at__lt=end)`。

    为什么不直接用 `created_at__date=`：Django 的 `__date` lookup 按
    `settings.TIME_ZONE`（生产为 UTC）做日期截断，不是按业务时区，
    在东八区凌晨窗口内会切错日期。传**带时区的 aware datetime** 给 `__gte/__lt`
    时 Django 用其自带绝对时刻比较，与 TIME_ZONE 无关 ⇒ 正确。

    :param day: 业务日期（date）；None 表示当前业务日。
    """
    if day is None:
        day = business_today()
    tz = ZoneInfo(settings.BUSINESS_TIME_ZONE)
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)