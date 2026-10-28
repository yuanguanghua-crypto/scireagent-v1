# -*- coding: utf-8 -*-
"""未付款提醒（`remind_unpaid_orders`）—— 2026-10-28。

业务背景：下单/审核会真实占用库存。客户下单后不付款 ⇒ 货被锁、别人买不到，
而且**不报任何错**。所以释放（7 天）之前必须有一个更早的提醒点（3 天）。

这个命令的失效方式同样全是静默的，所以每条都钉：
  · 该提醒的没提醒 ⇒ 客户直到库存被释放才知道；
  · 不该提醒的提醒了 ⇒ 已付款客户的体验崩（"你们系统在乱发信"）；
  · 重复提醒 ⇒ 客户把我们的信全丢垃圾箱，以后要紧的信也看不到；
  · 没有邮箱却"以为发了" ⇒ 没人知道提醒没送达。
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.notifications.models import EmailOutbox, EmailTemplate
from apps.transactions.models import Order


class ReminderBase(TestCase):
    def setUp(self):
        # 用**真实模板**：这样连"模板里有裸 {} 被当成占位符吃掉"这类问题也一起测到。
        call_command('seed_email_templates', verbosity=0)
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='rem_res', password='x', email='rem@lab.edu',
            organization=self.org, role='researcher')
        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-rem')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC9500-1', price=Decimal('59.00'))

    def _order(self, days_ago, status=Order.Status.CONFIRMED,
               email='buyer@lab.edu', amount='118.00', po=None):
        order = Order.objects.create(
            user=self.user,
            order_no=f'ORD-REM-{Order.objects.count() + 1}',
            status=status,
            shipping_name='Buyer',
            shipping_email=email,
            grand_total=Decimal(amount),
            currency='USD',
            po_number=po,
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago))
        order.refresh_from_db()
        return order


class ReminderRuleTest(ReminderBase):
    def test_reminds_unpaid_order_older_than_3_days(self):
        order = self._order(days_ago=4)
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)

        self.assertEqual(EmailOutbox.objects.count(), 1)
        mail = EmailOutbox.objects.get()
        self.assertIn(order.order_no, mail.subject)
        self.assertIn('buyer@lab.edu', mail.to_emails)
        # 正文要点：金额、已过天数、释放阈值（客户得知道后果）
        self.assertIn('118.00', mail.body_text)
        self.assertIn('4 days', mail.body_text)
        self.assertIn('7 days', mail.body_text)

        order.refresh_from_db()
        self.assertIsNotNone(order.unpaid_reminder_sent_at,
                             '发信后必须打标记，否则下次会重复发')

    def test_does_not_remind_fresh_order(self):
        self._order(days_ago=1)
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0)

    def test_does_not_remind_paid_or_completed(self):
        for st in (Order.Status.PAID, Order.Status.COMPLETED):
            self._order(days_ago=10, status=st, email=f'{st}@lab.edu', po=f'PO-{st}')
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0, '已付款的单不该被催')

    def test_does_not_remind_cancelled_or_quote(self):
        for st in (Order.Status.CANCELLED, Order.Status.QUOTED,
                   Order.Status.QUOTE_REJECTED):
            self._order(days_ago=10, status=st, email=f'{st}@lab.edu', po=f'PO-{st}')
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0,
                         '已取消/报价类不是"欠款"，催了会让客户莫名其妙')

    def test_reminds_shipped_and_invoiced(self):
        """货发了但钱没到 —— 正是最该催的时候。"""
        self._order(days_ago=5, status=Order.Status.SHIPPED,
                    email='a@lab.edu', po='PO-A')
        self._order(days_ago=6, status=Order.Status.INVOICED,
                    email='b@lab.edu', po='PO-B')
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 2)

    def test_only_reminds_once(self):
        """重复提醒会让客户把我们的邮件全丢垃圾箱。"""
        self._order(days_ago=5)
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 1)

        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 1, '第二次运行不得再发')

    def test_skips_order_without_email(self):
        self._order(days_ago=5, email='')
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0)
        # 但仍要"看得见"：不打标记，下次补上
        order = Order.objects.get()
        self.assertIsNone(order.unpaid_reminder_sent_at)

    def test_dry_run_sends_nothing(self):
        order = self._order(days_ago=5)
        call_command('remind_unpaid_orders', '--hours', '72',
                     '--dry-run', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0)
        order.refresh_from_db()
        self.assertIsNone(order.unpaid_reminder_sent_at)

    def test_threshold_is_configurable(self):
        self._order(days_ago=4)
        call_command('remind_unpaid_orders', '--hours', '240', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 0, '10 天阈值下，4 天的单不该催')
        call_command('remind_unpaid_orders', '--hours', '96', verbosity=0)
        self.assertEqual(EmailOutbox.objects.count(), 1, '4 天阈值下，4 天的单该催')


class ReminderTemplateTest(ReminderBase):
    def test_template_renders_without_placeholders_left(self):
        """模板里的占位符必须全被替换掉（漏一个会在客户信里出现 `{xxx}`）。"""
        self._order(days_ago=4)
        call_command('remind_unpaid_orders', '--hours', '72', verbosity=0)
        mail = EmailOutbox.objects.get()
        for field in (mail.subject, mail.body_text):
            self.assertNotIn('{order_no}', field)
            self.assertNotIn('{amount_due}', field)
            self.assertNotIn('{release_days}', field)

    def test_template_exists(self):
        self.assertTrue(
            EmailTemplate.objects.filter(key='order_unpaid_reminder').exists(),
            '模板缺失时 EmailService 会发出**空邮件**（subject/body 都是空串）')
