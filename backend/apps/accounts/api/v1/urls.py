from django.urls import path

from apps.accounts.api.v1 import views
from apps.accounts.api.v1 import ops_users

urlpatterns = [
    path('auth/register', views.RegisterView.as_view(), name='auth-register'),
    path('auth/login', views.LoginView.as_view(), name='auth-login'),
    path('auth/logout', views.LogoutView.as_view(), name='auth-logout'),
    # ── Email verification (register → verify → login) ──
    path('auth/verify-email', views.VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/resend-verification', views.ResendVerificationView.as_view(), name='auth-resend-verification'),
    # ── 密码重置（两次调用：申请 → 用 token 设置新密码）──
    path('auth/request-password-reset', views.PasswordResetRequestView.as_view(),
         name='auth-request-password-reset'),
    path('auth/reset-password', views.PasswordResetConfirmView.as_view(),
         name='auth-reset-password'),
    # ── 运营台「用户与角色」（IsAdmin）—— 只开改 role / 启停 / 验证邮箱 / 触发重置 ──
    path('ops/users/', ops_users.OpsUserListView.as_view(), name='ops-user-list'),
    path('ops/users/<int:pk>/', ops_users.OpsUserDetailView.as_view(), name='ops-user-detail'),
    path('ops/users/<int:pk>/verify-email/', ops_users.OpsUserVerifyEmailView.as_view(),
         name='ops-user-verify-email'),
    path('ops/users/<int:pk>/send-password-reset/',
         ops_users.OpsUserSendResetView.as_view(), name='ops-user-send-reset'),
    path('auth/me', views.MeView.as_view(), name='auth-me'),
    path('auth/profile', views.ProfileView.as_view(), name='auth-profile'),
    path('organizations', views.OrganizationSearchView.as_view(), name='org-search'),
    # 运维台「机构管理」全量列表（采购/管理员；匿名搜索仍走上面那条收紧的端点）
    path(
        'organizations/manage/',
        views.OrganizationManageListView.as_view(),
        name='org-manage-list',
    ),
    path(
        'organizations/create',
        views.OrganizationCreateView.as_view(),
        name='org-create',
    ),
    # ── Address CRUD (PO Portal 节点4) ──
    path('addresses/', views.AddressViewSet.as_view(
        {'get': 'list', 'post': 'create'}), name='address-list'),
    path('addresses/<int:pk>/', views.AddressViewSet.as_view(
        {'get': 'retrieve', 'put': 'update',
         'patch': 'partial_update', 'delete': 'destroy'}), name='address-detail'),
]
