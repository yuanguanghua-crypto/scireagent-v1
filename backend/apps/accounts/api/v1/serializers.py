from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.accounts.models import Organization

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

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
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
            org = Organization.objects.get(pk=org_id, status='active')
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
            'organization', 'organization_name', 'role', 'is_org_admin', 'is_superuser',
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
