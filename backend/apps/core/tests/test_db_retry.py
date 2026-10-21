# -*- coding: utf-8 -*-
"""死锁重试装饰器的契约测试（对应 FAILURE_MODES 5.5）

## 要钉住什么
1. **死锁（40P01）会重试**，且重试成功后返回正常结果
2. **序列化冲突（40001）也会重试**
3. **其它 OperationalError 不重试**（连接断/超时/磁盘满 —— 重试只会放大故障）
4. **非 OperationalError 不重试**（代码 bug 重试无意义）
5. **达到上限后抛出原异常**（不能无限重试）
6. `max_attempts=1` ⇒ 完全不重试
7. **重试期间不真的阻塞**（注入 sleep=no-op，测试必须毫秒级）

## 为什么用构造的异常而不是真 PG
真实死锁需要两个事务交叉加锁，构造复杂且不稳定。
重试逻辑本身与 PG 无关 —— 它只依赖 `OperationalError` + `pgcode`，
所以用构造异常测更精确（也能覆盖"其它错误码不重试"这种真 PG 难造的场景）。
"""
from django.db import OperationalError
from django.test import SimpleTestCase

from core.db_retry import MAX_DELAY, is_retryable, retry_on_deadlock


def _pg_error(code=None, cls=OperationalError):
    """构造带 SQLSTATE 的 OperationalError（psycopg2 把 pgcode 放在 __cause__ 上）。"""
    err = cls('wrapped')
    if code:
        cause = Exception('inner')
        cause.pgcode = code
        err.__cause__ = cause
    return err


class IsRetryableTests(SimpleTestCase):
    def test_deadlock_is_retryable(self):
        self.assertTrue(is_retryable(_pg_error('40P01')))

    def test_serialization_failure_is_retryable(self):
        self.assertTrue(is_retryable(_pg_error('40001')))

    def test_other_sqlstate_not_retryable(self):
        """连接断开(08006)/磁盘满(53100) 重试无用，必须不重试。"""
        for code in ('08006', '53100', '57014'):
            self.assertFalse(is_retryable(_pg_error(code)), f'{code} 不该重试')

    def test_no_sqlstate_not_retryable(self):
        self.assertFalse(is_retryable(_pg_error(None)))

    def test_non_operational_error_not_retryable(self):
        self.assertFalse(is_retryable(ValueError('x')))


class RetryBehaviourTests(SimpleTestCase):
    def setUp(self):
        self.calls = []

    def _fn_raising(self, *errors, then_return='ok'):
        """前 len(errors) 次抛对应异常，之后返回 then_return。"""
        def fn():
            self.calls.append(1)
            idx = len(self.calls) - 1
            if idx < len(errors):
                raise errors[idx]
            return then_return
        return fn

    def test_retries_on_deadlock_then_succeeds(self):
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising(_pg_error('40P01')))
        self.assertEqual(fn(), 'ok')
        self.assertEqual(len(self.calls), 2, f'应重试一次，实际调用 {len(self.calls)} 次')

    def test_retries_on_serialization_failure(self):
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising(_pg_error('40001')))
        self.assertEqual(fn(), 'ok')
        self.assertEqual(len(self.calls), 2)

    def test_gives_up_after_max_attempts(self):
        """连续死锁 ⇒ 用满 max_attempts 后抛出原异常，不能无限重试。"""
        err = _pg_error('40P01')
        fn = retry_on_deadlock(max_attempts=3, sleep=lambda _s: None)(
            self._fn_raising(err, err, err, err))
        with self.assertRaises(OperationalError):
            fn()
        self.assertEqual(len(self.calls), 3, f'应尝试 3 次，实际 {len(self.calls)}')

    def test_does_not_retry_non_deadlock(self):
        err = _pg_error('08006')          # 连接断开
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising(err))
        with self.assertRaises(OperationalError):
            fn()
        self.assertEqual(len(self.calls), 1, '非死锁错误不该重试')

    def test_does_not_retry_non_operational_error(self):
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising(ValueError('bug')))
        with self.assertRaises(ValueError):
            fn()
        self.assertEqual(len(self.calls), 1)

    def test_max_attempts_one_means_no_retry(self):
        fn = retry_on_deadlock(max_attempts=1, sleep=lambda _s: None)(
            self._fn_raising(_pg_error('40P01')))
        with self.assertRaises(OperationalError):
            fn()
        self.assertEqual(len(self.calls), 1)

    def test_success_path_calls_once(self):
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising())
        self.assertEqual(fn(), 'ok')
        self.assertEqual(len(self.calls), 1)

    def test_backoff_is_capped(self):
        """退避不能指数爆炸 —— 必须被 MAX_DELAY 封顶。"""
        delays = []
        err = _pg_error('40P01')
        fn = retry_on_deadlock(max_attempts=5, base_delay=1.0,
                               sleep=lambda s: delays.append(s))(
            self._fn_raising(err, err, err, err, err))
        with self.assertRaises(OperationalError):
            fn()
        self.assertTrue(delays, '应记录到退避')
        self.assertTrue(all(d <= MAX_DELAY for d in delays), f'退避未封顶：{delays}')

    def test_retry_logs_sqlstate(self):
        """重试必须留日志（否则线上只能看到 500，不知道发生过死锁）。"""
        fn = retry_on_deadlock(sleep=lambda _s: None)(self._fn_raising(_pg_error('40P01')))
        with self.assertLogs('core.db_retry', level='WARNING') as cm:
            fn()
        joined = '\n'.join(cm.output)
        self.assertIn('40P01', joined, '日志里必须带 sqlstate，便于线上检索')
