"""AI Tool API Views

DRF views exposing the three AI tools to the admin UI:
- ProductValidateView: PubChem + BioProCorpus validation
- ProductRecommendProtocolsView: BioProCorpus protocol recommendations
- ProductRecommendLiteratureView: PubMed literature recommendations
- BatchValidateView: batch product validation
- BatchRecommendLiteratureView: batch literature recommendations
- ValidateUnsavedView / RecommendProtocolsUnsavedView / RecommendLiteratureUnsavedView:
  新建页无 productId 时用 payload 直接调用服务
"""
import logging
from types import SimpleNamespace

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
    result = {
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
    # ── PubChemEnhancer 新增字段 ──
    if hasattr(report, 'molecular_properties') and report.molecular_properties:
        result['pubchem']['molecular_properties'] = report.molecular_properties
    if hasattr(report, 'lipinski') and report.lipinski:
        result['pubchem']['lipinski'] = report.lipinski
    if hasattr(report, 'similar_compounds') and report.similar_compounds:
        result['pubchem']['similar_compounds'] = report.similar_compounds

    return result


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


# ── PubChem Enrich ────────────────────────────────────────────────────

class PubChemEnrichView(EnvelopeMixin, APIView):
    """POST /api/v1/products/enrich-from-pubchem/

    从 PubChem 自动解析产品的化学属性（CAS/SMILES/Formula/MW 等）。
    用于产品编辑页的"自动补全"功能和产品列表页的"批量补全"。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer

        enhancer = PubChemEnhancer()
        product_ids = request.data.get("product_ids", []) if request.data else None
        product_name = request.data.get("product_name", "") if request.data else ""
        cas = request.data.get("cas", "") if request.data else ""

        # ── 批量模式 ──
        if product_ids:
            products = Product.objects.filter(pk__in=product_ids)
            results = []
            for product in products:
                name = product.name
                product_cas = product.cas or ""
                enriched = enhancer.resolve_to_properties(name)
                resolved_cas = enriched.get('cas_resolved') or product_cas
                props = enriched.get('properties') or {}
                results.append({
                    "product_id": product.id,
                    "product_name": name,
                    "enriched": {
                        "found": enriched.get('found', False),
                        "cid": enriched.get('cid'),
                        "cas": resolved_cas,
                        "smiles": props.get('canonical_smiles', ''),
                        "formula": props.get('molecular_formula', ''),
                        "molecular_weight": props.get('molecular_weight', 0),
                        "xlogp": props.get('xlogp'),
                        "tpsa": props.get('tpsa'),
                    },
                })
            return self.success_response(results)

        # ── 单产品模式 ──
        if cas and cas.strip():
            identifier = cas.strip()
        elif product_name and product_name.strip():
            identifier = product_name.strip()
        else:
            return self.error_response('product_name or cas is required')

        enriched = enhancer.resolve_to_properties(identifier)

        # 如果按 CAS 查出了属性但没有 CAS 号（测试场景），补充一程用产品名
        if cas and cas.strip() and not enriched.get('found'):
            enriched = enhancer.resolve_to_properties(product_name.strip())

        return self.success_response(enriched)


# ── Unsaved-product Views (新建页无 productId 时使用) ────────────────

def _build_fake_product(name, cas='', smiles=''):
    """用 SimpleNamespace 包装 payload — 三个 AI 服务只访问 name/cas/smiles/id。"""
    return SimpleNamespace(id=None, name=name, cas=cas or '', smiles=smiles or '')


class ValidateUnsavedView(EnvelopeMixin, APIView):
    """POST /api/v1/products/validate-unsaved/  body: {name, cas?, smiles?}

    新建产品页（未保存）的 AI 校验。三个服务不依赖持久化对象，
    只读取 name/cas/smiles 字段（id 仅用于日志）。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data or {}
        name = (data.get('name') or '').strip()
        if not name:
            return self.error_response('name is required')
        fake = _build_fake_product(
            name=name,
            cas=(data.get('cas') or '').strip(),
            smiles=(data.get('smiles') or '').strip(),
        )
        validator = ProductValidator()
        report = validator.validate(fake)
        return self.success_response(serialize_validation_report(report, fake))


class RecommendProtocolsUnsavedView(EnvelopeMixin, APIView):
    """POST /api/v1/products/recommend-protocols-unsaved/  body: {name, top_k?}"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data or {}
        name = (data.get('name') or '').strip()
        if not name:
            return self.error_response('name is required')
        top_k = int(data.get('top_k', 5))
        recommender = ProtocolRecommender()
        return self.success_response(recommender.recommend(name, top_k=top_k))


class RecommendLiteratureUnsavedView(EnvelopeMixin, APIView):
    """POST /api/v1/products/recommend-literature-unsaved/  body: {name, cas?, top_k?}"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data or {}
        name = (data.get('name') or '').strip()
        if not name:
            return self.error_response('name is required')
        top_k = int(data.get('top_k', 5))
        fake = _build_fake_product(
            name=name,
            cas=(data.get('cas') or '').strip(),
        )
        recommender = LiteratureRecommender()
        return self.success_response(recommender.recommend(fake, top_k=top_k))
