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

    identifier 优先级: CAS > name > SMILES > InChI > InChIKey > Formula
    有任一可用标识符即尝试查询。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer

        enhancer = PubChemEnhancer()
        product_ids = request.data.get("product_ids", []) if request.data else None
        product_name = request.data.get("product_name", "") if request.data else ""
        cas = request.data.get("cas", "") if request.data else ""
        smiles = request.data.get("smiles", "") if request.data else ""
        inchi = request.data.get("inchi", "") if request.data else ""

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

        # ── 单产品模式 — 优先级: CAS > name > SMILES > InChI ──
        identifier = None
        namespace = 'name'

        if cas and cas.strip():
            identifier = cas.strip()
            namespace = 'name'  # CAS 作为 name 搜索
        elif product_name and product_name.strip():
            identifier = product_name.strip()
            namespace = 'name'
        elif smiles and smiles.strip():
            identifier = smiles.strip()
            namespace = 'smiles'
        elif inchi and inchi.strip():
            identifier = inchi.strip()
            namespace = 'inchi'

        if not identifier:
            return self.error_response(
                'At least one identifier is required: product_name, cas, smiles, or inchi'
            )

        enriched = enhancer.resolve_to_properties(identifier, namespace=namespace)

        # 降级策略：当前 identifier 搜不到时，依次尝试其他可用字段
        fallbacks = []
        if not enriched.get('found'):
            if namespace != 'name' and product_name and product_name.strip():
                fallbacks.append(('name', product_name.strip()))
            if cas and cas.strip() and namespace != 'name':
                fallbacks.append(('name', cas.strip()))
            if smiles and smiles.strip() and namespace != 'smiles':
                fallbacks.append(('smiles', smiles.strip()))
            if inchi and inchi.strip() and namespace != 'inchi':
                fallbacks.append(('inchi', inchi.strip()))
            if namespace != 'name' and product_name and not product_name.strip() and cas and cas.strip():
                pass  # CAS already handled

            for fb_ns, fb_id in fallbacks:
                enriched = enhancer.resolve_to_properties(fb_id, namespace=fb_ns)
                if enriched.get('found'):
                    break

        return self.success_response(enriched)


# ── One-stop Enrich View ─────────────────────────────────────────────────

class ProductEnrichView(EnvelopeMixin, APIView):
    """POST /api/v1/products/enrich/

    一站式 enrich：一次调用返回化学属性 + 文献推荐 + 协议推荐。
    用于产品编辑页的"一键补全"按钮，研究员无需分三次调用。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer

        enhancer = PubChemEnhancer()
        product_name = (request.data.get("product_name") or "").strip()
        cas = (request.data.get("cas") or "").strip()
        smiles = (request.data.get("smiles") or "").strip()
        inchi = (request.data.get("inchi") or "").strip()

        # ── 化学属性（复用已有 enrich 逻辑）──
        chemical = {"found": False, "properties": {}, "source": ""}

        # 优先级: CAS > name > SMILES > InChI
        identifier = None
        namespace = "name"
        if cas:
            identifier = cas
        elif product_name:
            identifier = product_name
        elif smiles:
            identifier = smiles
            namespace = "smiles"
        elif inchi:
            identifier = inchi
            namespace = "inchi"

        if identifier:
            chemical = enhancer.resolve_to_properties(identifier, namespace=namespace)

            # CAS 搜不到时用 name 降级
            if not chemical.get("found") and cas and product_name:
                chemical = enhancer.resolve_to_properties(product_name, "name")

        # ── 文献推荐 ──
        literature = {"applications": [], "methods": [], "references": [], "protocols": [],
                      "matched_apps": [], "matched_methods": [], "unmatched_app_keywords": [],
                      "unmatched_method_keywords": []}
        try:
            from apps.knowledge.services.literature_recommender import LiteratureRecommender
            lit_recommender = LiteratureRecommender()
            lit_name = product_name or identifier or ""
            if lit_name:
                literature = lit_recommender.recommend(lit_name, top_k=5) or literature
        except Exception as e:
            logger.warning(f"Literature recommender failed: {e}")

        # ── 协议推荐 ──
        protocols = []
        try:
            from apps.knowledge.services.protocol_recommender import ProtocolRecommender
            proto_recommender = ProtocolRecommender()
            search_name = product_name or identifier or ""
            if search_name:
                results = proto_recommender.retriever.search(search_name, top_k=5, include_content=True)
                for r in results:
                    protocols.append({
                        "id": r["id"],
                        "source": r["source"],
                        "title": r["title"],
                        "abstract": r.get("abstract", ""),
                        "url": r.get("url", ""),
                        "score": r["score"],
                        "reagents": r.get("reagents", ""),
                        "equipment": r.get("equipment", ""),
                        "materials": r.get("materials", ""),
                        "steps": r.get("steps", []),
                        "method_hint": r.get("method_hint", ""),
                    })
        except Exception as e:
            logger.warning(f"Protocol recommender failed: {e}")

        return self.success_response({
            "chemical": chemical,
            "literature": literature,
            "protocols": protocols,
        })


# ── Protocol Import ──────────────────────────────────────────────────────────

class ProductImportProtocolView(EnvelopeMixin, APIView):
    """POST /api/v1/products/import-protocol/

    从 BioProCorpus 富协议内容创建 DB Protocol + ProtocolStep 并关联到产品。
    幂等：同一 DOI (slug) 不重复创建。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.knowledge.models import Method, Protocol, ProtocolStep
        from apps.bridges.models import ProductMethod
        from apps.commerce.models import Product
        from django.utils.text import slugify

        method_name = (request.data.get("method_name") or "").strip()
        protocol_title = (request.data.get("protocol_title") or "").strip()
        protocol_url = (request.data.get("protocol_url") or "").strip()
        objective = (request.data.get("objective") or "").strip()
        reagents = (request.data.get("reagents") or "").strip()
        equipment = (request.data.get("equipment") or "").strip()
        materials = (request.data.get("materials") or "").strip()
        steps = request.data.get("steps") or []
        method_ids = request.data.get("method_ids") or []

        if not protocol_title:
            return self.error_response("protocol_title is required")

        # 1. Find or create Method (fuzzy matching)
        method = None
        from django.db import models as db_models

        if method_name:
            # Try exact match first
            method = Method.objects.filter(name__iexact=method_name.strip()).first()
        if not method:
            # Fuzzy: match by title keywords against existing Methods
            title_lower = (method_name or protocol_title).lower()
            keywords = set(title_lower.split())
            # Filter stop words
            stop = {'of', 'in', 'for', 'and', 'the', 'a', 'an', 'with', 'using', 'by', 'to', 'via'}
            keywords = {k for k in keywords if len(k) > 2 and k not in stop}

            existing_methods = list(Method.objects.all().values('id', 'name', 'slug'))
            best_match = None
            best_count = 0
            for m in existing_methods:
                m_lower = m['name'].lower()
                count = sum(1 for kw in keywords if kw in m_lower)
                if count > best_count:
                    best_count = count
                    best_match = m

            if best_match and best_count >= 2:
                method = Method.objects.get(pk=best_match['id'])

        if not method:
            # Create a new Method — use method_name if provided, else first 50 chars of title
            new_method_name = method_name or protocol_title[:50].strip()
            # Ensure uniqueness
            base_slug = slugify(new_method_name)
            slug_orig = base_slug
            counter = 1
            while Method.objects.filter(slug=base_slug).exists():
                base_slug = f"{slug_orig}-{counter}"
                counter += 1
            # Attach to first available Application
            from apps.knowledge.models import Application, ResearchGoal
            app = Application.objects.first()
            if not app:
                # Auto-create default ResearchGoal + Application
                rg, _ = ResearchGoal.objects.get_or_create(
                    name="Research Applications",
                    defaults={"summary": "Auto-created for protocol import", "status": "active"}
                )
                app = Application.objects.create(
                    name="Research Application",
                    slug="research-application",
                    summary="Auto-created for protocol import",
                    status='active',
                    research_goal=rg,
                )
            method = Method.objects.create(
                name=new_method_name,
                slug=base_slug,
                application=app,
                summary=objective[:500] if objective else protocol_title,
                status='active',
            )

        # 2. Create Protocol (idempotent by slug = DOI or title)
        protocol_slug = protocol_url.split("/")[-1] if protocol_url else slugify(protocol_title)
        # Reuse existing if same slug & method
        existing = Protocol.objects.filter(slug=protocol_slug, method=method).first()
        if existing:
            protocol = existing
            # update content
            if objective:
                protocol.objective = objective
            if reagents:
                protocol.reagents = reagents
            if equipment:
                protocol.equipment = equipment
            if materials:
                protocol.materials = materials
            protocol.save()
        else:
            protocol = Protocol.objects.create(
                method=method,
                name=protocol_title,
                slug=protocol_slug,
                objective=objective,
                reagents=reagents,
                equipment=equipment,
                materials=materials,
                references=protocol_url,  # store DOI/URL as reference
                status='published',
            )

        # 3. Create ProtocolStep (bulk, clear old steps first)
        if steps:
            ProtocolStep.objects.filter(protocol=protocol).delete()
            step_objs = []
            for i, s in enumerate(steps):
                step_objs.append(ProtocolStep(
                    protocol=protocol,
                    step_no=i + 1,
                    title=s.get("title", "")[:255],
                    body=s.get("body", ""),
                    required_materials=s.get("body", "")[:500],
                ))
            ProtocolStep.objects.bulk_create(step_objs)

        # 4. Link Method to product if method_ids provided
        if method_ids:
            for pid in method_ids:
                try:
                    product = Product.objects.get(pk=pid)
                    ProductMethod.objects.get_or_create(
                        product=product,
                        method=method,
                    )
                except Product.DoesNotExist:
                    pass

        return self.success_response({
            "method_id": method.id,
            "method_name": method.name,
            "protocol_id": protocol.id,
            "protocol_slug": protocol.slug,
            "step_count": len(steps),
        })


# ── RDKit Structure Render ─────────────────────────────────────────────────

class ProductRenderStructureView(EnvelopeMixin, APIView):
    """POST /api/v1/products/render-structure/

    用 RDKit 将 SMILES 渲染为出版级 SVG 结构图。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer

        smiles = (request.data.get("smiles") or "").strip()
        if not smiles:
            return self.error_response("smiles is required")

        renderer = RDKitRenderer()
        svg = renderer.render_svg(
            smiles,
            width=int(request.data.get("width", 500)),
            height=int(request.data.get("height", 400)),
        )

        if not svg:
            return self.error_response("Failed to render structure — invalid SMILES")

        # Also return canonical SMILES for the front-end
        validated = RDKitRenderer.validate_smiles(smiles)
        canonical = validated.get("canonical", "") if validated.get("valid") else ""

        return self.success_response({"svg": svg, "format": "svg", "canonical_smiles": canonical})


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
