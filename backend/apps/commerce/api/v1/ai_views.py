"""AI Tool API Views

AI TOOLS (per-field Validate / Protocols / Literature) 已合并进一站式
ProductEnrichView（AUTO MATCH）：enrich 的 chemical 段现额外返回
`mismatches`（cas/smiles 跨字段一致性）与 `similar_compounds`（相似化合物），
即原 AI Tools Validate 标签的独有能力。

保留的独立端点（AUTO MATCH 不重复覆盖）：
- ProductEnrichView            : 一站式 enrich（chemical+jena+bioz+literature+protocols）
- BatchValidateView            : 批量校验
- BatchRecommendLiteratureView : 批量文献推荐
- PubChemEnrichView            : 仅 PubChem 化学属性补全（单+批量）
- ProductRenderStructureView   : RDKit SMILES → SVG 结构图
- ProductImportProtocolView    : BioProCorpus 协议落库
- ProductAdoptBiozRefsView     : Bioz 文献落库
"""
import logging
from types import SimpleNamespace

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.commerce.services.validators.product_validator import ProductValidator
from apps.bridges.models import MethodProtocol
from apps.knowledge.services.literature_recommender import LiteratureRecommender
from apps.bridges.services.auto_links import (
    recommend_protocols_for_enrich,
    recommend_methods_for_enrich,
)

logger = logging.getLogger(__name__)


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
                "validation": {
                    "status": report.status,
                    "mismatches": report.mismatches,
                    "similar_compounds": report.similar_compounds,
                    "pubchem_cid": report.pubchem_cid,
                    "overall_match": report.overall_match,
                },
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
                enriched = enhancer.resolve_to_properties(name, expected_cas=product_cas or None)
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
        # pubchempy 不支持 namespace='cas'，CAS 走 name 查询但传 expected_cas 做身份校验（修复 2）
        identifier = None
        namespace = 'name'

        if cas and cas.strip():
            identifier = cas.strip()
            namespace = 'name'
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

        expected_cas = cas.strip() if cas and cas.strip() else None
        expected_formula = (request.data.get("formula") or "").strip() or None
        try:
            expected_mw = float(request.data.get("molecular_weight")) \
                if request.data.get("molecular_weight") not in (None, "") else None
        except (TypeError, ValueError):
            expected_mw = None

        enriched = enhancer.resolve_to_properties(
            identifier, namespace=namespace,
            expected_cas=expected_cas,
            expected_formula=expected_formula,
            expected_mw=expected_mw,
        )

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
                enriched = enhancer.resolve_to_properties(
                    fb_id, namespace=fb_ns, expected_cas=expected_cas)
                if enriched.get('found'):
                    break

        return self.success_response(enriched)


# ── One-stop Enrich View ─────────────────────────────────────────────────

class ProductEnrichView(EnvelopeMixin, APIView):
    """POST /api/v1/products/enrich/

    一站式 enrich：一次调用返回化学属性 + 文献推荐 + 协议推荐 + jena 规格 + Bioz 文献。
    用于产品编辑页的"一键补全"按钮（AI AUTO MATCH）。

    化学段（chemical）现额外包含原 AI Tools Validate 标签的独有校验能力：
    - mismatches         : 跨字段一致性（cas 与 smiles 是否指向同一物质）
    - similar_compounds  : PubChem 相似化合物列表
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer
        from apps.knowledge.models import Reference

        enhancer = PubChemEnhancer()
        product_name = (request.data.get("product_name") or "").strip()
        cas = (request.data.get("cas") or "").strip()
        smiles = (request.data.get("smiles") or "").strip()
        inchi = (request.data.get("inchi") or "").strip()
        # 可选：传入 product_id 时关联已落库 Reference 的回写（P3-1）
        product_pk = request.data.get("product_id")
        ref_lookup = {}  # (kind, key_lower) → ref_id

        # ── 化学属性（复用已有 enrich 逻辑）──
        chemical = {"found": False, "properties": {}, "source": ""}

        # 优先级: CAS > name > SMILES > InChI
        # 注意：pubchempy 不支持 namespace='cas'（会 400），故 CAS 仍走 name 查询，
        # 但把 cas 作为 expected_cas 传入，由 resolve_to_properties 做身份校验兜底（修复 2）。
        identifier = None
        namespace = "name"
        expected_cas = cas or ""
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

        # 文档已提供的 Formula/MW，用于与搜索结果交叉校验（修复 3）
        expected_formula = (request.data.get("formula") or "").strip()
        try:
            expected_mw = float(request.data.get("molecular_weight")) \
                if request.data.get("molecular_weight") not in (None, "") else None
        except (TypeError, ValueError):
            expected_mw = None

        if identifier:
            chemical = enhancer.resolve_to_properties(
                identifier, namespace=namespace,
                expected_cas=expected_cas or None,
                expected_formula=expected_formula or None,
                expected_mw=expected_mw,
            )

            # CAS 搜不到时用 name 降级（name 结果会标 requires_review，由用户显式选择）
            if not chemical.get("found") and cas and product_name:
                chemical = enhancer.resolve_to_properties(
                    product_name, "name",
                    expected_cas=None,
                    expected_formula=expected_formula or None,
                    expected_mw=expected_mw,
                )

            # ── Lipinski（本地计算，集成 Validate 能力）──
            if chemical.get("found") and chemical.get("properties"):
                try:
                    chemical["lipinski"] = enhancer.check_lipinski(chemical["properties"])
                except Exception as e:
                    logger.warning(f"Lipinski check failed: {e}")
                    chemical["lipinski"] = None

            # ── 跨字段一致性校验（原 AI Tools Validate 标签能力合并进 AUTO MATCH）──
            # mismatches = cas/smiles 是否指向同一物质；similar_compounds = PubChem 相似化合物。
            # 复用 ProductValidator，与旧 Validate 端点逻辑完全一致；失败不阻断 enrich 主流程。
            try:
                _fake = SimpleNamespace(
                    id=None,
                    name=product_name or identifier or "",
                    cas=cas or "",
                    smiles=smiles or "",
                )
                _vreport = ProductValidator().validate(_fake)
                chemical["mismatches"] = list(getattr(_vreport, "mismatches", []) or [])
                chemical["similar_compounds"] = list(getattr(_vreport, "similar_compounds", []) or [])
            except Exception as e:
                logger.warning(f"cross-field validation (merged from AI Tools) failed: {e}")
                chemical.setdefault("mismatches", [])
                chemical.setdefault("similar_compounds", [])

        # ── jena 匹配：规格预填草案（cas→name→synonyms 真级联，多供应商）──
        jena = {"matched": False, "sources": []}
        try:
            from apps.commerce.services.jena_matcher import match_jena, _looks_like_cas
            user_cas = cas or ""
            synonyms = (chemical.get("properties") or {}).get("synonyms", []) or []
            search_name = product_name or (identifier if namespace == "name" else "") or ""
            jena_input = user_cas or search_name
            jena_ns = "cas" if (user_cas and _looks_like_cas(user_cas)) else "name"
            # Biotium 光谱近似匹配（D2）：研究者可附带 Ex/Em 光谱，仅对 biotium 候选生效
            ex_em = (request.data.get("ex_em") or "").strip()
            if jena_input or synonyms:
                jena = match_jena(
                    identifier=jena_input,
                    namespace=jena_ns,
                    synonyms=synonyms,
                    request_name=product_name,
                    ex_em=ex_em,
                )
            # CAS 匹配失败 → 用 name 降级（修复 Word 导入自动填入错误 CAS 的情况）
            if not jena.get("matched"):
                if jena_ns == "cas" and search_name:
                    jena = match_jena(
                        identifier=search_name,
                        namespace="name",
                        synonyms=synonyms,
                        request_name=product_name,
                        ex_em=ex_em,
                    )
            # name 也没命中、且 PubChem 解析出不同 CAS → 用该 CAS 二次尝试
            if not jena.get("matched"):
                resolved_cas = (chemical.get("cas_resolved") or "").strip()
                if resolved_cas and resolved_cas != user_cas and _looks_like_cas(resolved_cas):
                    try:
                        jena = match_jena(
                            identifier=resolved_cas,
                            namespace="cas",
                            request_name=product_name,
                            ex_em=ex_em,
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"jena match failed: {e}")
            jena = {"matched": False, "sources": []}

        # ── Bioz 文献证据（兼容新旧结果结构）──
        bioz = {"queried": False, "reason": "no_jena_match"}
        try:
            from apps.knowledge.services.bioz_pipeline import fetch_bioz_evidence
            platform_cas = cas or chemical.get("cas_resolved") or ""
            # 兼容新旧结构：新结构优先取 jena 的 catalog_no（Bioz 只覆盖 jena）
            jena_for_bioz = jena
            if "sources" in jena and not jena.get("catalog_no"):
                # 优先 jena，其次任一个命中 source
                matched_sources = [s for s in jena.get("sources", []) if s.get("matched")]
                jena_source = next((s for s in matched_sources if s.get("vendor") == "jena"), None)
                s = jena_source or (matched_sources[0] if matched_sources else None)
                if s:
                    vendor_name = s.get("vendor", "")
                    if vendor_name == "jena":
                        vendor_for_bioz = "Jena Bioscience"
                    elif vendor_name == "cayman":
                        vendor_for_bioz = "Cayman Chemical"
                    elif vendor_name == "trilink":
                        vendor_for_bioz = "TriLink BioTechnologies"
                    elif vendor_name == "biotium":
                        vendor_for_bioz = "Biotium"
                    else:
                        vendor_for_bioz = vendor_name.capitalize() if vendor_name else "Unknown"
                    jena_for_bioz = {
                        "matched": True,
                        "catalog_no": s.get("catalog_no", ""),
                        "cas_number": s.get("cas_number"),
                        "match_key": s.get("match_key"),
                        "vendor": vendor_for_bioz,
                    }
            bioz = fetch_bioz_evidence(jena_for_bioz, platform_cas=platform_cas)
        except Exception as e:
            logger.warning(f"bioz pipeline failed: {e}")
            bioz = {"queried": False, "error": str(e)}

        # P3-1：回写已落库 Reference 的 ref_id（仅当传了 product_id）
        try:
            product_pk_int = int(product_pk) if product_pk else None
        except (TypeError, ValueError):
            product_pk_int = None

        # ── 文献推荐（PubMed 关键词/引用，保留 references 等）──
        literature = {"applications": [], "methods": [], "references": [], "protocols": [],
                      "matched_apps": [], "matched_methods": [], "unmatched_app_keywords": [],
                      "unmatched_method_keywords": []}
        try:
            lit_recommender = LiteratureRecommender()
            lit_name = product_name or identifier or ""
            if lit_name:
                literature = lit_recommender.recommend(lit_name, top_k=5) or literature
        except Exception as e:
            logger.warning(f"Literature recommender failed: {e}")

        # R1：enrich 预览方法推荐改走 auto_links 真 relevance 图（取代关键词子串假阳性）
        # 仅覆盖 matched_methods；PubMed references/关键词 其余部分保留。
        try:
            literature["matched_methods"] = recommend_methods_for_enrich(
                product_name or identifier or "", product_pk=product_pk_int)
        except Exception as e:
            logger.warning(f"R1 method recommendation failed: {e}")

        # ── 协议推荐（R1：auto_links 真 relevance 流水线，取代关键词 TF 假阳性）──
        # 已有商品返回其落库真实 PP 行（带真实三轴分）；草稿以 product_name 作伪 usage 实时算 S_A/S_B。
        protocols = []
        try:
            search_name = product_name or identifier or ""
            if search_name:
                protocols = recommend_protocols_for_enrich(
                    search_name, product_pk=product_pk_int, top_k=5)
        except Exception as e:
            logger.warning(f"R1 protocol recommendation failed: {e}")

        self._attach_ref_ids(literature, bioz, product_pk_int)

        return self.success_response({
            "chemical": chemical,
            "literature": literature,
            "protocols": protocols,
            "jena": jena,
            "bioz": bioz,
        })

    @staticmethod
    def _attach_ref_ids(literature, bioz, product_pk):
        """P3-1：给 enrich 返回的 references 回写 ref_id（已落库的 Reference id）。

        基于 product 已关联的 Reference 的 doi/pmid 建立索引，
        对 literature.references + bioz.references 每条加 ref_id 字段。
        """
        if not product_pk:
            return
        try:
            existing = Reference.objects.filter(
                product_references__product_id=product_pk
            ).values("doi", "pmid", "id")
        except Exception:
            return
        lookup = {}
        for r in existing:
            if r.get("doi"):
                lookup[("doi", r["doi"].lower())] = r["id"]
            if r.get("pmid"):
                lookup[("pmid", r["pmid"])] = r["id"]
        if not lookup:
            return
        for section in (literature, bioz):
            for ref in (section.get("references") or []):
                doi = (ref.get("doi") or "").strip().lower()
                pmid = (ref.get("pmid") or "").strip()
                if doi and ("doi", doi) in lookup:
                    ref["ref_id"] = lookup[("doi", doi)]
                elif pmid and ("pmid", pmid) in lookup:
                    ref["ref_id"] = lookup[("pmid", pmid)]


# ── Protocol Import ──────────────────────────────────────────────────────────

class ProductImportProtocolView(EnvelopeMixin, APIView):
    """POST /api/v1/products/import-protocol/

    从 BioProCorpus 富协议内容创建 DB Protocol + ProtocolStep 并关联到产品。
    幂等：同一 DOI (slug) 不重复创建。
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.knowledge.models import Method, Protocol, ProtocolStep
        from apps.bridges.models import ProductMethod, MethodProtocol
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
        method_ids = request.data.get("method_ids") or []   # 向后兼容：历史上误当作 product id 使用
        product_id = request.data.get("product_id")

        if not protocol_title:
            return self.error_response("protocol_title is required")

        # 1. Protocol 幂等（R0-b）—— 级联查重：name → slug，两者均**全局**匹配。
        #    历史缺陷 D2：filter(slug=..., method=method) 双条件查重 —— BioProCorpus 原件的
        #    method_id 全为 NULL，而下方 Method 解析逻辑对「协议标题式长句」必然新建 Method，
        #    两者永不相等 → 查重恒失败 → 每次导入都重复新建 Protocol（脏实体自我放大）。
        #    历史缺陷 D7：仅按 slug 查重仍然无效 —— 两端 slug 生成规则不一致：
        #      · BioProCorpus 语料：slug = slugify(name)   例 'context-driven-salt-seeking-test-rats'
        #      · 本导入端旧逻辑  ：slug = DOI 尾段          例 'BioProtoc.2456'
        #    且语料原件 references 为空（全库 14065 条仅 44 条含 doi.org），DOI 无法作为对齐键。
        #    实测：今日新建的 42 条协议 100% 是既有记录的同名重复，但 slug 无一相同。
        #    故以 name 为主键（全库同名重复仅 5 例，近似唯一），slug 为兜底。
        #    新建时统一采用 slugify(name)，与语料对齐，使后续 slug 查重也能生效；DOI 存 references。
        protocol_slug = slugify(protocol_title)[:255] or (
            protocol_url.split("/")[-1][:255] if protocol_url else 'protocol'
        )
        existing = Protocol.objects.filter(name__iexact=protocol_title).first()
        if existing is None and protocol_url:
            # 兼容早期以 DOI 尾段为 slug 写入的记录
            existing = Protocol.objects.filter(slug=protocol_url.split("/")[-1]).first()
        if existing is None:
            existing = Protocol.objects.filter(slug=protocol_slug).first()

        # 2. Method 解析：命中既有协议时**直接复用其桥接 method**，不再新建
        method = None
        if existing:
            mp = existing.method_protocols.select_related('method').first()
            method = mp.method if mp else None
        if method is None:
            method = self._resolve_or_create_method(
                method_name, protocol_title, objective,
                allow_create=bool(request.data.get("allow_create_method")),
            )

        # 3. 写入 Protocol —— R0-c：既有协议只补空字段，绝不覆盖既有语料
        reused = existing is not None
        if reused:
            protocol = existing
            update_fields = []
            for field, value in (
                ('objective', objective),
                ('reagents', reagents),
                ('equipment', equipment),
                ('materials', materials),
            ):
                if value and not (getattr(protocol, field, '') or '').strip():
                    setattr(protocol, field, value)
                    update_fields.append(field)
            if method is not None:
                MethodProtocol.objects.get_or_create(method=method, protocol=protocol)
            if update_fields:
                protocol.save(update_fields=update_fields + ['updated_at'])
        else:
            protocol = Protocol.objects.create(
                name=protocol_title,
                slug=protocol_slug,
                objective=objective,
                reagents=reagents,
                equipment=equipment,
                materials=materials,
                references=protocol_url,  # store DOI/URL as reference
                status='published',
            )
            if method is not None:
                MethodProtocol.objects.get_or_create(method=method, protocol=protocol)

        # 4. ProtocolStep —— R0-c：严禁 delete 既有步骤。
        #    仅在「本次新建的协议」或「既有协议一步都没有」时写入（补空不覆盖）。
        step_count = 0
        if steps and (not reused or not ProtocolStep.objects.filter(protocol=protocol).exists()):
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
            step_count = len(step_objs)

        # 5. 建立 Method↔Protocol 桥（此前缺失导致产品 protocol_ids 恒为空 → Protocols: None）
        if method is not None:
            MethodProtocol.objects.get_or_create(method=method, protocol=protocol)

        # 6. 将 Method 关联至产品（编辑页传 product_id；新建成品无 id 时由保存阶段按数组重建）
        product_ids = [product_id] if product_id else list(method_ids)
        for pid in product_ids:
            if not pid or method is None:
                continue
            try:
                product = Product.objects.get(pk=pid)
                ProductMethod.objects.get_or_create(
                    product=product,
                    method=method,
                )
            except Product.DoesNotExist:
                pass

        return self.success_response({
            "method_id": method.id if method else None,
            "method_name": method.name if method else "",
            "protocol_id": protocol.id,
            "protocol_slug": protocol.slug,
            "step_count": step_count,
            "protocol_reused": reused,   # R0-b 幂等回执：True = 命中既有协议，未新建
        })

    # ── Method 解析（R0-b）：精确 → slug → 关键词模糊；**默认绝不新建** ──────────
    #
    # 历史缺陷 D1：调用方传来的 method_name 实际是「协议标题式长句」（Bio-protocol 摘要句），
    # Method 表里根本不存在同名短方法名 → 精确匹配必失败；关键词重合 >=2 的阈值对
    # 长句 vs 短方法名同样几乎不可能达成 → 双双失败 → 必然走 Method.objects.create()。
    # 今日 16 条垃圾 Method（#58–73）全部由此产生，名称就是整句协议标题，且会被下一个
    # 产品的关键词检索重新捞回，形成自我放大的污染闭环。
    #
    # 新策略：BioProCorpus 语料原件的 method_id 全部为 NULL —— 「协议不挂方法」本就是
    # 既有约定。因此解析不到既有 Method 时直接返回 None，而不是凭空造一个。
    # 确需新建的调用方必须显式传 allow_create_method=true（人工兜底通道）。
    @staticmethod
    def _resolve_or_create_method(method_name, protocol_title, objective, allow_create=False):
        from apps.knowledge.models import Application, Method, ResearchGoal
        from django.utils.text import slugify

        name = (method_name or "").strip()
        if name:
            method = Method.objects.filter(name__iexact=name).first()
            if method:
                return method
            method = Method.objects.filter(slug=slugify(name)[:255]).first()
            if method:
                return method

        # 关键词模糊匹配（阈值 >=2 个非停用词命中）
        title_lower = (name or protocol_title).lower()
        stop = {'of', 'in', 'for', 'and', 'the', 'a', 'an', 'with', 'using', 'by', 'to', 'via'}
        keywords = {k for k in title_lower.split() if len(k) > 2 and k not in stop}
        best_match, best_count = None, 0
        for m in Method.objects.all().values('id', 'name'):
            count = sum(1 for kw in keywords if kw in m['name'].lower())
            if count > best_count:
                best_count, best_match = count, m
        if best_match and best_count >= 2:
            return Method.objects.get(pk=best_match['id'])

        if not allow_create:
            # 止血：解析不到就不挂方法（与语料 method_id=NULL 的既有约定一致）
            return None

        new_method_name = name or protocol_title[:50].strip()
        base_slug = slugify(new_method_name)[:255] or 'method'
        existing_method = Method.objects.filter(slug=base_slug).first()
        if existing_method:
            return existing_method

        app = Application.objects.first()
        if not app:
            rg, _ = ResearchGoal.objects.get_or_create(
                name="Research Applications",
                defaults={"summary": "Auto-created for protocol import", "status": "active"},
            )
            app = Application.objects.create(
                name="Research Application",
                slug="research-application",
                summary="Auto-created for protocol import",
                status='active',
                research_goal=rg,
            )
        return Method.objects.create(
            name=new_method_name,
            slug=base_slug,
            application=app,
            summary=objective[:500] if objective else protocol_title,
            status='active',
        )


# ── RDKit Structure Render ─────────────────────────────────────────────────

class ProductAdoptBiozRefsView(EnvelopeMixin, APIView):
    """POST /api/v1/products/<pk>/adopt-bioz-refs/

    把 Bioz enrich 返回的 references 批量落库到 Reference + ProductReference。
    去重：DOI > PMID > title 降级查重；关联按 (product, reference, citation_role) 去重。
    单条失败不中断整体（收集 errors），事务包裹。
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        from apps.commerce.services.bioz_adopter import adopt_bioz_references

        product = get_object_or_404(Product, pk=pk)
        refs = request.data.get("references") or []
        citation_role = (request.data.get("citation_role") or "supporting").strip()

        # citation_role 合法性校验
        valid_roles = {"primary", "supporting", "validation", "background"}
        if citation_role not in valid_roles:
            return self.error_response(
                f"invalid citation_role: {citation_role}, must be one of {sorted(valid_roles)}")

        if not isinstance(refs, list):
            return self.error_response("references must be a list")

        result = adopt_bioz_references(product, refs, citation_role=citation_role)
        return self.success_response(result)


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
