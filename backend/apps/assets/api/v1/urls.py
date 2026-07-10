from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.assets.api.v1.views import PdfFileViewSet

router = DefaultRouter()
router.register('pdf-files', PdfFileViewSet, basename='pdf-file')

urlpatterns = [path('', include(router.urls))]
