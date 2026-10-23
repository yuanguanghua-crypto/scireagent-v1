import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjValidationError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.mixins import EnvelopeMixin
from core.permissions import LoginRateThrottle, IsProcurementOrAdmin

from apps.notifications.services import EmailService, email_delivery_is_unavailable

from apps.accounts.api.v1.serializers import (
    LoginSerializer,
    OrganizationSerializer,
    OrganizationSummarySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
    AddressSerializer,
)
from apps.accounts.email import send_verification_email
from apps.accounts.models import (
    Address, EmailVerification, Organization, PasswordReset, User,
)

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    """POST /api/v1/auth/register — Register a new user and email a verification link.

    No auth token is minted here. The account starts unverified
    (``email_verified=False``) and cannot log in until the user clicks the
    verification link (see :class:`VerifyEmailView`, which issues the token on
    success).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()  # email_verified defaults to False

        # ⚠️ 邮件通道不可达时，不要一边说「请去邮箱验证」一边又让人永远等不到邮件。
        #    此时直接把账号标为已验证，并在响应里如实告知「可以直接登录」，
        #    避免用户去收一封永远不会来的信（2026-10-23 生产事故）。
        mail_ok = not email_delivery_is_unavailable()
        if mail_ok:
            send_verification_email(user)
            detail = (
                'Registration successful. We have sent a verification link '
                'to your email address — please verify before signing in.'
            )
            verified = False
        else:
            logger.warning(
                '[auth] EMAIL_BACKEND=%s 不可投递，注册时直接放行 username=%s id=%s'
                '（未发送验证邮件）。请尽快配置真实发信通道。',
                getattr(settings, 'EMAIL_BACKEND', ''),
                user.username,
                user.pk,
            )
            user.email_verified = True
            user.save(update_fields=['email_verified'])
            detail = (
                'Registration successful. Email verification is currently '
                'unavailable, so your account is ready — you can sign in now.'
            )
            verified = True

        return Response(
            {
                'detail': detail,
                'email': user.email,
                'email_verified': verified,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/v1/auth/login — Authenticate user and return auth token.

    Hard-blocks accounts whose email is not yet verified (HTTP 403) so an
    unverified registration cannot be used until the user confirms their email.
    """

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

        # Hard-block unverified emails: the account cannot be used until the
        # user clicks the verification link emailed at registration.
        #
        # ⚠️ 例外：当邮件通道根本投递不到用户时（console/locmem 等），
        #    这道硬阻断会把人永久锁死 —— 注册成功、邮件收不到、登录 403、
        #    无任何自助恢复路径。2026-10-23 生产实测确实发生了（2 个僵尸账号）。
        #    此时降级放行并自动标记已验证，同时打 warning 让问题可见；
        #    一旦配置真实发信通道，这个分支自动失效，严格验证恢复。
        if not user.email_verified:
            if email_delivery_is_unavailable():
                logger.warning(
                    '[auth] EMAIL_BACKEND=%s 无法投递验证邮件，降级放行未验证账号 '
                    'username=%s id=%s 并自动置 email_verified=True。'
                    '请尽快配置真实发信通道，否则邮箱验证形同虚设。',
                    getattr(settings, 'EMAIL_BACKEND', ''),
                    user.username,
                    user.pk,
                )
                user.email_verified = True
                user.save(update_fields=['email_verified'])
            else:
                return Response(
                    {
                        'detail': (
                            'Email address is not verified. Please check your inbox '
                            'for the verification link (or request a new one from '
                            'the sign-in page).'
                        ),
                        'email_verified': False,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class VerifyEmailView(APIView):
    """GET /api/v1/auth/verify-email?token=<uuid> — Verify a user's email.

    On success the account is marked verified and a fresh auth token is issued
    (the link effectively logs the user in). The consumed token is deleted.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raw_token = request.query_params.get('token')
        if not raw_token:
            return Response(
                {'detail': 'Missing verification token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            verification = EmailVerification.objects.get(token=raw_token)
        except (EmailVerification.DoesNotExist, ValueError, DjValidationError):
            # ★ 2026-10-22 修：`token` 是 UUIDField，畸形字符串（如 `probe-invalid-token`）
            #   抛的是 **django.core.exceptions.ValidationError**，不是 ValueError。
            #   此前只捕 ValueError ⇒ 未捕获 → 500 + HTML 错误页（实测）。
            #   现在统一返回 400 + 「链接无效」，与"格式正确但不存在"同一句口径。
            return Response(
                {'detail': 'Invalid or expired verification token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if verification.is_expired():
            verification.delete()
            return Response(
                {'detail': 'Verification link has expired. Please request a new one.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = verification.user
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        verification.delete()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    """POST /api/v1/auth/resend-verification — Re-issue a verification email.

    Rate-limited like login. Responds identically whether or not the email
    exists / is already verified to avoid account enumeration.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response(
                {'detail': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(email=email).first()
        if user and not user.email_verified:
            send_verification_email(user)
        # Always return the same generic message (no enumeration).
        return Response(
            {
                'detail': (
                    'If an unverified account exists for that email, '
                    'a verification link has been sent.'
                )
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
    """GET /api/v1/organizations — Search organizations by name.

    ★ 2026-10-21 F2（P1 匿名泄露 PII）：本端点是 `AllowAny` +
      `authentication_classes = []`（公开注册页的机构选择器），此前用
      `OrganizationSerializer` 直出 ⇒ 匿名者可拿到 contact_email / contact_phone /
      完整地址 / member_count（客户名录 + 联系人 + 规模），且这些字段由任意登录用户
      经 `OrganizationCreateView` 写入。
      改为 `OrganizationSummarySerializer`（仅 id/name/short_name/org_type/country）。
    ★ 同时给 `q` 加长度下限：此前不传 q 时 `q=''` ⇒ `name__icontains=''`
      命中全部 active 机构，一次吐 10 条全表。现要求去空白后 ≥ 2 字符，
      否则返回空列表（不是全表）。
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    MIN_QUERY_LEN = 2

    def get(self, request):
        q = (request.query_params.get('q', '') or '').strip()
        if len(q) < self.MIN_QUERY_LEN:
            # 空/过短查询一律空列表：既防全表泄露，也避免 1 字符把客户名录捞出来
            return Response([], status=status.HTTP_200_OK)
        orgs = Organization.objects.filter(
            name__icontains=q, status='active'
        )[:10]
        serializer = OrganizationSummarySerializer(orgs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizationManageListView(EnvelopeMixin, APIView):
    """GET /api/v1/organizations/manage/ — 运维台「机构管理」的全量分页列表。

    ★ 2026-10-21 补 F2 的功能回退：`OrganizationSearchView` 收紧为
      「匿名 + q 至少 2 字符 + 仅 5 个摘要素」之后，`/ops/po/organizations`
      （`frontend/src/views/admin/PoOrgManagement.vue:16`）拿 `page_size: 100`
      **不带 q** 去取左栏列表，于是恒得空数组 —— 左栏 Organizations 表格空白。
      ⇒ 不能靠"放开匿名搜索"来修（那等于把刚堵的 PII 泄露洞重新打开），
      而是**另开一个受权限保护的管理端点**：匿名搜索保持收紧，管理页面走这里。

    为什么权限是 `IsProcurementOrAdmin` 而不是 `IsStaffUser`：
      该页面属 PO 运维域，本仓库同类端点（`AdminOrderListView`、`ArAgingView`）
      一律用 `IsProcurementOrAdmin`；改成 `IsStaffUser` 会把 `procurement`
      角色（非 staff）挡在门外，直接打断他们的日常流程。

    为什么这里可以用完整 `OrganizationSerializer`（含 contact_* / 地址 / member_count）：
      调用方已限定为内部采购/管理员，这些正是机构管理需要看的字段；
      而匿名面走的是 `OrganizationSummarySerializer`。两条路径的字段面**刻意不同**，
      改动任一序列化器前请先看 F2 的测试（`test_org_search_privacy.py` 用
      `set(item.keys()) == {...}` 钉死了匿名面的字段集）。
    """

    permission_classes = [IsProcurementOrAdmin]

    DEFAULT_PAGE_SIZE = 100
    MAX_PAGE_SIZE = 500

    def get(self, request):
        try:
            page_size = int(request.query_params.get('page_size') or self.DEFAULT_PAGE_SIZE)
        except (TypeError, ValueError):
            page_size = self.DEFAULT_PAGE_SIZE
        # 上下夹紧：防止 page_size=0（返回空）或超大值（一次拉全表）
        page_size = max(1, min(page_size, self.MAX_PAGE_SIZE))

        qs = Organization.objects.filter(status='active').order_by('name')
        total = qs.count()
        serializer = OrganizationSerializer(qs[:page_size], many=True)
        return self.success_response(
            serializer.data,
            meta={'pagination': {'count': total, 'page': 1, 'page_size': page_size}},
        )


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
    - 写（增/改/删）= **任意已登录用户**（2026-10-21 从「采购或管理员」放开）。

    ★ 为什么要放开：`/po/addresses`（`router/index.js:205`）是**客户侧**页面，
      只要求登录。而注册已不再允许自选 `procurement`（见 serializers.py 的
      `role = User.Role.RESEARCHER`）⇒ 若写权限仍绑 `procurement/admin`，
      客户的采购经理就**能看不能改**自己的地址簿，直接 403，打断真实业务。

    ★ 为什么放开是安全的：本 ViewSet 的行级隔离在**三处**，权限只是最外层：
        ① `get_queryset()` 按 `request.user.organization_id` 收窄，无机构返回 `.none()`
        ② `create()` 强制 `serializer.save(organization=request.user.organization)`
           —— 客户端传什么 organization 都不算（`organization_id` 在序列化器里 read_only）
        ③ `update`/`destroy` 走 `self.get_object()` ⇒ 必然经过 ①
      所以"已登录可写"的实际语义是「**只能改自己机构那一小撮行**」。
      读权限本来就是"任意已登录用户 + 本机构过滤"，写权限与读权限对齐，
      增量风险仅是"同机构成员可改彼此的地址"——本来就是机构内协作。

    ★ 依赖：这条放开的**前提**是「不能自助加入任意机构」已堵住
      （`RegisterSerializer._check_join_domain`）。否则攻击者先 join 别人的机构、
      再改该机构的收货地址，等于把洞放大。两个改动必须同批上线。

    无机构用户不在这里拦：让 `create()` 返回结构化的 400 `NO_ORGANIZATION`
    （比 403 更能说明原因）；`update`/`destroy` 自然因 `get_queryset().none()` 而 404。
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated)


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


class PasswordResetRequestView(APIView):
    """POST /api/v1/auth/request-password-reset — 申请密码重置链接。

    ★ 安全取舍（改动前务必读）：**无论邮箱是否已注册，响应完全一致**。
      否则这个匿名端点就成了用户枚举器 —— 攻击者可批量试探哪些邮箱有账号。
      同理，邮件入队失败也必须返回同样的响应，不能透出"这个邮箱存在"。
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    _ALWAYS = (
        'If that email address is registered, a reset link is on its way. '
        'Check your inbox (and spam folder).'
    )

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data['email'].strip()

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            logger.info('[auth] 密码重置请求：邮箱未注册或已停用，按惯例静默忽略')
            return Response({'detail': self._ALWAYS}, status=status.HTTP_200_OK)

        expires_hours = getattr(settings, 'PASSWORD_RESET_EXPIRE_HOURS', 1)
        # OneToOne + update_or_create ⇒ 重复申请会让旧 token 立即失效
        reset, _ = PasswordReset.objects.update_or_create(
            user=user,
            defaults={
                'token': uuid.uuid4(),
                'expires_at': timezone.now() + timedelta(hours=expires_hours),
                'requested_ip': (
                    request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                    or request.META.get('REMOTE_ADDR')
                ),
            },
        )
        reset_url = (
            f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={reset.token}"
        )

        try:
            EmailService.enqueue(
                'password_reset',
                to=[user.email],
                ctx={
                    'username': user.username,
                    'reset_url': reset_url,
                    'expire_hours': expires_hours,
                },
            )
        except Exception:
            # 不能让调用方从异常/耗时差异推断邮箱是否存在
            logger.exception('[auth] 密码重置邮件入队失败 user_id=%s', user.pk)

        return Response({'detail': self._ALWAYS}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """POST /api/v1/auth/reset-password — 用 token 设置新密码。

    三条硬性要求：
    1. 畸形 token 必须 400，不能 500（`UUIDField` 抛的是 `DjValidationError`，不是 ValueError）
    2. 用完即删（一次性）
    3. 重置后**吊销该用户全部 token**，否则旧会话仍然有效
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        raw_token = ser.validated_data['token'].strip()
        new_password = ser.validated_data['new_password']

        invalid = Response(
            {'detail': 'This reset link is invalid or has expired. Please request a new one.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

        try:
            reset = PasswordReset.objects.select_related('user').get(token=raw_token)
        except (PasswordReset.DoesNotExist, DjValidationError, ValueError):
            return invalid

        if reset.is_expired() or not reset.user.is_active:
            reset.delete()
            return invalid

        user = reset.user
        user.set_password(new_password)
        user.save(update_fields=['password'])
        reset.delete()
        Token.objects.filter(user=user).delete()

        logger.info('[auth] 密码已重置 user_id=%s，已吊销全部 token', user.pk)
        return Response(
            {'detail': 'Password updated. Please sign in with your new password.'},
            status=status.HTTP_200_OK,
        )
