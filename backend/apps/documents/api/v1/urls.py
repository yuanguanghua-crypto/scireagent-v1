from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BatchViewSet, CoaViewSet, SdsRevisionViewSet, PubChemCacheViewSet

router = DefaultRouter()
router.register('batches', BatchViewSet, basename='batch')
router.register('coas', CoaViewSet, basename='coa')
router.register('sds-revisions', SdsRevisionViewSet, basename='sds-revision')
router.register('pubchem-cache', PubChemCacheViewSet, basename='pubchem-cache')

urlpatterns = [
    path('', include(router.urls)),
]
