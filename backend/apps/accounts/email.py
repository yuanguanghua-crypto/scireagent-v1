"""Email helpers for the accounts app (registration email verification).

Sends the verification link to a newly registered (or resend-requesting) user.
The email backend itself is chosen in config/settings/base.py: Mailgun over
HTTP API when ANYMAIL_MAILGUN_API_KEY is set, otherwise the console backend
(which prints the link to the backend logs — zero credentials required).
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import EmailVerification


def send_verification_email(user):
    """(Re)issue a verification token for ``user`` and email the verify link.

    A fresh token + expiry are always written, so a resend invalidates any
    previously issued link. Returns the :class:`EmailVerification` instance.
    """
    expires_at = timezone.now() + timedelta(
        hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
    )
    verification, _ = EmailVerification.objects.update_or_create(
        user=user,
        defaults={'token': uuid.uuid4(), 'expires_at': expires_at},
    )

    link = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify-email"
        f"?token={verification.token}"
    )
    subject = 'Verify your SciReAgent account email'
    message = (
        f"Hi {user.username},\n\n"
        f"Thanks for registering with SciReAgent. Please verify your email "
        f"address by opening the link below:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.EMAIL_VERIFICATION_EXPIRE_HOURS} "
        f"hour(s). If you did not create this account, you can ignore this "
        f"email.\n\n"
        f"The SciReAgent Team"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return verification
