"""
Custom permission classes for the SciReagent project.
"""
from django.conf import settings
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.throttling import AnonRateThrottle


class IsAdminOrReadOnly(BasePermission):
    """
    Allow read-only access to anyone, but require admin for write operations.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsStaffUser(BasePermission):
    """统一工作台 API 权限 — 检查 is_staff。

    GET/POST/PUT/PATCH/DELETE 均要求 request.user.is_staff = True。
    与 IsAdminOrReadOnly 的区别：不放开匿名读。
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class LoginRateThrottle(AnonRateThrottle):
    """
    Rate limit for login endpoint: 5 requests per minute per IP.
    Prevents brute-force password attacks.

    Disabled when settings.DISABLE_THROTTLE is True (dev/test).
    """
    rate = '5/min'

    def allow_request(self, request, view):
        if getattr(settings, 'DISABLE_THROTTLE', False):
            return True
        return super().allow_request(request, view)
