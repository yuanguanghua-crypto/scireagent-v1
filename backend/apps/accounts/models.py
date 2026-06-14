from django.contrib.auth.models import AbstractUser
from django.db import models


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

    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username
