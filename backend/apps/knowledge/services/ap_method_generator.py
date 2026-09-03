"""AP → Method 补链 — ApMethodGenerator 服务（T2）。

为无 Method 的 AP 生成实验方法：新建 Method 实体（status=draft、FK 挂 AP、
origin=ai_extracted 诚实标注 AI 生成来源）。范围守卫：ACTIVE + 非 fixture +
无 methods（draft/archived/fixture/已有方法的 AP 一律不动）。

**方案 B（2026-09-03 成本治理）**：原实现把**全量词表**塞进每次 system_prompt
（词表已 21,302 条 ≈ 单次 16.9 万 input tokens，是成本失控根因）。现改为
**关键词召回 top-50 候选**进 prompt：单次 ~800 tokens，**成本降约 99.5%**，
且候选更精准（LLM 不再被 2 万条无关词表干扰）。造新名规则保留——
候选只是"优先复用"的参考，不是封闭集合（与 T3 的封闭选名不同）。

词表/倒排为实例级缓存：主线程（build_item）预热，并发 worker 只做 LLM 调用，
规避 pytest 事务测试下子线程读不到未提交数据（T3 已踩同款坑）。

用法：由 generate_ap_methods 命令调用；extractor 可注入测试桩
（见 tests/test_generate_ap_methods.py 的 FakeExtractor）。
"""
import json
import re

from apps.knowledge.models import Application, Method, OriginChoices
from apps.knowledge.services.llm_extractor import _strip_fence

MAX_OBJ_CHARS = 300

# 召回分词停用词（AP/协议标题里的高频无信息词，与 T3 同口径）
STOP_WORDS = {
    'protocol', 'protocols', 'method', 'methods', 'the', 'a', 'an', 'of', 'and',
    'for', 'to', 'in', 'with', 'on', 'from', 'by', 'at', 'as', 'using', 'use',
    'via', 'et', 'al', 'its', 'their', 'this', 'that', 'into', 'after', 'before',
    'between', 'during', 'across', 'under', 'over', 'through', 'based', 'study',
    'studies', 'analysis', 'analyses', 'data', 'cell', 'cells', 'mouse', 'mice',
    'human', 'gene', 'genes', 'protein', 'proteins', 'rna', 'dna',
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def trunc(text, n=MAX_OBJ_CHARS):
    text = (text or '').strip()
    return text if len(text) <= n else text[:n].rstrip() + '…'


def _append_context(sources, lines, label, name, objective=''):
    sources.append(label)
    if objective:
        lines.append(f'{label} name: {name}\n  objective: {objective}')
    else:
        lines.append(f'{label} name: {name}')


class ApMethodGenerator:
    """AP 方法补链服务：取数 + 上下文构建 + 单 AP 方法识别 + 落库。

    extractor 需提供 chat(system_prompt, user_prompt, temperature=0) ->
    纯文本（真实 LLMExtractor 已实现；测试注入 FakeExtractor）。
    """

    # 候选召回上限（方案 B：prompt 只带 top-K 候选，不再塞全量词表）
    TOP_K = 50

    def __init__(self, extractor):
        self.extractor = extractor
        # 实例级缓存：build_item（主线程）预热，worker 子线程只读缓存，
        # 规避 pytest 事务测试下子线程读不到未提交数据。
        self._lexicon = None
        self._inverted = None

    def lexicon(self):
        """词表：Method 表（排除 archived）的 name 集合。

        实例级缓存（首次查询后快照）；主线程预热，worker 复用。
        """
        if self._lexicon is None:
            self._lexicon = set(
                Method.objects.exclude(status=Method.Status.ARCHIVED)
                .values_list('name', flat=True)
            )
        return self._lexicon

    # ---------- 候选召回（方案 B：词表瘦身） ----------

    @classmethod
    def _tokenize(cls, text):
        toks = [t for t in TOKEN_RE.findall((text or '').lower())
                if t not in STOP_WORDS and len(t) > 2 and not t.isdigit()]
        return list(set(toks))

    def _inverted_index(self):
        """token -> [method name] 倒排（惰性构建并缓存）。"""
        if self._inverted is None:
            inverted = {}
            for name in self.lexicon():
                for tok in self._tokenize(name):
                    inverted.setdefault(tok, []).append(name)
            self._inverted = inverted
        return self._inverted

    def recall(self, query, top_k=None):
        """关键词召回：query 分词 → token 倒排 → 词重合打分 → top-K 方法名。

        召回为空是合法的（此时仍调 LLM，只是没有词表参考，可自由造新名）。
        """
        top_k = top_k or self.TOP_K
        if not self.lexicon():
            return []
        inverted = self._inverted_index()
        scores = {}
        for tok in self._tokenize(query):
            for name in inverted.get(tok, ()):
                scores[name] = scores.get(name, 0) + 1
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [name for name, _ in ranked[:top_k]]

    def system_prompt(self, candidates):
        """候选为召回的 top-K 方法名（不是全量词表）。"""
        lex = sorted(candidates or [])
        return (
            'You are a scientific knowledge graph curator. Given an application '
            'scenario (an experimental technique or assay) and its supporting context, '
            'identify the most common experimental methods used to perform it.\n'
            'Rules:\n'
            '- Output 1-3 method names, most relevant first.\n'
            '- PREFER names from the candidate method list below when one fits well.\n'
            '- If no candidate fits, you MAY propose a concise new method name '
            '(a standard experimental method name, capitalized).\n'
            '- NEVER invent methods unrelated to the application.\n'
            '- Output STRICT JSON only, no markdown, no commentary: '
            '{"methods": ["Name One", "Name Two"]}\n'
            '- If the application is too vague and the context provides no clue, '
            'output {"methods": []}.\n'
            f'\nCandidate method names ({len(lex)} entries):\n'
            + '\n'.join(f'- {n}' for n in lex)
        )

    def fetch_pool(self):
        """范围守卫取数：ACTIVE + 非 fixture + 无 methods 的 AP。"""
        return list(
            Application.objects
            .filter(status=Application.Status.ACTIVE, is_test_fixture=False)
            .exclude(methods__isnull=False)
            .order_by('id')
            .prefetch_related('research_goal_collections__protocols')
        )

    def build_item(self, ap):
        """构建单 AP 任务（主线程预取完数据，worker 只做 LLM 调用）。

        候选召回也在主线程完成：词表缓存 + 倒排索引在此预热，
        worker 子线程不再查库（LLM 调用是唯一 I/O）。
        """
        sources, lines, query_parts = [], [], [ap.name]
        for rg in list(ap.research_goal_collections.all()[:2]):
            _append_context(sources, lines, 'research goal', rg.name)
            for p in list(rg.protocols.all()[:2]):
                _append_context(sources, lines, 'protocol',
                                p.name, trunc(p.objective))
                query_parts.append(p.name)
        user_prompt = (
            f'Application to analyze:\n'
            f'--- name: {ap.name}\n'
            '\nSupporting context:\n' + ('\n'.join(lines) if lines else '(none)') +
            '\n\nIdentify the experimental methods per the instructions.'
        )
        return {
            'ap_id': ap.id,
            'ap_name': ap.name,
            'context_sources': sources,
            'user_prompt': user_prompt,
            'candidates': self.recall(' '.join(query_parts)),
        }

    def probe_one(self, item):
        """单 AP 方法识别（供并发 worker）：返回 JSONL 行（含 error 字段）。"""
        base = {
            'ap_id': item['ap_id'],
            'ap_name': item['ap_name'],
            'context_sources': item['context_sources'],
        }
        try:
            raw = self.extractor.chat(
                self.system_prompt(item.get('candidates') or []),
                item['user_prompt'], temperature=0,
            )
            data = json.loads(_strip_fence(raw))
            names = [str(n).strip()[:255] for n in (data.get('methods') or [])
                     if str(n).strip()]
        except Exception as e:  # noqa: BLE001 —— 批级兜底，失败就记录不崩溃
            return {**base, 'methods': [], 'error': str(e)}
        lex = self.lexicon()
        return {
            **base,
            'methods': [{'name': n, 'in_lexicon': n in lex} for n in names],
            'error': None,
        }

    @staticmethod
    def apply_row(row):
        """apply：为该 AP 新建 Method（空方法列表不落库）。返回新建数。"""
        names = [m['name'] for m in row.get('methods') or [] if m.get('name')]
        if not names:
            return 0
        ap = Application.objects.get(pk=row['ap_id'])
        for name in names:
            Method.objects.create(
                name=name,
                application=ap,
                status=Method.Status.DRAFT,
                origin=OriginChoices.AI_EXTRACTED,
                origin_detail='T2 AP method backfill (llm)',
            )
        return len(names)
