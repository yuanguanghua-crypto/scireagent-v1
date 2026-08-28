"""T2.2 结构化审计日志测试（MUST-5，标准 logging，非 StatusLog）。

验证每次 pipeline 产生一条含 product_id + result 的结构化日志记录；
字段经 logging extra 注入为 LogRecord 属性（非 record.extra 子字典）。
"""
import logging
import pytest

from apps.bridges.services.pipeline_log import log_pipeline, LOGGER_NAME

pytestmark = pytest.mark.django_db


def test_log_pipeline_emits_structured_record(caplog):
    """SUCCESS 产生一条含 product_id + result + 边计数的结构化日志。"""
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        log_pipeline(
            product_id=42,
            pipeline_version='0.1.0',
            execution_result='SUCCESS',
            scientific_quality='REVIEW',
            created_edges=0,
            deleted_edges=5,
            duration_ms=12,
            actor='system',
        )
    records = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert records, "应产生 association_pipeline 日志记录"
    rec = records[0]
    assert rec.product_id == 42
    assert rec.execution_result == 'SUCCESS'
    assert rec.scientific_quality == 'REVIEW'
    assert rec.created_edges == 0
    assert rec.deleted_edges == 5
    assert rec.rule_version  # 来自 rule_registry.RULE_VERSION，非空


def test_log_pipeline_failed_uses_error_level(caplog):
    """FAILED 走 logger.error，且携带 error 字段。"""
    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        log_pipeline(
            product_id=7,
            pipeline_version='0.1.0',
            execution_result='FAILED',
            scientific_quality=None,
            created_edges=0,
            deleted_edges=0,
            duration_ms=3,
            actor='system',
            error='boom',
        )
    records = [r for r in caplog.records if r.name == LOGGER_NAME and r.levelno == logging.ERROR]
    assert records, "FAILED 应走 error level"
    assert records[0].error == 'boom'
