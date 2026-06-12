from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.v1.serializers import (
    LoginSerializer,
    OrganizationSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from apps.accounts.models import Organization


class RegisterView(APIView):
    """POST /api/v1/auth/register — Register a new user and return auth token."""

    permission_classes = [AllowAny]
    authentication_classes = []

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
