"""DataSourceCache 模型 + L1 helper 单测。

L1 持久化缓存：命中/过期/allow_stale/upsert 行为。详见 docs/DATASOURCE_RELIABILITY.md §6。
"""
import json
from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.documents.models import DataSourceCache
from apps.documents.services.datasource_cache import (
    DEFAULT_TTL,
    SOURCE_TTL,
    get_cache,
    set_cache,
)


class DataSourceCacheModelTest(TestCase):
    def test_create_and_retrieve(self):
        entry = DataSourceCache.objects.create(
            source="pubchem",
            query_key="aspirin",
            query_namespace="name",
            data_json=json.dumps({"cid": 2244}),
            expires_at=timezone.now() + timedelta(days=30),
        )
        fetched = DataSourceCache.objects.get(pk=entry.pk)
        self.assertEqual(fetched.source, "pubchem")
        self.assertEqual(fetched.query_key, "aspirin")
        self.assertEqual(fetched.get_data(), {"cid": 2244})
        self.assertFalse(fetched.is_stale)

    def test_unique_constraint(self):
        DataSourceCache.objects.create(
            source="pubchem", query_key="X", query_namespace="name",
            data_json="{}", expires_at=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(IntegrityError):
            DataSourceCache.objects.create(
                source="pubchem", query_key="X", query_namespace="name",
                data_json="{}", expires_at=timezone.now() + timedelta(days=1),
            )

    def test_namespace_disambiguates(self):
        """同 source + key 但不同 namespace 可共存（name vs cas 是不同查询）。"""
        for ns in ("name", "cas"):
            DataSourceCache.objects.create(
                source="pubchem", query_key="aspirin", query_namespace=ns,
                data_json="{}", expires_at=timezone.now() + timedelta(days=1),
            )
        self.assertEqual(DataSourceCache.objects.filter(source="pubchem", query_key="aspirin").count(), 2)


class GetCacheTest(TestCase):
    def test_miss_returns_none(self):
        self.assertIsNone(get_cache("pubchem", "nonexistent"))

    def test_hit_returns_entry(self):
        set_cache("pubchem", "aspirin", "name", {"cid": 2244})
        entry = get_cache("pubchem", "aspirin", "name")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get_data(), {"cid": 2244})
        self.assertFalse(entry.is_stale)

    def test_expired_returns_none_without_allow_stale(self):
        set_cache("pubchem", "old", "name", {"v": 1}, ttl_seconds=0)
        # expires_at 设为 now，立即过期
        DataSourceCache.objects.filter(source="pubchem", query_key="old").update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertIsNone(get_cache("pubchem", "old", "name"))

    def test_expired_returns_entry_with_allow_stale(self):
        set_cache("pubchem", "old", "name", {"v": 1})
        DataSourceCache.objects.filter(source="pubchem", query_key="old").update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        entry = get_cache("pubchem", "old", "name", allow_stale=True)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get_data(), {"v": 1})

    def test_empty_query_key_returns_none(self):
        self.assertIsNone(get_cache("pubchem", ""))


class SetCacheTest(TestCase):
    def test_set_then_get(self):
        set_cache("chembl", "CHEMBL25", "name", {"mw": 180.16})
        entry = get_cache("chembl", "CHEMBL25", "name")
        self.assertEqual(entry.get_data(), {"mw": 180.16})

    def test_upsert_refreshes(self):
        set_cache("pubchem", "aspirin", "name", {"v": 1})
        set_cache("pubchem", "aspirin", "name", {"v": 2})
        self.assertEqual(DataSourceCache.objects.filter(source="pubchem", query_key="aspirin").count(), 1)
        entry = get_cache("pubchem", "aspirin", "name")
        self.assertEqual(entry.get_data(), {"v": 2})

    def test_upsert_clears_stale_flag(self):
        DataSourceCache.objects.create(
            source="pubmed", query_key="X", query_namespace="name",
            data_json="{}", expires_at=timezone.now() + timedelta(days=1),
            is_stale=True,
        )
        set_cache("pubmed", "X", "name", {"fresh": True})
        entry = get_cache("pubmed", "X", "name")
        self.assertFalse(entry.is_stale)

    def test_uses_source_specific_ttl(self):
        set_cache("pubchem", "a", "name", {})
        set_cache("pubmed", "b", "name", {})
        pubchem_entry = get_cache("pubchem", "a", "name")
        pubmed_entry = get_cache("pubmed", "b", "name")
        # PubChem 30 天，PubMed 14 天 → PubChem 过期更晚
        self.assertGreater(pubchem_entry.expires_at, pubmed_entry.expires_at)
        self.assertEqual(SOURCE_TTL["pubchem"], 60 * 60 * 24 * 30)
        self.assertEqual(SOURCE_TTL["pubmed"], 60 * 60 * 24 * 14)
        self.assertEqual(DEFAULT_TTL, 60 * 60 * 24 * 14)

    def test_custom_ttl_overrides(self):
        set_cache("pubchem", "short", "name", {}, ttl_seconds=60)
        entry = get_cache("pubchem", "short", "name")
        self.assertLess(entry.expires_at - timezone.now(), timedelta(minutes=2))
