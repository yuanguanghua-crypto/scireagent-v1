"""AI Tool API Views

DRF views exposing the three AI tools to the admin UI:
- ProductValidateView: PubChem + BioProCorpus validation
- ProductRecommendProtocolsView: BioProCorpus protocol recommendations
- ProductRecommendLiteratureView: PubMed literature recommendations
- BatchValidateView: batch product validation
- BatchRecommendLiteratureView: batch literature recommendations
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.commerce.services.validators.product_validator import ProductValidator
from apps.knowledge.services.protocol_recommender import ProtocolRecommender
from apps.knowledge.services.literature_recommender import LiteratureRecommender

logger = logging.getLogger(__name__)


# ── Serialization helper ──────────────────────────────────────────────

def serialize_validation_report(report, product):
    """Convert ValidationReport dataclass + Product info to JSON-safe dict."""
    return {
        "status": report.status,
        "product": {
            "id": product.id,
            "name": product.name,
            "cas": product.cas or "",
            "smiles": product.smiles or "",
        },
        "pubchem": {
            "match": report.pubchem_match,
            "cid": report.pubchem_cid,
            "result": report.pubchem_result,
        },
        "mismatches": report.mismatches,
        "bioprocorpus": {
            "match_count": len(report.matched_protocols),
            "result": report.bioprocorpus_result,
        },
        "matched_protocols": report.matched_protocols,
        "overall_match": report.overall_match,
        "timestamp": report.timestamp,
    }


# ── Single-Product Views ──────────────────────────────────────────────

class ProductValidateView(EnvelopeMixin, APIView):
    """POST /api/v1/products/<pk>/validate/

    Validate a product's structural data against PubChem and BioProCorpus.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        logger.info(f"Running ProductValidator for product {pk}: {product.name}")
        validator = ProductValidator()
        report = validator.validate(product)
        return self.success_response(serialize_validation_report(report, product))


class ProductRecommendProtocolsView(EnvelopeMixin, APIView):
    """POST /api/v1/products/<pk>/recommend-protocols/

    Recommend experimental protocols from BioProCorpus based on product name.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        top_k = int(request.data.get("top_k", 5)) if request.data else 5
        logger.info(f"Running ProtocolRecommender for product {pk}: {product.name}")
        recommender = ProtocolRecommender()
        recommendations = recommender.recommend(product.name, top_k=top_k)
        return self.success_response(recommendations)


class ProductRecommendLiteratureView(EnvelopeMixin, APIView):
    """POST /api/v1/products/<pk>/recommend-literature/

    Search PubMed for product-related literature and extract knowledge chain.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        top_k = int(request.data.get("top_k", 5)) if request.data else 5
        logger.info(f"Running LiteratureRecommender for product {pk}: {product.name}")
        recommender = LiteratureRecommender()
        result = recommender.recommend(product, top_k=top_k)
        return self.success_response(result)


# ── Batch Views ───────────────────────────────────────────────────────

class BatchValidateView(EnvelopeMixin, APIView):
    """POST /api/v1/products/batch-validate/

    Validate multiple products at once.
    Request body: {"product_ids": [1, 2, 3]}
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        product_ids = request.data.get("product_ids", []) if request.data else []
        if not product_ids:
            return self.success_response([])

        products = Product.objects.filter(pk__in=product_ids)
        validator = ProductValidator()
        results = []
        for product in products:
            report = validator.validate(product)
            results.append({
                "product_id": product.id,
                "product_name": product.name,
                "validation": serialize_validation_report(report, product),
            })
        logger.info(f"Batch validate: {len(results)} products processed")
        return self.success_response(results)


class BatchRecommendLiteratureView(EnvelopeMixin, APIView):
    """POST /api/v1/products/batch-recommend-literature/

    Recommend literature for multiple products at once.
    Request body: {"product_ids": [1, 2, 3]}
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        product_ids = request.data.get("product_ids", []) if request.data else []
        if not product_ids:
            return self.success_response([])

        products = Product.objects.filter(pk__in=product_ids)
        recommender = LiteratureRecommender()
        results = []
        for product in products:
            lit = recommender.recommend(product, top_k=5)
            results.append({
                "product_id": product.id,
                "product_name": product.name,
                "literature": lit,
            })
        logger.info(f"Batch literature: {len(results)} products processed")
        return self.success_response(results)
