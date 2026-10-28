# -*- coding: utf-8 -*-
"""
`Order.unpaid_reminder_sent_at` —— 未付款提醒的「已发送」标记（2026-10-28）。

只有 AddField，nullable、无默认值 ⇒ 对存量订单是 NULL（= 没提醒过），
第一次跑到 `remind_unpaid_orders` 时老订单也会被提醒一次。这是期望行为：
它们确实还没付款，客户该收到一封。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0009_ordersequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='unpaid_reminder_sent_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='未付款提醒已发送时间'),
        ),
    ]
