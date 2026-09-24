"""★ 第 0 步闸门：协议侧领域词 Q 的**离线预算缓存**（2026-09-24）。

## 为什么

`recommend_protocols_for_enrich` 的**草稿分支**（新品页 / AI 预览）要按 `P ∩ Q(每个协议)`
对**全库协议**打分。实测（14,084 条，i7-13700KF）：

| 方式 | 耗时 |
|---|---|
| 实时全库预计算 | **21.97s**（`_extract_domains` 占 21.75s，DB 取数仅 0.11s） |
| 读离线预算文件 | **0.007s** |

⇒ 离线预算成文件后，请求路径不再付这 22s。

## 本文件锁死的契约

1. **文件缺失 / 解析失败 / 指纹不符 ⇒ 一律回退实时计算**（返回 None，绝不抛错、绝不给出错误结果）。
2. **指纹 = (协议总数, max(id))**。这条是**正确性安全阀**，不是可选优化：
   缓存是快照，协议被新增后若仍信任它，**新协议将永远不被推荐**
   —— 这会打红既有的 `test_ai_views.py::test_draft_protocol_via_domain_match`
   （该用例新建一条协议后期望草稿分支能找到它）。
3. **快路径与实时计算结果必须逐条一致**（本文件用 round-trip 比对）。
4. 命令幂等；`--check` 在不新鲜时 **exit 1**（供部署后核验）。
"""
import json

from django.core.management import call_command
from django.test import TestCase

from apps.bridges.services import auto_links as A
from apps.knowledge.models import Protocol


def _write_cache(path, meta, q):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({A._Q_CACHE_META_KEY: meta, 'q': q}, fh)


class QCacheLoadContractTest(TestCase):
    """加载端的四种失败形态都必须**安全回退**，绝不抛错。"""

    def setUp(self):
        self._orig = A._Q_CACHE_PATH

    def tearDown(self):
        A._Q_CACHE_PATH = self._orig
        A._PROTO_Q_CACHE = None

    def test_missing_file_returns_none(self):
        A._Q_CACHE_PATH = '/nonexistent/definitely-missing.json'
        self.assertIsNone(A._load_q_cache_from_file(), '文件缺失 ⇒ 必须回退')

    def test_corrupt_file_returns_none(self):
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('{ this is not json')
        try:
            A._Q_CACHE_PATH = p
            self.assertIsNone(A._load_q_cache_from_file(), '坏文件 ⇒ 必须回退而不是崩')
        finally:
            os.remove(p)

    def test_fingerprint_mismatch_returns_none(self):
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        _write_cache(p, {'protocol_count': 999999, 'max_id': 999999}, {'1': ['pcr']})
        try:
            A._Q_CACHE_PATH = p
            self.assertIsNone(
                A._load_q_cache_from_file(),
                '指纹不符 ⇒ 必须回退（否则新协议永远不被推荐）',
            )
        finally:
            os.remove(p)

    def test_fingerprint_match_returns_set_valued_dict(self):
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        live = A._q_cache_fingerprint()
        _write_cache(p, live, {'7': ['pcr', 'dna']})
        try:
            A._Q_CACHE_PATH = p
            got = A._load_q_cache_from_file()
            self.assertIsNotNone(got, '指纹相符 ⇒ 应加载')
            self.assertEqual(got, {7: {'pcr', 'dna'}}, '键必须还原为 int、值必须还原为 set')
        finally:
            os.remove(p)


class QCacheBuildCommandTest(TestCase):
    """`build_protocol_q_cache`：round-trip 等价 + 幂等 + `--check` 语义。"""

    def setUp(self):
        self._orig = A._Q_CACHE_PATH
        import tempfile, os
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'protocol_q_cache.json')
        A._Q_CACHE_PATH = self.path
        A._PROTO_Q_CACHE = None
        Protocol.objects.create(name='PCR amplification protocol', slug='q-pcr',
                                status='published', objective='pcr primer extension')

    def tearDown(self):
        A._Q_CACHE_PATH = self._orig
        A._PROTO_Q_CACHE = None
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_build_then_load_equals_live_compute(self):
        import io
        call_command('build_protocol_q_cache', stdout=io.StringIO())
        live = A.compute_q_cache()
        A._PROTO_Q_CACHE = None
        got = A._get_proto_q_cache()
        for pid, q in live.items():
            if q:
                self.assertEqual(got.get(pid), q, f'协议 {pid} 的 Q 应与实时计算一致')
        # 空 Q 的条目不写入文件 ⇒ 取值应缺省（调用方按"空即跳过"处理，语义等价）
        for pid, q in live.items():
            if not q:
                self.assertFalse(got.get(pid), f'协议 {pid} 的 Q 为空 ⇒ 缺省即空集语义')

    def test_build_is_idempotent(self):
        call_command('build_protocol_q_cache')
        with open(self.path, encoding='utf-8') as fh:
            first = fh.read()
        call_command('build_protocol_q_cache')
        with open(self.path, encoding='utf-8') as fh:
            second = fh.read()
        self.assertEqual(first, second, '重复构建内容必须一致（不得写时间戳等易变字段）')

    def test_check_passes_when_fresh_and_fails_when_stale(self):
        call_command('build_protocol_q_cache')
        call_command('build_protocol_q_cache', check=True)  # 新鲜 ⇒ 不抛
        # 新增协议 ⇒ 指纹变化 ⇒ --check 必须 exit 1
        Protocol.objects.create(name='Another protocol', slug='q-2', status='published')
        with self.assertRaises(SystemExit):
            call_command('build_protocol_q_cache', check=True)


class QCacheStalenessSafetyTest(TestCase):
    """★ 最关键的一条：缓存陈旧时，**新建的协议仍必须能被推荐**。"""

    def setUp(self):
        self._orig = A._Q_CACHE_PATH
        A._PROTO_Q_CACHE = None

    def tearDown(self):
        A._Q_CACHE_PATH = self._orig
        A._PROTO_Q_CACHE = None

    def test_new_protocol_still_recommended_despite_stale_cache(self):
        # 造一个"陈旧"缓存：指纹与当前库不符（预算是旧快照）
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        _write_cache(p, {'protocol_count': 0, 'max_id': 0}, {})
        A._Q_CACHE_PATH = p
        try:
            Protocol.objects.create(
                name='PCR amplification protocol using primers',
                slug='q-fresh', status='published',
            )
            A._PROTO_Q_CACHE = None
            rows = A.recommend_protocols_for_enrich('pcr primer')
            self.assertEqual(
                len(rows), 1,
                '缓存陈旧时必须回退实时计算 ⇒ 新建协议仍能被推荐（否则新协议永远不可见）',
            )
        finally:
            os.remove(p)
