"""Literature-Driven Knowledge Chain Recommender
Searches PubMed for product-related literature and extracts:
- Research applications (Application)
- Experimental methods (Method)
- Protocol references (Reference)
"""
import logging
from typing import Optional
from django.db import models as db_models
from apps.knowledge.services.pubmed_client import PubMedClient
from apps.knowledge.models import Application, Method, Reference as RefModel

logger = logging.getLogger(__name__)


class LiteratureRecommender:
    """文献驱动的知识链推荐器"""

    def __init__(self, pubmed_client: Optional[PubMedClient] = None):
        self.pubmed = pubmed_client or PubMedClient()

    def recommend(self, product, top_k: int = 5) -> dict:
        """为产品推荐文献驱动的知识链"""
        if not product.name:
            return {"applications": [], "methods": [], "references": [], "protocols": []}

        literature = self.pubmed.search_by_product(
            product_name=product.name,
            cas=product.cas if product.cas else None,
            max_results=top_k,
        )

        applications = []
        methods = []
        references = []
        protocols = []

        for article in literature:
            title = article.get("title", "")
            source = article.get("source", "")

            # 从标题提取应用场景关键词
            app_keywords = self._extract_applications(title)
            applications.extend(app_keywords)

            # 提取方法关键词
            method_keywords = self._extract_methods(title)
            methods.extend(method_keywords)

            # 格式化引用
            authors = article.get("authors", [])
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += ", et al."
            pubdate = article.get("pubdate", "")
            citation = f"{author_str} ({pubdate}). {title}. {source}."
            if article.get("doi"):
                citation += f" https://doi.org/{article['doi']}"

            references.append({
                "pmid": article["pmid"],
                "title": title,
                "source": source,
                "pubdate": pubdate,
                "authors": authors,
                "doi": article.get("doi", ""),
                "citation": citation,
            })

            # 如果来源是 protocols.io/Nature Protocols 等，归为协议
            if any(kw in source.lower() for kw in ["protocol", "method", "jove"]):
                protocols.append({
                    "title": title,
                    "source": source,
                    "pmid": article["pmid"],
                })

        # 去重
        app_keywords = list(set(applications))
        method_keywords = list(set(methods))

        # ── 反向匹配已有知识实体 ──
        matched_apps, matched_methods, unmatched_apps, unmatched_methods = \
            self._match_against_db(app_keywords, method_keywords)

        return {
            "applications": app_keywords,
            "methods": method_keywords,
            "references": references,
            "protocols": protocols,
            # 新增的匹配信息
            "matched_apps": matched_apps,
            "matched_methods": matched_methods,
            "unmatched_app_keywords": unmatched_apps,
            "unmatched_method_keywords": unmatched_methods,
        }

    def _match_against_db(self, app_keywords, method_keywords):
        """检查提取的关键词是否匹配已有知识实体。
        返回 (matched_apps, matched_methods, unmatched_app_kw, unmatched_method_kw)
        """
        matched_apps = []
        unmatched_app_keywords = []

        for kw in app_keywords:
            readable = kw.replace('_', ' ')
            # Search name, summary, AND slug for matches
            found = Application.objects.filter(
                db_models.Q(name__icontains=readable) |
                db_models.Q(summary__icontains=readable) |
                db_models.Q(slug__icontains=kw) |
                db_models.Q(slug__icontains=readable.replace(' ', '-'))
            ).values('id', 'name', 'slug', 'research_goal_id')[:3]
            if found:
                matched_apps.append({
                    'keyword': kw,
                    'matches': list(found),
                })
            else:
                unmatched_app_keywords.append(kw)

        matched_methods = []
        unmatched_method_keywords = []

        for kw in method_keywords:
            readable = kw.replace('_', ' ')
            # Search name, summary, purpose, AND slug for matches
            found = Method.objects.filter(
                db_models.Q(name__icontains=readable) |
                db_models.Q(summary__icontains=readable) |
                db_models.Q(purpose__icontains=readable) |
                db_models.Q(slug__icontains=kw) |
                db_models.Q(slug__icontains=readable.replace(' ', '-'))
            ).values('id', 'name', 'slug', 'application_id')[:3]
            if found:
                matched_methods.append({
                    'keyword': kw,
                    'matches': list(found),
                })
            else:
                unmatched_method_keywords.append(kw)

        return matched_apps, matched_methods, unmatched_app_keywords, unmatched_method_keywords

    def _extract_applications(self, title: str) -> list:
        """从文献标题提取应用场景"""
        app_patterns = [
            ("cell proliferation", "cell_proliferation"),
            ("cell labeling", "cell_labeling"),
            ("cell detection", "cell_detection"),
            ("DNA labeling", "dna_labeling"),
            ("RNA labeling", "rna_labeling"),
            ("in situ", "in_situ_hybridization"),
            ("imaging", "imaging"),
            ("sequencing", "sequencing"),
            ("PCR", "pcr"),
            ("diagnostic", "diagnostics"),
            ("therapeutic", "therapy"),
            ("drug", "drug_discovery"),
            ("biomarker", "biomarker_detection"),
            ("protein", "protein_analysis"),
            ("gene", "gene_expression"),
            ("bacteria", "microbial_detection"),
            ("virus", "viral_detection"),
        ]
        title_lower = title.lower()
        found = []
        for pattern, app_name in app_patterns:
            if pattern in title_lower:
                found.append(app_name)
        return found if found else ["research_application"]

    def _extract_methods(self, title: str) -> list:
        """从文献标题提取实验方法"""
        method_patterns = [
            ("click chemistry", "click_chemistry"),
            ("CuAAC", "cuaac"),
            ("PCR", "polymerase_chain_reaction"),
            ("sequencing", "sequencing"),
            ("microscopy", "microscopy"),
            ("flow cytometry", "flow_cytometry"),
            ("spectroscopy", "spectroscopy"),
            ("chromatography", "chromatography"),
            ("electrophoresis", "electrophoresis"),
            ("hybridization", "hybridization"),
            ("microarray", "microarray"),
            ("mass spectrometry", "mass_spectrometry"),
            ("NMR", "nmr"),
            ("X-ray", "xray_crystallography"),
            ("crystal", "xray_crystallography"),
            ("FRET", "fret"),
            ("ELISA", "elisa"),
            ("Western", "western_blot"),
            ("labeling", "labeling"),
            ("detection", "detection"),
            ("amplification", "amplification"),
        ]
        title_lower = title.lower()
        found = []
        for pattern, method_name in method_patterns:
            if pattern in title_lower:
                found.append(method_name)
        return found
