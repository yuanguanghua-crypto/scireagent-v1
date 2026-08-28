"""Phase 2 结构化审计日志（T2.2，修正 MUST-5）。

依据 product_association_infra_plan_v0.2.md §6 / §7 MUST-5 + 任务 T2.2。
不使用 StatusLog（订单维度表，order 外键必填，复用需迁移越 scope）。

采用标准 logging 模块 + 专用 logger `association_pipeline`，每条记录以结构化 extra
字段附加，便于集中采集与回溯。字段集（方案 §6 末行 + T2.2 验收）：
    product_id, pipeline_version, rule_version,
    execution_result, scientific_quality,
    created_edges, deleted_edges, duration_ms, actor, error

调用方负责传入上述字段；本模块只做"组装 extra + logger.info/error"的薄封装。
FAILED 走 logger.error，其余走 logger.info（便于告警规则按 level 订阅）。
"""
import logging

from apps.bridges.services.rule_registry import RULE_VERSION

LOGGER_NAME = 'association_pipeline'
logger = logging.getLogger(LOGGER_NAME)


def log_pipeline(*, product_id, pipeline_version, execution_result,
                 scientific_quality, created_edges, deleted_edges,
                 duration_ms, actor, error=None, rule_version=RULE_VERSION):
    """写一条关联管线结构化审计日志。

    :param product_id: 产品主键
    :param pipeline_version: 管线编排版本（association_service.PIPELINE_VERSION）
    :param rule_version: 规则注册表版本（rule_registry.RULE_VERSION）
    :param execution_result: SUCCESS | FAILED | SKIPPED（MUST-4 / A1）
    :param scientific_quality: ACCEPTABLE | REVIEW（MUST-4；SKIPPED 时为 None）
    :param created_edges: 本次重建写入的 derived 边计数
    :param deleted_edges: 本次重建删除的 derived 边计数
    :param duration_ms: 管线耗时（毫秒）
    :param actor: 触发者标识（user id / 'system'）；Phase 2 暂由调用方透传
    :param error: 系统错误信息（FAILED 时非空）
    """
    extra = {
        'product_id': product_id,
        'pipeline_version': pipeline_version,
        'rule_version': rule_version,
        'execution_result': execution_result,
        'scientific_quality': scientific_quality,
        'created_edges': created_edges,
        'deleted_edges': deleted_edges,
        'duration_ms': duration_ms,
        'actor': actor,
        'error': error,
    }
    if execution_result == 'FAILED':
        logger.error('association_pipeline.executed', extra=extra)
    else:
        logger.info('association_pipeline.executed', extra=extra)
