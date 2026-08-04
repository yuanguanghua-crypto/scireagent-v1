import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class Organization(models.Model):
    """Organization model for grouping users."""

    class OrgType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        ACADEMIC = 'academic', 'Academic'
        ENTERPRISE = 'enterprise', 'Enterprise'
        GOVERNMENT = 'government', 'Government'
        HOSPITAL = 'hospital', 'Hospital'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        PENDING = 'pending', 'Pending'

    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True, default='')
    org_type = models.CharField(
        max_length=20, choices=OrgType.choices, default=OrgType.INDIVIDUAL
    )
    description = models.TextField(blank=True, default='')
    website = models.URLField(blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')
    address_line1 = models.CharField(max_length=200, blank=True, default='')
    address_line2 = models.CharField(max_length=200, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, default='China')
    approval_required = models.BooleanField(default=True)
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_organizations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Extended user model for SciReagent platform."""

    class Role(models.TextChoices):
        RESEARCHER = 'researcher', 'Researcher'
        PROCUREMENT = 'procurement', 'Procurement'
        EDITOR = 'editor', 'Editor'
        ADMIN = 'admin', 'Admin'

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.RESEARCHER
    )
    is_org_admin = models.BooleanField(default=False)
    nickname = models.CharField(max_length=50, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    title = models.CharField(max_length=100, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    default_shipping_address = models.TextField(blank=True, default='')
    shipping_name = models.CharField(max_length=200, blank=True, default='', verbose_name='收件人')
    shipping_phone = models.CharField(max_length=30, blank=True, default='', verbose_name='收件电话')
    shipping_email = models.EmailField(blank=True, default='', verbose_name='收件邮箱')
    default_payment_method = models.CharField(max_length=20, blank=True, default='purchase_order', verbose_name='默认付款方式')
    default_po_number = models.CharField(max_length=100, blank=True, default='', verbose_name='默认PO号')
    alternate_email = models.EmailField(blank=True, default='')
    email_verified = models.BooleanField(
        default=False, verbose_name='邮箱已验证',
        help_text='注册后须点击验证邮件中的链接置为 True，方可登录。',
    )

    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username


class EmailVerification(models.Model):
    """邮箱验证令牌 — 一对一挂到 User。注册后签发；用户点击验证链接后删除并置
    User.email_verified=True。每次（重发）重新生成 token，旧的立即失效。"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='email_verification'
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'email_verification'
        verbose_name = '邮箱验证令牌'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'verification for user {self.user_id}'

    def is_expired(self):
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        # Defensive default: if created without an explicit expiry, use the
        # configured lifetime so a token is never left permanently valid.
        if not self.expires_at:
            from django.conf import settings
            self.expires_at = timezone.now() + timedelta(
                hours=getattr(settings, 'EMAIL_VERIFICATION_EXPIRE_HOURS', 24)
            )
        super().save(*args, **kwargs)


class Address(TimeStampedModel):
    """机构地址 — 一对多挂在 Organization，billing/shipping 用途标记。"""

    class Type(models.TextChoices):
        BILLING = 'billing', 'Billing'
        SHIPPING = 'shipping', 'Shipping'
        OTHER = 'other', 'Other'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        related_name='addresses', verbose_name='机构'
    )
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.SHIPPING
    )
    is_default = models.BooleanField(default=False, verbose_name='默认地址')
    attention = models.CharField(max_length=200, blank=True, default='', verbose_name='收件人/部门')
    line1 = models.CharField(max_length=200, blank=True, default='', verbose_name='地址行1')
    line2 = models.CharField(max_length=200, blank=True, default='', verbose_name='地址行2')
    city = models.CharField(max_length=100, blank=True, default='', verbose_name='城市')
    state = models.CharField(max_length=100, blank=True, default='', verbose_name='州/省')
    postal_code = models.CharField(max_length=20, blank=True, default='', verbose_name='邮编')
    country = models.CharField(max_length=100, default='US', verbose_name='国家')
    phone = models.CharField(max_length=30, blank=True, default='', verbose_name='电话')

    class Meta:
        db_table = 'address'
        verbose_name = '地址'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'type'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_type',
            ),
        ]

    def __str__(self):
        return f'{self.get_type_display()} @ {self.organization_id}: {self.line1}'
