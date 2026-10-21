# -*- coding: utf-8 -*-
"""PostgreSQL 死锁 / 序列化冲突的**事务级重试**

## 为什么需要（对应 FAILURE_MODES 5.5，此前是最后一条实质空白）
审查结论：**全仓 0 处**处理 `40P01`（deadlock_detected）/ `40001`（serialization_failure）
—— 没有捕获、没有重试、没有日志。也就是说：

> PostgreSQL 检测到死锁时会**主动杀掉其中一个事务** —— 这是它的**正常行为**，
> 不是异常情况。而我们的应用层完全不处理 ⇒ 那个用户的操作**直接变成 500**。
> 生产是 gunicorn `--workers 3 --threads 4`，并发写同一订单/同一库存行时必然偶发。

## 为什么在这里重试是安全的
重试装饰器包在 `@transaction.atomic` **外层**：
死锁发生时整个事务已被 PG 回滚，**其中所有写入（订单、流水、审计、邮件入队）一并撤销**
⇒ 重新开一个事务重跑，不会产生重复副作用。

⚠️ 前提：被装饰的函数内部**不能有不可回滚的副作用**（发真实邮件、调外部非幂等接口）。
本项目这 4 条路径的"外部动作"都是**写表**（`EmailService.enqueue` 写 EmailOutbox），
随事务一起回滚 ⇒ 安全。

## 只重试这两类错误码
- `40P01` deadlock_detected —— PG 已判定死锁并杀掉本事务
- `40001` serialization_failure —— SERIALIZABLE 隔离级别下的冲突

**不重试** `OperationalError` 的其它子类（连接断开、超时、磁盘满）——
那些重试也没用，反而会放大故障。

## 用法
```python
@retry_on_deadlock()
@transaction.atomic
def do_work(): ...
```
装饰器必须在 `transaction.atomic` **外面**（顺序反了等于不重试）。
"""
from __future__ import annotations

import functools
import logging
import time

from django.db import OperationalError

logger = logging.getLogger(__name__)

#: 可安全重试的 PostgreSQL SQLSTATE
RETRYABLE_PGCODES = frozenset({'40P01', '40001'})

#: 默认重试参数：3 次尝试，50ms 起指数退避（最多 200ms）
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.05
MAX_DELAY = 0.2


def _sqlstate(exc: BaseException):
    """从异常链里取出 PostgreSQL SQLSTATE。

    psycopg2 把它放在 `exc.__cause__.pgcode`（`diag.sqlstate` 同值）；
    psycopg3 放在 `exc.__cause__.sqlstate`。这里都试一遍。
    """
    cause = getattr(exc, '__cause__', None) or exc
    code = getattr(cause, 'pgcode', None)
    if code:
        return code
    code = getattr(cause, 'sqlstate', None)
    if code:
        return code
    diag = getattr(cause, 'diag', None)
    return getattr(diag, 'sqlstate', None)


def is_retryable(exc: BaseException) -> bool:
    """只有死锁 / 序列化冲突才值得重试。"""
    if not isinstance(exc, OperationalError):
        return False
    return _sqlstate(exc) in RETRYABLE_PGCODES


def retry_on_deadlock(max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                      base_delay: float = DEFAULT_BASE_DELAY,
                      sleep=time.sleep):
    """死锁重试装饰器。

    Args:
        max_attempts: 最多尝试次数（含首次）。1 = 不重试。
        base_delay: 首次退避秒数，之后按 2 倍递增、上限 MAX_DELAY。
        sleep: 可注入（测试里替换成 no-op，避免真的等）。
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if max_attempts <= 1:
                return fn(*args, **kwargs)
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except OperationalError as exc:
                    if not is_retryable(exc) or attempt == max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), MAX_DELAY)
                    # ★ 记录 sqlstate 而不是整条消息：后者含 SQL 片段，可能有业务数据
                    logger.warning(
                        'deadlock/serialization conflict on %s (sqlstate=%s)，第 %d/%d 次重试，%.0fms 后',
                        getattr(fn, '__name__', 'unknown'), _sqlstate(exc),
                        attempt, max_attempts, delay * 1000,
                    )
                    sleep(delay)
            # 逻辑上不可达（循环内要么 return 要么 raise）
            return fn(*args, **kwargs)
        return wrapper
    return decorator
