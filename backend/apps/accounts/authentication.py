"""Custom token authentication that reads the token from the X-Auth-Token
header instead of the standard ``Authorization: Token`` header.

Why: the site is protected by nginx HTTP Basic Auth, which consumes the
``Authorization: Basic`` header. The SPA also sends a DRF auth token, and
DRF's built-in ``TokenAuthentication`` uses the *same* ``Authorization``
header. When the browser has cached Basic credentials (from the nginx
popup) and the SPA sets ``Authorization: Token <token>``, the two collide
and nginx rejects the request (401). Routing the app token through a
separate ``X-Auth-Token`` header avoids the clash. ``Authorization: Token``
is still accepted as a fallback for API clients.
"""
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


class XAuthTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        token = request.META.get('HTTP_X_AUTH_TOKEN')
        if token:
            try:
                token_obj = Token.objects.select_related('user').get(key=token)
            except Token.DoesNotExist:
                raise AuthenticationFailed('Invalid or expired token.')
            return (token_obj.user, token_obj)
        # Fall back to the standard Authorization: Token header.
        return super().authenticate(request)
