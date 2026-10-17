"""SDS 修订日期的业务时区（东八区）回归测试。

背景：生产 `TIME_ZONE='UTC'`，而 SDS 的 `revised_at` 是写进合规业务档案的
**日历日**，必须按 `settings.BUSINESS_TIME_ZONE`（默认 `Asia/Shanghai`）判定。
东八区 00:00-07:59 之间，UTC 日期比业务日期晚一天 ⇒ 该窗口生成的 SDS
修订日期会**回退一天**。

实现原为 `datetime.date.today()`，取的是**进程操作系统时区**；生产容器 TZ 为 UTC
时它等于 UTC 日期 —— 这正是本文件要锁定的缺陷。

伪造时刻：UTC 2026-10-16 16:30 == 东八区 2026-10-17 00:30
  → UTC 日期 = 2026-10-16，业务日期 = 2026-10-17（差一天）
"""
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as dj_tz

from apps.commerce.tests.factories import ProductFactory
from apps.documents.models import SdsRevision
from apps.documents.services import workflow as wf

FAKE_NOW = datetime(2026, 10, 16, 16, 30, tzinfo=ZoneInfo('UTC'))
FAKE_BIZ_DATE = date(2026, 10, 17)
FAKE_UTC_DATE = date(2026, 10, 16)


@contextmanager
def _patch_process_date_today(module, fixed):
    """把被测模块里 `date.today()` 固定为 `fixed`，模拟生产容器 TZ=UTC。

    只 patch 被测模块自己的 `datetime` 名字（workflow 用 `import datetime` +
    `datetime.date.today()`）；**刻意不 patch 全局 `datetime.date`** ——
    否则 Django 的 DateField.to_python 会因 `parse_date` 拿到非 str 而炸
    （实测 TypeError: fromisoformat: argument must be str）。
    """
    assert fixed is not None

    class _FixedTodayDate(date):
        @classmethod
        def today(cls):
            return fixed

    class _DatetimeProxy:
        def __getattr__(self, name):
            if name == 'date':
                return _FixedTodayDate
            return getattr(datetime, name)

    with patch.object(module, 'datetime', _DatetimeProxy()):
        yield


@pytest.mark.django_db
class TestSdsRevisedAtBusinessDate:
    def _create(self, product):
        return wf._create_sds_revision(
            product,
            signal_word='Warning', pictograms=[], hazard_codes=[],
            precaution_codes=[], section_data={},
            confidence=SdsRevision.DataConfidence.LOW, source_detail='tz probe',
        )

    def test_process_today_simulated_as_utc(self):
        """前置自检：确认模拟环境成立，否则后续断言无意义。"""
        with _patch_process_date_today(wf, FAKE_UTC_DATE):
            assert wf.datetime.date.today() == FAKE_UTC_DATE
            assert wf.datetime.date.today() != FAKE_BIZ_DATE

    def test_revised_at_uses_business_date_in_early_hours(self):
        """东八区 00:30 创建 SDS：revised_at 必须是业务日期，不是 UTC 日期。"""
        assert FAKE_BIZ_DATE != FAKE_UTC_DATE, '伪造时刻必须落在跨日窗口内'
        product = ProductFactory()

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW), \
                _patch_process_date_today(wf, FAKE_UTC_DATE):
            sds = self._create(product)

        assert sds.revised_at == FAKE_BIZ_DATE, (
            f'SDS 修订日期应为业务日期 {FAKE_BIZ_DATE}，实际 {sds.revised_at}'
        )
        assert sds.revised_at != FAKE_UTC_DATE, '修订日期不得回退到 UTC 日期'

    def test_revised_at_matches_business_date_in_real_time(self):
        """正常时段（当前真实时刻）：业务日期 == 系统本地日期，不应被改坏。"""
        product = ProductFactory()
        sds = self._create(product)
        assert sds.revised_at == datetime.now(ZoneInfo('Asia/Shanghai')).date()