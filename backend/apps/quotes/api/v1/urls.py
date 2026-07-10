from django.urls import path
from apps.quotes.api.v1.views import QuoteRequestCreateView, QuoteRequestDetailView

urlpatterns = [
    path('quote-requests/', QuoteRequestCreateView.as_view(), name='quote-request-create'),
    path('quote-requests/<int:pk>/', QuoteRequestDetailView.as_view(), name='quote-request-detail'),
]
