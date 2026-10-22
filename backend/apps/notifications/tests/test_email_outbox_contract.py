"""X-4 邮件链路 —— 锁住"模板表为空 ⇒ 发出的是空邮件"这个现状。

## 为什么这是个"锁定缺陷"的测试
实测（2026-10-22）：
  · `EmailTemplate` 表 **0 条**
  · `EmailOutbox` 2984 封**全 pending**，历史零 sent
  · 手动跑 `send_outbox_emails` 会真的标记 sent，但发出的邮件**主题与正文都是空**

所以本文件的断言分两类：
  A. **能力断言**（应该永远成立）：入队写 pending、发送命令能标记 sent、重试上限
  B. **缺陷锁定**（修好就该变红）：模板为 0 时 enqueue 不报错但产出空壳

一旦有人补上模板，B 类会失败 —— 那是**好事**，请同步删除/更新这里与说明书 §11.3 #11。
"""
import pytest
from django.core.management import call_command

from apps.notifications.models import EmailOutbox, EmailTemplate
from apps.notifications.services import EmailService


@pytest.mark.django_db
class TestEmailOutbox:
    def test_enqueue_creates_pending(self):
        """能力：入队后状态是 pending，且带上收件人。"""
        o = EmailService.enqueue('po_submitted', 'buyer@example.com', {'order_no': 'X'})
        o.refresh_from_db()
        assert o.status == EmailOutbox.Status.PENDING
        assert o.to_emails == 'buyer@example.com'
        assert o.template_key == 'po_submitted'

    def test_send_command_marks_sent(self):
        """能力：send_outbox_emails 能把 pending 变成 sent（console backend 下不真发但仍标记）。"""
        EmailService.enqueue('order_confirmed', 'buyer@example.com', {'order_no': 'X'})
        assert EmailOutbox.objects.filter(status=EmailOutbox.Status.PENDING).count() == 1

        call_command('send_outbox_emails', '--limit', '1', verbosity=0)

        assert EmailOutbox.objects.filter(status=EmailOutbox.Status.SENT).count() == 1

    def test_missing_template_yields_empty_subject_and_body(self):
        """★ 缺陷锁定：模板缺失时**不报错**，直接用空串入队 ⇒ 空邮件。"""
        assert EmailTemplate.objects.count() == 0, (
            '模板表不再为空 —— 若已补齐模板，请删除本用例并更新说明书 §11.3 #11')
        o = EmailService.enqueue('po_submitted', 'buyer@example.com', {'order_no': 'X'})
        o.refresh_from_db()
        assert o.subject == '', f'期望空主题（当前缺陷），实得 {o.subject!r}'
        assert (o.body_text or '') == '', '期望空正文（当前缺陷）'

    def test_explicit_subject_is_respected(self):
        """能力：直接给 subject/body 时不该被模板逻辑清空（证明上面的空壳是模板缺失导致）。"""
        o = EmailService.enqueue('no_such_template', 'buyer@example.com',
                                 {'order_no': 'X'}, subject='Hi', body_text='Body')
        o.refresh_from_db()
        assert o.subject == 'Hi'
        assert o.body_text == 'Body'
