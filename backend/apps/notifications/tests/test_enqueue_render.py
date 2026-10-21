"""`EmailService.enqueue` / `render_template` / 序列化器 / 模型 —— notifications 的"入队侧"测试。

## 为什么补这一批（2026-10-21）
`apps/notifications` 是风险评分里的 **P1（静默失败）**，但此前**只有 5 条测试**，且全在"发送侧"
（`test_send_outbox.py`）。而"入队侧"——模板渲染、多收件人、缺变量、附件——**一条都没测**。
按方案 §2.5 的量化线（P0：每个写操作 ≥3 条；边界 ≥5 条），本文件补齐入队侧的边界。

## 特别注意的两个"静默失败"点
1. `render_template` 用 `format_map(_SafeDict)`：**缺失变量渲染成空串**，不抛错。
   这会让邮件正文"悄悄少一段"（如 "Hi , your order  is ready"）——必须固化当前行为，
   否则将来有人改成抛错/保留原文，是**行为变更**而没人发现。
2. 模板 miss 时**不报错**，直接用调用方传的 subject/body（可能是空）⇒ 会发出一封空主题邮件。
   这里断言"miss 时如实使用传入值"，把"应该配模板"这件事变成可见事实，而不用异常打断业务。
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import EmailOutbox, EmailTemplate
from apps.notifications.serializers import EmailOutboxSerializer, EmailTemplateSerializer
from apps.notifications.services import EmailService, render_template


class RenderTemplateTest(TestCase):
    """`render_template` 的边界 —— 全是"静默失败"高发区。"""

    def test_empty_text_returns_empty(self):
        self.assertEqual(render_template('', {'a': 1}), '')
        self.assertEqual(render_template(None, {'a': 1}), '')

    def test_plain_substitution(self):
        self.assertEqual(render_template('Hi {name}!', {'name': 'Ada'}), 'Hi Ada!')

    def test_multiple_and_repeated_placeholders(self):
        self.assertEqual(
            render_template('{a}-{b}-{a}', {'a': 'X', 'b': 'Y'}), 'X-Y-X')

    def test_missing_key_renders_empty_not_error(self):
        """★ 固化"缺变量 → 空串"这一既有语义（不抛错、不保留 `{name}` 原文）。"""
        self.assertEqual(render_template('Hi {name}!', {}), 'Hi !')
        self.assertEqual(render_template('Hi {name}!', None), 'Hi !')

    def test_malformed_placeholder_returns_original(self):
        """非法格式（未闭合花括号）⇒ 兜底返回原文，绝不抛错。"""
        bad = 'Total {amount'
        self.assertEqual(render_template(bad, {'amount': 1}), bad)

    def test_non_string_context_value_is_stringified(self):
        self.assertEqual(render_template('n={n}', {'n': 42}), 'n=42')


class EnqueueTest(TestCase):
    """`EmailService.enqueue` —— 唯一的写入口，P0 标准要求覆盖正常/边界/异常。"""

    def test_single_recipient_string(self):
        ob = EmailService.enqueue('welcome', to='a@example.com', subject='Hi', body_text='Hello')
        self.assertEqual(ob.to_emails, 'a@example.com')
        self.assertEqual(ob.status, EmailOutbox.Status.PENDING)
        self.assertEqual(ob.subject, 'Hi')
        self.assertEqual(ob.body_text, 'Hello')

    def test_recipient_list_joined_by_comma(self):
        ob = EmailService.enqueue('welcome', to=['a@x.com', 'b@x.com'], subject='Hi')
        self.assertEqual(ob.to_emails, 'a@x.com,b@x.com')

    def test_recipient_tuple_and_set(self):
        ob = EmailService.enqueue('welcome', to=('a@x.com', 'b@x.com'), subject='Hi')
        self.assertEqual(ob.to_emails, 'a@x.com,b@x.com')
        ob2 = EmailService.enqueue('welcome', to={'solo@x.com'}, subject='Hi')
        self.assertEqual(ob2.to_emails, 'solo@x.com')

    def test_pending_is_immediately_deliverable(self):
        """入队后 `next_retry_at` 必须已设且到期，否则 cron 永远捞不到它。"""
        ob = EmailService.enqueue('welcome', to='a@x.com', subject='Hi')
        self.assertIsNotNone(ob.next_retry_at)
        self.assertLessEqual(ob.next_retry_at, timezone.now() + timedelta(seconds=1))

    def test_attachments_default_empty(self):
        ob = EmailService.enqueue('welcome', to='a@x.com', subject='Hi')
        self.assertEqual(ob.attachment_paths, [])

    def test_attachments_persisted(self):
        ob = EmailService.enqueue('welcome', to='a@x.com', subject='Hi',
                                  attachments=['/tmp/a.pdf', '/tmp/b.pdf'])
        ob.refresh_from_db()
        self.assertEqual(ob.attachment_paths, ['/tmp/a.pdf', '/tmp/b.pdf'])

    def test_context_persisted_for_audit(self):
        ctx = {'order_no': 'ORD-1', 'total': '12.00'}
        ob = EmailService.enqueue('welcome', to='a@x.com', ctx=ctx)
        ob.refresh_from_db()
        self.assertEqual(ob.context_json, ctx)

    def test_template_hit_renders_subject_and_bodies(self):
        EmailTemplate.objects.create(
            key='order-shipped',
            subject='Order {order_no} shipped',
            body_text='Hi {name}, {order_no} is on the way.',
            body_html='<p>Hi {name}</p>',
        )
        ob = EmailService.enqueue('order-shipped', to='a@x.com',
                                  ctx={'order_no': 'ORD-9', 'name': 'Ada'},
                                  subject='IGNORED', body_text='IGNORED')
        self.assertEqual(ob.subject, 'Order ORD-9 shipped')
        self.assertEqual(ob.body_text, 'Hi Ada, ORD-9 is on the way.')
        self.assertEqual(ob.body_html, '<p>Hi Ada</p>', '模板命中时正文应被渲染覆盖')
        self.assertEqual(ob.template_key, 'order-shipped')

    def test_template_hit_with_missing_variable_leaves_hole(self):
        """★ 静默失败点：模板变量缺失 ⇒ 渲染成空串（不报错）。固化它。"""
        EmailTemplate.objects.create(key='greet', subject='Hi {name}', body_text='Hello {name}')
        ob = EmailService.enqueue('greet', to='a@x.com', ctx={})
        self.assertEqual(ob.subject, 'Hi ')
        self.assertEqual(ob.body_text, 'Hello ')

    def test_template_miss_uses_caller_values(self):
        """★ 模板未配置时**不报错**，直接用调用方传的 subject/body（可能为空）。"""
        ob = EmailService.enqueue('no-such-template', to='a@x.com',
                                  subject='Direct subject', body_text='Direct body')
        self.assertEqual(ob.subject, 'Direct subject')
        self.assertEqual(ob.body_text, 'Direct body')
        self.assertEqual(ob.template_key, 'no-such-template')

    def test_template_miss_and_empty_values_still_enqueues(self):
        """即使 subject 为空也照样入队 —— 说明"漏配模板"不会被拦截，只会发出空主题邮件。"""
        ob = EmailService.enqueue('no-such-template', to='a@x.com')
        self.assertEqual(ob.subject, '')
        self.assertEqual(ob.status, EmailOutbox.Status.PENDING)


class OutboxModelTest(TestCase):
    def test_default_status_is_pending(self):
        ob = EmailOutbox.objects.create(to_emails='a@x.com', subject='s')
        self.assertEqual(ob.status, EmailOutbox.Status.PENDING)

    def test_str_contains_id_recipient_status(self):
        ob = EmailOutbox.objects.create(to_emails='a@x.com', subject='s')
        text = str(ob)
        self.assertIn(str(ob.id), text)
        self.assertIn('a@x.com', text)
        self.assertIn(ob.status, text)

    def test_ordering_newest_first(self):
        self.assertEqual(EmailOutbox._meta.ordering, ['-created_at'])


class SerializerContractTest(TestCase):
    """序列化器字段集 —— 防止"把大字段/敏感字段塞进列表接口"。"""

    def test_outbox_serializer_fields(self):
        fields = set(EmailOutboxSerializer().fields.keys())
        self.assertEqual(fields, {
            'id', 'to_emails', 'cc_emails', 'subject',
            'status', 'retry_count', 'next_retry_at', 'sent_at',
            'template_key', 'created_at',
        })

    def test_outbox_serializer_excludes_bodies_and_error(self):
        """★ 列表接口不该吐正文与 last_error（体积 + 可能含内部异常信息）。"""
        fields = set(EmailOutboxSerializer().fields.keys())
        for k in ('body_html', 'body_text', 'last_error', 'attachment_paths', 'context_json'):
            self.assertNotIn(k, fields, f'{k} 不应出现在 Outbox 列表序列化器里')

    def test_template_serializer_fields(self):
        fields = set(EmailTemplateSerializer().fields.keys())
        self.assertEqual(fields, {
            'id', 'key', 'subject', 'body_html', 'body_text',
            'description', 'language', 'created_at', 'updated_at',
        })

    def test_template_key_must_be_unique(self):
        EmailTemplate.objects.create(key='dup-key', subject='s1')
        ser = EmailTemplateSerializer(data={'key': 'dup-key', 'subject': 's2'})
        self.assertFalse(ser.is_valid())
        self.assertIn('key', ser.errors)
