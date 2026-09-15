"""TDD for backfill_reference_fields 管理命令（PubMed esummary → Reference 字段回填）。

契约（见 apps/bridges/management/commands/backfill_reference_fields.py）：
- 只处理有 pmid 的 Reference；默认 dry-run 绝不写库，--apply 才写。
- 只填空字段，绝不覆盖已有非空值（宁缺毋滥）。
- year 从 pubdate 取开头 4 位数字；doi 优先 elocationid('doi:...') 再 articleids(idtype=doi)；
  authors 取前 20 位用 ', ' 连接；journal 取 source。
- 长度守卫：doi<=100（超长丢弃）、journal<=255（超长截断），与 adopt_cached_evidence._normalize 口径一致。
- Reference.doi 唯一：回填冲突时跳过 doi，其余字段照常写，不整批失败。
- --limit / --ids 生效。

全部用例用 monkeypatch 打桩 core.datasource_client.request_with_resilience，
伪造带 .raise_for_status() / .json() 的 response 对象，**禁止发真实网络请求**。
"""
import io

import core.datasource_client
from django.core.management import call_command
from django.test import TestCase

from apps.knowledge.models import Reference


# ── 伪造 response（带 .raise_for_status() 与 .json()）─────────────────
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _make_fake(payload):
    """返回一个伪造的 request_with_resilience：按 pmid 回灌 esummary 数据。

    payload: {pmid: entry_dict}。每批请求只看 params['id'] 里的 pmid，
    从 payload 取对应 entry，拼成 {"result": {"uids": [...], pmid: entry, ...}}。
    """
    def _fake(method, url, source="pubmed", timeout=20, retries=3,
              params=None, **kwargs):
        params = params or {}
        ids = [i for i in (params.get("id") or "").split(",") if i]
        result = {"uids": ids}
        for pid in ids:
            if pid in payload:
                result[pid] = payload[pid]
        return _FakeResp({"result": result})
    return _fake


def _entry(pmid, *, pubdate="", elocationid="", authors=None, source="",
           articleids=None):
    return {
        "uid": pmid,
        "pubdate": pubdate,
        "elocationid": elocationid,
        "authors": [{"name": n} for n in (authors or [])],
        "source": source,
        "articleids": articleids or [],
    }


class BackfillReferenceFieldsTests(TestCase):
    # monkeypatch 目标固定为 core.datasource_client.request_with_resilience
    PATCH_TARGET = "core.datasource_client.request_with_resilience"

    def _run(self, *args, **opts):
        out = io.StringIO()
        call_command('backfill_reference_fields', *args, stdout=out, **opts)
        return out.getvalue()

    def _mk(self, **kw):
        defaults = dict(title="T", authors="", journal="", year=None,
                        doi=None, pmid=None)
        defaults.update(kw)
        return Reference.objects.create(**defaults)

    def _stub(self, monkeypatch, payload):
        monkeypatch.setattr(
            core.datasource_client, 'request_with_resilience',
            _make_fake(payload))

    # ---- 1. dry-run 绝不写库 ----
    def test_dry_run_never_writes(self, monkeypatch):
        ref = self._mk(pmid="111")
        payload = {"111": _entry("111", pubdate="2024 Jan",
                                 elocationid="doi:10.1/x",
                                 authors=["A B"], source="Nature")}
        self._stub(monkeypatch, payload)
        out = self._run()
        ref.refresh_from_db()
        self.assertIsNone(ref.year)
        self.assertIsNone(ref.doi)
        self.assertEqual(ref.authors, "")
        self.assertEqual(ref.journal, "")
        self.assertIn("dry-run", out)

    # ---- 2. --apply 只填空字段，已有非空值不被覆盖 ----
    def test_apply_fills_only_empty_fields(self, monkeypatch):
        empty = self._mk(pmid="111")
        full = self._mk(pmid="222", year=2001, doi="10.exist/1",
                        authors="Keep Me", journal="KeepJ")
        payload = {
            "111": _entry("111", pubdate="2024", elocationid="doi:10.new/1",
                          authors=["X Y"], source="Nat"),
            "222": _entry("222", pubdate="1999", elocationid="doi:10.other/9",
                          authors=["Z"], source="OtherJ"),
        }
        self._stub(monkeypatch, payload)
        out = self._run('--apply')
        empty.refresh_from_db()
        full.refresh_from_db()
        self.assertEqual(empty.year, 2024)
        self.assertEqual(empty.doi, "10.new/1")
        self.assertEqual(empty.authors, "X Y")
        self.assertEqual(empty.journal, "Nat")
        # 已有值一个都不能变
        self.assertEqual(full.year, 2001)
        self.assertEqual(full.doi, "10.exist/1")
        self.assertEqual(full.authors, "Keep Me")
        self.assertEqual(full.journal, "KeepJ")
        self.assertIn("apply", out)

    # ---- 3. pubdate 三种格式解析 ----
    def test_pubdate_formats(self, monkeypatch):
        a = self._mk(pmid="1")
        b = self._mk(pmid="2")
        c = self._mk(pmid="3")
        d = self._mk(pmid="4")
        payload = {
            "1": _entry("1", pubdate="2024"),
            "2": _entry("2", pubdate="2024 Jan"),
            "3": _entry("3", pubdate="2023 Dec 15"),
            "4": _entry("4", pubdate=""),          # 解析不出 → 不动
        }
        self._stub(monkeypatch, payload)
        self._run('--apply')
        for ref, want in ((a, 2024), (b, 2024), (c, 2023)):
            ref.refresh_from_db()
            self.assertEqual(ref.year, want)
        d.refresh_from_db()
        self.assertIsNone(d.year)

    # ---- 4. doi 两路来源（elocationid / articleids）----
    def test_doi_from_elocationid_and_articleids(self, monkeypatch):
        a = self._mk(pmid="1")
        b = self._mk(pmid="2")
        payload = {
            "1": _entry("1", elocationid="doi:10.1/loc"),
            "2": _entry("2", elocationid="",
                        articleids=[{"idtype": "doi", "value": "10.2/aid"}]),
        }
        self._stub(monkeypatch, payload)
        self._run('--apply')
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.doi, "10.1/loc")
        self.assertEqual(b.doi, "10.2/aid")

    # ---- 5. doi 冲突 → 跳过 doi，其余照写，不报错 ----
    def test_doi_conflict_skipped_but_other_fields_written(self, monkeypatch):
        target = self._mk(pmid="111")
        self._mk(pmid="222", doi="10.dup/1")
        payload = {"111": _entry("111", pubdate="2020",
                                 elocationid="doi:10.dup/1",
                                 authors=["A"], source="J")}
        self._stub(monkeypatch, payload)
        self._run('--apply')
        target.refresh_from_db()
        self.assertIsNone(target.doi)          # 冲突 → 不写 doi
        self.assertEqual(target.year, 2020)    # 其余字段照常写
        self.assertEqual(target.authors, "A")
        self.assertEqual(target.journal, "J")

    # ---- 6a. --ids 只处理指定行 ----
    def test_ids_filter(self, monkeypatch):
        a = self._mk(pmid="111")
        b = self._mk(pmid="222")
        payload = {
            "111": _entry("111", pubdate="2024"),
            "222": _entry("222", pubdate="2024"),
        }
        self._stub(monkeypatch, payload)
        self._run('--apply', ids=str(b.id))
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertIsNone(a.year)
        self.assertEqual(b.year, 2024)

    # ---- 6b. --limit 生效（按 id 升序取前 N）----
    def test_limit(self, monkeypatch):
        a = self._mk(pmid="111")
        b = self._mk(pmid="222")
        payload = {
            "111": _entry("111", pubdate="2024"),
            "222": _entry("222", pubdate="2024"),
        }
        self._stub(monkeypatch, payload)
        self._run('--apply', limit=1)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.year, 2024)
        self.assertIsNone(b.year)

    # ---- 7. 无 pmid 的行不在目标集合（不发请求）----
    def test_rows_without_pmid_skipped(self, monkeypatch):
        # 用真实 spy 替换，确认根本没发网络请求
        sentinel = {"called": 0}
        real = core.datasource_client.request_with_resilience

        def _spy(*args, **kwargs):
            sentinel["called"] += 1
            return real(*args, **kwargs)
        monkeypatch.setattr(core.datasource_client, 'request_with_resilience', _spy)
        no_pmid = self._mk(title="NoPmid", year=None)
        out = self._run('--apply')
        no_pmid.refresh_from_db()
        self.assertIsNone(no_pmid.year)
        self.assertIn("有 pmid 的 Reference：0", out)
        self.assertEqual(sentinel["called"], 0)

    # ---- 8. --ids 非法输入 → 友好报错，不写库 ----
    def test_invalid_ids_reports_error(self, monkeypatch):
        self._mk(pmid="111")
        out = io.StringIO()
        # 非法 --ids 在解析即报错，不应触达网络
        monkeypatch.setattr(core.datasource_client, 'request_with_resilience',
                            _make_fake({}))
        call_command('backfill_reference_fields', '--ids', 'a,b',
                     stdout=out, stderr=out)
        self.assertIn("--ids", out.getvalue())

    # ---- 9. 批次失败不阻塞（异常被吞、只报错）----
    def test_batch_failure_does_not_crash(self, monkeypatch):
        self._mk(pmid="111")

        def _boom(*args, **kwargs):
            raise RuntimeError("boom")
        monkeypatch.setattr(core.datasource_client, 'request_with_resilience', _boom)
        # 不应抛异常
        self._run('--apply')

    # ---- 10. 报告含"将回填"预测 + (apply) before→after ----
    def test_report_contains_predictions_and_before_after(self, monkeypatch):
        self._mk(pmid="111", year=None, doi=None, authors="", journal="")
        self._mk(pmid="222", year=None, doi=None, authors="", journal="")
        payload = {
            "111": _entry("111", pubdate="2020", elocationid="doi:10.a/1",
                          authors=["P Q"], source="J1"),
            "222": _entry("222", pubdate="2021", elocationid="doi:10.a/2",
                          authors=["R S"], source="J2"),
        }
        self._stub(monkeypatch, payload)
        out = self._run('--apply')
        # 预测分列
        self.assertIn("year", out)
        self.assertIn("doi", out)
        self.assertIn("authors", out)
        self.assertIn("journal", out)
        # 查询批数 + before→after
        self.assertIn("批", out)
        self.assertIn("->", out)
