# -*- coding: utf-8 -*-
"""外部数据源「离线回放」端到端用例 —— 证明依赖外网的业务逻辑可以脱离网络测试

## 为什么这组用例比一般 mock 测试更有价值
一般测试用 `mock.patch` 手写响应 JSON。手写的东西**必然与真实响应有差异**：
真实 PubChem 响应带 `PC_Compounds` / `PropertyTable.Properties` 两层嵌套、
字段名大小写、类型（CID 是 int）、错误分支的 `Fault` 结构……
手写 mock 只能覆盖"我以为的样子"，于是出现过"测试全绿、真机 500"。

这里回放的是**真实录制下来的原始字节**（`backend/cassettes/*.jsonl`），
由 `scripts/record_datasources.py` 从线上 API 录的。
所以它既离线、又保真。

## 关键断言：不仅"结果对"，还要"确实没联网"
光断言 `cid == 2244` 说明不了离线可用 —— 网络好的时候它也会绿。
每个用例都把 `requests.request` 打成"一碰就炸"，
**只有真的一次都没调用**才算通过。

## 数据源变了怎么办
回放的是录下来的快照，线上数据源更新**不会**自动反映（这是特性，不是 bug：
测试要稳定）。需要更新时：
```bash
rm backend/cassettes/pubchem.jsonl
cd backend && venv/Scripts/python.exe ../scripts/record_datasources.py --only pubchem
```
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from core import http_cassette

CASSETTE_DIR = http_cassette.cassette_dir()


def _cassette_exists(source):
    return os.path.exists(http_cassette.cassette_path(source))


class _ReplayMixin:
    """把模式切到 replay，并保证不残留环境变量影响后续用例。"""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(
            os.environ, {http_cassette.MODE_ENV: http_cassette.MODE_REPLAY}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _no_network(self):
        """把真实网络调用打成"一碰就炸"，用来证明回放确实没回源。"""
        return mock.patch(
            'core.datasource_client.requests.request',
            side_effect=AssertionError('回放模式下不该发起真实网络请求'),
        )


class PubChemReplayTests(_ReplayMixin, SimpleTestCase):
    """PubChem：CAS → CID → CanonicalSMILES（`PubChemClient` 走统一客户端）。"""

    def setUp(self):
        super().setUp()
        if not _cassette_exists('pubchem'):
            self.skipTest(
                '缺少 backend/cassettes/pubchem.jsonl —— '
                '运行 venv/Scripts/python.exe ../scripts/record_datasources.py --only pubchem 录制')

    def test_lookup_by_cas_offline(self):
        from apps.commerce.services.validators.product_validator import PubChemClient

        with self._no_network() as m:
            result = PubChemClient(timeout=10).lookup_by_cas('50-78-2')

        self.assertEqual(m.call_count, 0, '回放模式必须一次网络调用都没有')
        self.assertIsNotNone(result, 'cassette 未命中 ⇒ lookup_by_cas 吞异常返回了 None')
        self.assertEqual(result['cid'], 2244, '阿司匹林的 PubChem CID 应为 2244')

    def test_compare_smiles_offline_full_chain(self):
        """完整链路（两次请求：CAS→CID、CID→SMILES）都必须命中 cassette。"""
        from apps.commerce.services.validators.product_validator import PubChemClient

        aspirin = 'CC(=O)OC1=CC=CC=C1C(=O)O'
        with self._no_network() as m:
            result = PubChemClient(timeout=10).compare_smiles(aspirin, '50-78-2')

        self.assertEqual(m.call_count, 0)
        self.assertTrue(result['match'], f'SMILES 应一致，实际：{result}')
        self.assertEqual(result['cid'], 2244)
        self.assertEqual(result['mismatch_fields'], [])
        # 真实响应里 PubChem 的 SMILES 与产品侧写法完全一致（不是我们造的假数据）
        self.assertEqual(result['pubchem_smiles'], aspirin)


class PubMedReplayTests(_ReplayMixin, SimpleTestCase):
    """PubMed：按 PMID 取摘要（E-utilities efetch，返回 XML）。"""

    def setUp(self):
        super().setUp()
        if not _cassette_exists('pubmed'):
            self.skipTest(
                '缺少 backend/cassettes/pubmed.jsonl —— '
                '运行 venv/Scripts/python.exe ../scripts/record_datasources.py --only pubmed 录制')

    def test_fetch_abstract_offline(self):
        from apps.knowledge.services.pubmed_client import PubMedClient

        with self._no_network() as m:
            text = PubMedClient(timeout=10).fetch_abstract('24151172', max_chars=1200)

        self.assertEqual(m.call_count, 0, '回放模式必须一次网络调用都没有')
        self.assertTrue(text, 'cassette 未命中或 XML 解析失败 ⇒ 摘要为空')
        self.assertGreater(len(text), 100, f'摘要过短，疑似解析异常：{text[:80]!r}')
        # 录的是 XML，解析后应该是纯文本（不该残留标签）
        self.assertNotIn('<AbstractText', text, 'XML 标签没被剥离')
        self.assertNotIn('</', text, 'XML 标签没被剥离')


class CassetteHygieneTests(SimpleTestCase):
    """cassette 是要进仓库的文件 ⇒ 顺手守住"不含凭据、不含巨大体积"。"""

    def test_no_credentials_in_any_cassette(self):
        if not os.path.isdir(CASSETTE_DIR):
            self.skipTest('还没有 cassette 目录')
        suspects = ('authorization', 'cookie', 'api_key', 'sk-', 'token=')
        for name in os.listdir(CASSETTE_DIR):
            if not name.endswith('.jsonl'):
                continue
            path = os.path.join(CASSETTE_DIR, name)
            with open(path, encoding='utf-8') as f:
                raw = f.read().lower()
            for bad in suspects:
                self.assertNotIn(
                    bad, raw,
                    f'{name} 里出现了疑似凭据片段 {bad!r} —— cassette 会进仓库，必须清掉')

    def test_cassette_size_reasonable(self):
        """单文件不该大到没法进仓库（每行 ≤ 2MB 上限已由录制侧保证）。"""
        if not os.path.isdir(CASSETTE_DIR):
            self.skipTest('还没有 cassette 目录')
        for name in os.listdir(CASSETTE_DIR):
            if not name.endswith('.jsonl'):
                continue
            size = os.path.getsize(os.path.join(CASSETTE_DIR, name))
            self.assertLess(size, 5 * 1024 * 1024, f'{name} 有 {size} 字节，过大了')
