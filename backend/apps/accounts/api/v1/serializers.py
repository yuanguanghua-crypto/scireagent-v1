from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.accounts.models import Organization, Address

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration with organization support."""

    ROLE_CHOICES = (
        ('researcher', 'Researcher'),
        ('procurement', 'Procurement'),
    )
    ORG_CHOICES = (
        ('solo', 'Solo'),
        ('join', 'Join'),
        ('create', 'Create'),
    )

    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=True)
    organization_choice = serializers.ChoiceField(choices=ORG_CHOICES, required=True)
    organization_id = serializers.IntegerField(required=False, allow_null=True)
    organization_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    organization_type = serializers.ChoiceField(
        choices=Organization.OrgType.choices,
        default=Organization.OrgType.ACADEMIC,
        required=False,
    )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}
            )

        # Enforce the configured AUTH_PASSWORD_VALIDATORS
        # (UserAttributeSimilarity / MinimumLength / CommonPassword /
        # NumericPassword). The settings define these validators, but
        # RegisterSerializer.create() calls create_user() directly, which
        # never invokes them — so without this explicit call, weak passwords
        # (too common, purely numeric, too similar to the username/email)
        # silently pass registration. We surface the messages under the
        # "password" field so the frontend error UI can show them.
        password = data['password']
        # Build a transient, unsaved user so the similarity validator can
        # compare against the username/email actually being registered.
        temp_user = User(
            username=data.get('username', ''),
            email=data.get('email', ''),
        )
        try:
            django_validate_password(password, user=temp_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        role = data.get('role')
        if role in ('editor', 'admin'):
            raise serializers.ValidationError(
                {"role": "Cannot register with role 'editor' or 'admin'"}
            )

        org_choice = data.get('organization_choice')

        if org_choice == 'join':
            org_id = data.get('organization_id')
            if not org_id:
                raise serializers.ValidationError(
                    {"organization_id": "organization_id is required when joining"}
                )
            try:
                Organization.objects.get(pk=org_id, status='active')
            except Organization.DoesNotExist:
                raise serializers.ValidationError(
                    {"organization_id": "Organization not found or not active"}
                )

        if org_choice == 'create':
            org_name = data.get('organization_name', '').strip()
            if not org_name:
                raise serializers.ValidationError(
                    {"organization_name": "organization_name is required when creating"}
                )

        return data

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password_confirm')
        org_choice = validated_data.pop('organization_choice')
        org_id = validated_data.pop('organization_id', None)
        org_name = validated_data.pop('organization_name', '').strip()
        org_type = validated_data.pop('organization_type', Organization.OrgType.ACADEMIC)

        username = validated_data['username']
        email = validated_data['email']
        role = validated_data['role']

        # Create user — explicitly unverified; the user must click the
        # verification link emailed by RegisterView before they can log in.
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            email_verified=False,
        )

        # Handle organization assignment
        if org_choice == 'solo':
            org = Organization.objects.create(
                name=f"{username}'s Lab",
                org_type=Organization.OrgType.INDIVIDUAL,
                created_by=user,
            )
            user.organization = org
            user.is_org_admin = True
            user.save()

        elif org_choice == 'join':
            # ★ P1 修复：此处不能裸 get。validate() 与 create() 是两次独立查询，
            # 两者之间机构可能被停用（管理员操作 / 批量任务），裸 get 会把
            # Organization.DoesNotExist 抛到视图外 ⇒ HTTP 500。该端点是
            # AllowAny（匿名可打），未捕获异常会变成可被匿名触发的 500。
            # 语义与 validate() 保持一致：解析不到「active」机构即字段级 400。
            org = Organization.objects.filter(
                pk=org_id, status=Organization.Status.ACTIVE).first()
            if org is None:
                raise serializers.ValidationError(
                    {"organization_id": "Organization not found or not active"}
                )
            user.organization = org
            user.is_org_admin = False
            user.save()

        elif org_choice == 'create':
            org = Organization.objects.create(
                name=org_name,
                org_type=org_type,
                created_by=user,
            )
            user.organization = org
            user.is_org_admin = True
            user.save()

        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for read-only user information."""

    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'date_joined',
            'organization', 'organization_name', 'role', 'is_org_admin', 'is_staff', 'is_superuser',
            'email_verified',
            'nickname', 'phone', 'department', 'title',
            'default_shipping_address', 'shipping_name', 'shipping_phone', 'shipping_email',
            'default_payment_method', 'default_po_number',
        ]
        read_only_fields = fields

    def get_organization_name(self, obj):
        if obj.organization:
            return obj.organization.name
        return None


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile fields."""

    class Meta:
        model = User
        fields = [
            'nickname', 'phone', 'department', 'title',
            'avatar_url', 'default_shipping_address', 'alternate_email',
            'shipping_name', 'shipping_phone', 'shipping_email',
            'default_payment_method', 'default_po_number',
        ]


class OrganizationSummarySerializer(serializers.ModelSerializer):
    """机构摘要 —— **仅用于匿名搜索选择器**（`GET /api/v1/organizations?q=`）。

    铁律（2026-10-21 F2）：只输出 5 个公开可辨识字段。
    **禁止**在此处加 `contact_*` / `address_*` / `city` / `state` / `postal_code`
    / `member_count` —— 该端点是 `AllowAny` + `authentication_classes=[]`，
    任何新增字段都会**直接匿名泄露**（contact_* 由任意登录用户经
    `OrganizationCreateView` 写入，等于客户名录+联系人裸奔）。
    回归：`apps/accounts/tests/test_org_search_privacy.py` 用
    `set(item.keys()) == {...}` 钉死键集合，加字段立刻红。
    """

    class Meta:
        model = Organization
        fields = ['id', 'name', 'short_name', 'org_type', 'country']
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for organization listing and detail."""

    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'short_name', 'org_type', 'description', 'website',
            'contact_email', 'contact_phone', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'approval_required',
            'status', 'member_count', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'member_count', 'created_at']

    def get_member_count(self, obj):
        return obj.members.count()


class AddressSerializer(serializers.ModelSerializer):
    """机构地址（billing/shipping）序列化器 — 字段显式声明（禁 __all__）。

    organization_id 为只读：归属由 View 依据 request.user.organization 推入，
    前端地址簿不传 organization，避免越权写入其他机构。
    """

    class Meta:
        model = Address
        fields = [
            'id', 'organization_id', 'type', 'is_default',
            'attention', 'line1', 'line2', 'city', 'state',
            'postal_code', 'country', 'phone',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'organization_id', 'created_at', 'updated_at']
