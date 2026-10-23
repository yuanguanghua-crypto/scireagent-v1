"""运营台「用户与角色」—— 只开三条写操作，刻意不做到底。

## 为什么这么窄

用户管理是权限边界，开错一个口子就是提权或客户数据事故。本项目已经立过铁律：
注册一律落 `researcher`，`role` 字段"接受不采信"。所以这里**只允许**：

1. 改 `role`（必须在枚举内）
2. 启停账号（`is_active`）
3. 手动验证邮箱 / 触发重置密码邮件

**明确不做（写进代码，不只是文档）**：
- ❌ 改密码明文 —— 只能触发重置邮件，让人自己设
- ❌ 改 `is_staff` / `is_superuser` —— 那是提权，必须走 Django admin + 双人确认
- ❌ 删除用户 —— 有订单/线索关联，删了就是数据事故
- ❌ 改自己的 role 或 is_active —— 防自锁（把自己降权/禁用后再也进不来）

## 为什么权限用 IsAdmin 而非 IsProcurementOrAdmin

`procurement` 能看订单、能报价，但**不该能改别人的角色**。改角色是管理员动作。
"""
import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsAdmin

from apps.notifications.services import EmailService

logger = logging.getLogger(__name__)
User = get_user_model()


# ── 序列化器 ────────────────────────────────────────────────────────────

class OpsUserRowSerializer(serializers.ModelSerializer):
    """列表行 —— 只给判断"这个人是什么状态"所需的信息，不含密码/权限位细节。"""

    organization_name = serializers.CharField(
        source='organization.name', read_only=True, default=''
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'is_active', 'email_verified',
            'is_staff', 'date_joined', 'last_login', 'organization_name',
        ]
        read_only_fields = fields


class OpsUserPatchSerializer(serializers.Serializer):
    """白名单式更新 —— 只认这两个字段，其它一律 400（不静默忽略）。

    静默忽略是最危险的：调用方以为改了 is_staff 成功了，实际没改，
    下次排查会怀疑人生。这里明确报错。
    """

    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Nothing to update: provide role or is_active.')
        unknown = set(self.initial_data.keys()) - {'role', 'is_active'}
        if unknown:
            raise serializers.ValidationError({
                'unsupported_fields': (
                    f'不允许修改: {sorted(unknown)}。'
                    '可改的只有 role / is_active；'
                    'is_staff / is_superuser / password 必须走 Django admin。'
                )
            })
        return attrs


# ── 视图 ────────────────────────────────────────────────────────────────

class OpsUserListView(EnvelopeMixin, ListAPIView):
    """GET /api/v1/ops/users/ — 用户列表，支持搜索与筛选。

    参数：search（用户名/邮箱/机构名）、role、is_active、email_verified、page_size
    """

    permission_classes = [IsAdmin]
    serializer_class = OpsUserRowSerializer

    def get_queryset(self):
        qs = User.objects.select_related('organization').order_by('-date_joined')
        p = self.request.query_params

        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(organization__name__icontains=search)
            )
        if p.get('role'):
            qs = qs.filter(role=p['role'])
        for flag in ('is_active', 'email_verified', 'is_staff'):
            v = p.get(flag)
            if v in ('true', 'false'):
                qs = qs.filter(**{flag: v == 'true'})
        return qs

    def list(self, request, *args, **kwargs):
        try:
            page_size = min(int(request.query_params.get('page_size', 100)), 500)
        except (TypeError, ValueError):
            page_size = 100
        qs = self.get_queryset()
        total = qs.count()
        rows = self.get_serializer(qs[:page_size], many=True).data
        return self.success_response(
            rows,
            meta={'pagination': {'count': total, 'page': 1, 'page_size': page_size}},
        )


class OpsUserDetailView(EnvelopeMixin, APIView):
    """PATCH /api/v1/ops/users/:id/ — 改 role 或启停。

    三条拒绝规则（都有实际后果，不是防御性编程）：
    - 改自己 ⇒ 400（防自锁：把自己降权后立刻失去这个页面）
    - 停用自己 ⇒ 400
    - 把最后一个 admin 降级 ⇒ 400（否则没人能再进后台）
    """

    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        ser = OpsUserPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if user.pk == request.user.pk:
            return Response(
                {'detail': '不能修改自己的角色或启停状态（会导致自己失去访问权限）。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_role = data.get('role', user.role)
        new_active = data.get('is_active', user.is_active)

        # 最后一个 admin 不能再被降级/停用 —— 否则整套运维入口永久锁死
        if user.is_staff or user.role == 'admin':
            losing_admin = (
                (new_role != 'admin' and not user.is_staff)
                or not new_active
            )
            if losing_admin:
                others = User.objects.filter(
                    Q(role='admin') | Q(is_staff=True)
                ).exclude(pk=user.pk).count()
                if others == 0:
                    return Response(
                        {'detail': '这是最后一个管理员账号，不能降级或停用。'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        changed = []
        if 'role' in data and data['role'] != user.role:
            user.role = data['role']
            changed.append('role')
        if 'is_active' in data and data['is_active'] != user.is_active:
            user.is_active = data['is_active']
            changed.append('is_active')

        if changed:
            user.save(update_fields=changed)
            logger.info(
                '[ops] 用户 %s 的属性被 %s 修改: %s',
                user.pk, request.user.pk, changed,
            )
            # 停用后立即失效其登录凭证 —— 否则旧 token 还能继续用
            if 'is_active' in changed and not user.is_active:
                from rest_framework.authtoken.models import Token
                Token.objects.filter(user=user).delete()

        return self.success_response(self._row(user))

    @staticmethod
    def _row(user):
        return OpsUserRowSerializer(user).data


class OpsUserVerifyEmailView(EnvelopeMixin, APIView):
    """POST /api/v1/ops/users/:id/verify-email/ — 手动置为已验证。

    用途：邮件通道出故障期间注册的账号（如本项目的 tracy / tracylqq），
    或客户明确说收不到信但又急着用。**这只是补状态，不是绕过验证机制** —— 
    真实通道恢复后，新注册用户仍然要走邮箱验证。
    """

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.accounts.models import EmailVerification
        already = user.email_verified
        if not already:
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        # 顺手清掉待验证令牌，避免用户以后点了旧链接又被翻回奇怪状态
        EmailVerification.objects.filter(user=user).delete()

        logger.info('[ops] 用户 %s 邮箱被 %s 手动置为已验证', user.pk, request.user.pk)
        return self.success_response({
            'id': user.pk,
            'email_verified': True,
            'already_verified': already,
        })


class OpsUserSendResetView(EnvelopeMixin, APIView):
    """POST /api/v1/ops/users/:id/send-password-reset/ — 触发一封重置邮件。

    ★ 不提供"直接改密码"：密码只能由本人通过邮件链接设置。
      管理员能设密码 = 能冒充用户，审计上不可接受。
    """

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not user.email:
            return Response(
                {'detail': '该账号没有邮箱，无法发送重置链接。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {'detail': '账号已停用，重置密码无意义。请先启用。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.conf import settings
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import PasswordReset
        import uuid

        expires_hours = getattr(settings, 'PASSWORD_RESET_EXPIRE_HOURS', 1)
        reset, _ = PasswordReset.objects.update_or_create(
            user=user,
            defaults={
                'token': uuid.uuid4(),
                'expires_at': timezone.now() + timedelta(hours=expires_hours),
                'requested_ip': request.META.get('REMOTE_ADDR'),
            },
        )
        reset_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={reset.token}"

        mailed = False
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
            mailed = True
        except Exception:
            logger.exception('[ops] 为用户 %s 触发重置邮件失败', user.pk)

        return self.success_response({
            'id': user.pk,
            'queued': mailed,
            'expires_hours': expires_hours,
            # 邮件没入队也把链接给出来，管理员可以人工转达（不要写进日志）
            'reset_url': reset_url if not mailed else None,
        })
