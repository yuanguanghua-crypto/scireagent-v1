from django.db import models
from core.models import TimeStampedModel


class EmailOutbox(TimeStampedModel):
    """邮件发件箱 — Outbox 模式，cron 实际投递，请求线程不阻塞。"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    to_emails = models.CharField(max_length=2000, verbose_name='收件人')
    cc_emails = models.CharField(max_length=2000, blank=True, default='', verbose_name='抄送')
    subject = models.CharField(max_length=500, verbose_name='主题')
    body_text = models.TextField(blank=True, default='', verbose_name='正文(纯文本)')
    body_html = models.TextField(blank=True, default='', verbose_name='正文(HTML)')
    attachment_paths = models.JSONField(default=list, verbose_name='附件路径列表')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    retry_count = models.IntegerField(default=0, verbose_name='重试次数')
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name='下次重试时间')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    last_error = models.TextField(blank=True, default='', verbose_name='最后错误')
    template_key = models.CharField(max_length=100, blank=True, default='', verbose_name='模板键')
    context_json = models.JSONField(default=dict, verbose_name='渲染上下文')

    class Meta:
        db_table = 'email_outbox'
        verbose_name = '邮件发件箱'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Outbox #{self.id} → {self.to_emails} [{self.status}]'


class EmailTemplate(TimeStampedModel):
    """邮件模板 — key 唯一，Admin 可改；代码只引用 key。"""

    key = models.SlugField(max_length=100, unique=True, verbose_name='模板键')
    subject = models.CharField(max_length=500, verbose_name='主题')
    body_html = models.TextField(blank=True, default='', verbose_name='HTML 正文')
    body_text = models.TextField(blank=True, default='', verbose_name='纯文本正文')
    description = models.TextField(blank=True, default='', verbose_name='说明')
    language = models.CharField(max_length=10, default='en', verbose_name='语言')

    class Meta:
        db_table = 'email_template'
        verbose_name = '邮件模板'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'Template[{self.key}]'
