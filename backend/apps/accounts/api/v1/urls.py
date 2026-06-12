from django.urls import path

from apps.accounts.api.v1 import views

urlpatterns = [
    path('auth/register', views.RegisterView.as_view(), name='auth-register'),
    path('auth/login', views.LoginView.as_view(), name='auth-login'),
    path('auth/logout', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/me', views.MeView.as_view(), name='auth-me'),
    path('auth/profile', views.ProfileView.as_view(), name='auth-profile'),
    path('organizations', views.OrganizationSearchView.as_view(), name='org-search'),
    path(
        'organizations/create',
        views.OrganizationCreateView.as_view(),
        name='org-create',
    ),
]
