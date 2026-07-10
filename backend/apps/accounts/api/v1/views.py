from django.contrib.auth import authenticate
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView
from core.mixins import EnvelopeMixin
from core.permissions import LoginRateThrottle, IsProcurementOrAdmin

from apps.accounts.api.v1.serializers import (
    LoginSerializer,
    OrganizationSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
    AddressSerializer,
)
from apps.accounts.models import Organization, Address


class RegisterView(APIView):
    """POST /api/v1/auth/register — Register a new user and return auth token."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/v1/auth/login — Authenticate user and return auth token."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )

        if user is None:
            return Response(
                {'detail': 'Invalid username or password'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout — Delete the user's auth token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Token.DoesNotExist:
            pass
        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """GET /api/v1/auth/me — Return the current authenticated user's info."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileView(APIView):
    """PUT/PATCH /api/v1/auth/profile — Update current user's profile."""

    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    # Alias PATCH to PUT for partial updates
    patch = put


class OrganizationSearchView(APIView):
    """GET /api/v1/organizations — Search organizations by name."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        q = request.query_params.get('q', '')
        orgs = Organization.objects.filter(
            name__icontains=q, status='active'
        )[:10]
        serializer = OrganizationSerializer(orgs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizationCreateView(APIView):
    """POST /api/v1/organizations/create — Create a new organization."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save(created_by=request.user)
        # Auto-join the creator
        request.user.organization = org
        request.user.is_org_admin = True
        request.user.save()
        return Response(
            OrganizationSerializer(org).data, status=status.HTTP_201_CREATED
        )


class AddressPermission(BasePermission):
    """机构地址权限：
    - 读（list/retrieve）= 任意已登录用户，但仅可见本机构地址（见 queryset 过滤）。
    - 写（增/改/删）= 采购或管理员（机构地址由内部人员维护，PRD 节点4）。
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return IsProcurementOrAdmin().has_permission(request, view)


class AddressViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """机构地址 CRUD（节点4 — bill-to / ship-to）。

    - URL：/addresses/（list/create），/addresses/<pk>/（retrieve/update/destroy）。
    - 列表按 request.user 所属 organization 过滤。
    - 创建时 organization 由 request.user.organization 推入（前端不传）。
    - 统一信封 {success,data,meta}；关闭分页，列表直接返回数组。
    """
    serializer_class = AddressSerializer
    permission_classes = [AddressPermission]
    pagination_class = None
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        if not (user and user.is_authenticated):
            return Address.objects.none()
        # 按本机构过滤；内部人员无 organization 时返回空（避免越权看全量）。
        if user.organization_id:
            return Address.objects.filter(organization_id=user.organization_id)
        return Address.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        organization = request.user.organization
        if not organization:
            return self.error_response(
                'User has no organization', code='NO_ORGANIZATION', status_code=400
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=organization)
        return self.success_response(serializer.data, status_code=201)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self.success_response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return self.success_response(None, status_code=204)
