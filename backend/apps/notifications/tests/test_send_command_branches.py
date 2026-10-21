"""`send_outbox_emails` 命令 —— 补充 `test_send_outbox.py` 未覆盖的分支（2026-10-21）

已有 5 条覆盖了主干（正常发送 / 未到点跳过 / HTML 替代体 / 失败重试 / 超限 FAILED）。
本文件补的是**命令参数与批量语义**，这些分支此前一条都没测：

| 分支 | 代码位置 | 为什么重要 |
|---|---|---|
| `--force` 忽略 `next_retry_at` | `handle():32` | 运维抢发手段；写错就会重复轰炸用户 |
| `--limit` 上限 | `handle():34` | 防止一次把几万封全发出去 |
| 非 PENDING 不处理 | `handle():31` | SENT/FAILED 被重发 = 重复通知 |
| `next_retry_at` 为 null 的 PENDING 也投递 | `handle():33` | 漏了这个条件会让老数据永远发不出去 |
| cc 逗号解析（trim + 空项过滤） | `_send():63` | `'a, ,b'` 会带出一个空收件人 |
| 附件不存在时跳过、不中断 | `_send():74` | 附件被清理后不应导致整封发不出去 |
| 成功时清空 `last_error` | `handle():42` | 否则列表里会残留上一次的失败原因 |
| 一封失败不中断整批 | `handle():37-57` | 单封坏数据不该拖垮整批 |
| 退避阶梯 60/300/900/3600/7200 | `handle():51-52` | 重试太密 = 骚扰；太疏 = 延迟 |
| FAILED 不再被后续 cron 捞起 | `handle():31` | 否则会无限重试 |
"""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import EmailOutbox

SEND_PATH = 'apps.notifications.management.commands.send_outbox_emails.EmailMultiAlternatives.send'


class SendCommandBranchesTest(TestCase):
    def _ob(self, **kwargs):
        defaults = dict(
            to_emails='a@example.com', subject='Hi', body_text='Hello',
            status=EmailOutbox.Status.PENDING, next_retry_at=timezone.now(),
        )
        defaults.update(kwargs)
        return EmailOutbox.objects.create(**defaults)

    # ── 状态过滤 ──
    def test_sent_and_failed_are_ignored(self):
        """非 PENDING 一律不碰 —— 否则会重复通知用户。"""
        sent = self._ob(status=EmailOutbox.Status.SENT)
        failed = self._ob(status=EmailOutbox.Status.FAILED)
        call_command('send_outbox_emails')
        self.assertEqual(len(mail.outbox), 0)
        sent.refresh_from_db(); failed.refresh_from_db()
        self.assertEqual(sent.status, EmailOutbox.Status.SENT)
        self.assertEqual(failed.status, EmailOutbox.Status.FAILED)

    def test_pending_with_null_next_retry_is_sent(self):
        """`next_retry_at` 为空的老数据也必须被投递（条件里有 or isnull）。"""
        self._ob(next_retry_at=None)
        call_command('send_outbox_emails')
        self.assertEqual(len(mail.outbox), 1)

    # ── 参数 ──
    def test_force_ignores_future_retry(self):
        ob = self._ob(next_retry_at=timezone.now() + timedelta(hours=5))
        call_command('send_outbox_emails', '--force')
        ob.refresh_from_db()
        self.assertEqual(ob.status, EmailOutbox.Status.SENT, '--force 应忽略 next_retry_at')

    def test_limit_caps_batch_size(self):
        for i in range(3):
            self._ob(to_emails=f'u{i}@example.com')
        call_command('send_outbox_emails', '--limit', '2')
        self.assertEqual(len(mail.outbox), 2, '--limit 2 只应发 2 封')
        self.assertEqual(EmailOutbox.objects.filter(status=EmailOutbox.Status.PENDING).count(), 1)

    # ── 收件人解析 ──
    def test_cc_parsed_trimmed_and_empty_dropped(self):
        self._ob(to_emails='a@x.com, b@x.com', cc_emails=' cc1@x.com , ,cc2@x.com ')
        call_command('send_outbox_emails')
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['a@x.com', 'b@x.com'])
        self.assertEqual(msg.cc, ['cc1@x.com', 'cc2@x.com'], '空项与首尾空格都应被过滤')

    def test_empty_cc_becomes_none(self):
        self._ob(cc_emails='')
        call_command('send_outbox_emails')
        self.assertFalse(mail.outbox[0].cc)

    # ── 附件 ──
    def test_missing_attachment_is_skipped_without_failing(self):
        """附件路径不存在时**跳过**，整封仍正常发出（不该因为附件丢了就发不出去）。"""
        ob = self._ob(attachment_paths=['/nonexistent/dir/x.pdf'])
        call_command('send_outbox_emails')
        ob.refresh_from_db()
        self.assertEqual(ob.status, EmailOutbox.Status.SENT)
        self.assertEqual(len(mail.outbox[0].attachments), 0)

    def test_existing_attachment_attached(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.txt')
        os.write(fd, b'hello')
        os.close(fd)
        try:
            self._ob(attachment_paths=[path])
            call_command('send_outbox_emails')
            self.assertEqual(len(mail.outbox[0].attachments), 1)
        finally:
            os.remove(path)

    # ── 状态与错误字段 ──
    def test_success_clears_previous_last_error(self):
        ob = self._ob(last_error='previous failure')
        call_command('send_outbox_emails')
        ob.refresh_from_db()
        self.assertEqual(ob.last_error, '', '成功后必须清空上次错误')

    def test_one_failure_does_not_stop_the_batch(self):
        """第一封失败、第二封仍要发出（单封坏数据不拖垮整批）。"""
        bad = self._ob(to_emails='bad@x.com')
        good = self._ob(to_emails='good@x.com')
        calls = {'n': 0}

        def _send(msg, *a, **kw):
            calls['n'] += 1
            if calls['n'] == 1:
                raise Exception('smtp down')
            return 1

        with mock.patch(SEND_PATH, autospec=True, side_effect=_send):
            call_command('send_outbox_emails')

        bad.refresh_from_db(); good.refresh_from_db()
        self.assertEqual(bad.retry_count, 1)
        self.assertEqual(bad.status, EmailOutbox.Status.PENDING)
        self.assertEqual(good.status, EmailOutbox.Status.SENT, '第二封不应受第一封失败影响')

    # ── 退避阶梯 ──
    def test_retry_backoff_ladder(self):
        """退避阶梯：首次失败 60s、第 2 次 300s、第 3 次 900s、第 4 次 3600s，第 5 次直接 FAILED。

        ⚠️ 映射来源（读码，不是猜）：`handle()` 先 `retry_count += 1`，再
        `idx = min(retry_count, len(RETRY_BACKOFF_SECONDS)) - 1`
        ⇒ 新 retry_count 1→idx0(60s)、2→idx1(300s)、3→idx2(900s)、4→idx3(3600s)；
        新 retry_count 5 命中 `>= MAX_RETRIES(5)` ⇒ 直接 FAILED，不设 next_retry_at。
        （初版我把 preset 1 也写成 60s，是**测试算错**，实测 300s —— 已按代码修正。）
        """
        expected = {0: 60, 1: 300, 2: 900, 3: 3600}
        for preset, secs in expected.items():
            ob = self._ob(to_emails=f'r{preset}@x.com', retry_count=preset)
            with mock.patch(SEND_PATH, side_effect=Exception('boom')):
                call_command('send_outbox_emails')
            ob.refresh_from_db()
            self.assertEqual(ob.retry_count, preset + 1)
            delta = (ob.next_retry_at - timezone.now()).total_seconds()
            self.assertAlmostEqual(delta, secs, delta=5,
                                   msg=f'retry_count {preset}→{preset+1} 的退避应约 {secs}s，实际 {delta:.0f}s')

    def test_failed_is_not_picked_up_again(self):
        """已 FAILED 的不再被 cron 重试（否则无限重试）。"""
        ob = self._ob(retry_count=4)
        with mock.patch(SEND_PATH, side_effect=Exception('boom')):
            call_command('send_outbox_emails')
        ob.refresh_from_db()
        self.assertEqual(ob.status, EmailOutbox.Status.FAILED)

        # 再跑一次：不该再尝试
        with mock.patch(SEND_PATH) as m:
            call_command('send_outbox_emails')
            m.assert_not_called()

    def test_command_reports_counts(self):
        """命令输出形如 `Sent 1, failed 0`（运维/日志靠它判断批量结果）。

        ⚠️ 不要 `mock.patch('sys.stdout')` —— 会和 pytest 的输出捕获打架，
        实测报 `ValueError: I/O operation on closed file`。
        用 `io.StringIO()` 通过 `call_command(stdout=...)` 注入才是正路。
        """
        import io as _io

        class _SafeBuf(_io.StringIO):
            """Django 会在 GC 时对输出流 flush；普通 StringIO 关闭后 flush 会抛
            `ValueError: I/O operation on closed file`（被解释器打成 "Exception ignored"，
            虽不影响结果但污染输出）⇒ 这里让 flush 幂等。"""
            def flush(self):
                try:
                    super().flush()
                except ValueError:
                    pass

        self._ob()
        buf = _SafeBuf()
        call_command('send_outbox_emails', stdout=buf)
        written = buf.getvalue()
        self.assertIn('Sent 1', written)
        self.assertIn('failed 0', written)
