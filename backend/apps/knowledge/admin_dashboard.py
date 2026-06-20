"""
Researcher Dashboard — admin home page.

Shows quick actions, pending items, and recent updates.
"""
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.conf import settings

from apps.commerce.models import Product
from apps.bridges.models import ProductMethod

logger = logging.getLogger(__name__)


@staff_member_required
def dashboard_view(request):
    """Researcher dashboard with quick actions and status overview."""

    # Recent products (last 5 updated)
    recent_products = list(
        Product.objects.order_by('-updated_at', '-id')[:5]
        .values('id', 'name', 'catalog_no', 'status')
    )

    # Products without method association
    products_without_method = Product.objects.filter(
        status='active'
    ).exclude(
        id__in=ProductMethod.objects.values('product_id')
    ).count()

    # Counts
    total_products = Product.objects.filter(status='active').count()
    products_with_cas = Product.objects.filter(status='active').exclude(cas='').count()
    pubchem_coverage = round(products_with_cas / total_products * 100, 1) if total_products else 0.0

    context = {
        'title': 'Dashboard',
        'site_title': getattr(settings, 'UNFOLD', {}).get('SITE_TITLE', 'Admin'),
        'site_header': getattr(settings, 'UNFOLD', {}).get('SITE_HEADER', 'Admin'),
        'recent_products': recent_products,
        'products_without_method': products_without_method,
        'total_products': total_products,
        'products_with_cas': products_with_cas,
        'pubchem_coverage': pubchem_coverage,
    }

    return render(request, 'admin/dashboard.html', context)
