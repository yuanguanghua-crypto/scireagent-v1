"""AP → Method 补链 — ApMethodGenerator 服务（T2）。

为无 Method 的 AP 生成实验方法：新建 Method 实体（status=draft、FK 挂 AP、
origin=ai_extracted 诚实标注 AI 生成来源）。范围守卫：ACTIVE + 非 fixture +
无 methods（draft/archived/fixture/已有方法的 AP 一律不动）。

**方案 B（最终，2026-09-04 实测选定，质量优先）**：完整 Method 词表作为
**system_prompt 的固定前缀**，整个跑批期间逐字节不变 → 稳定命中 DeepSeek 上下文
硬盘缓存（命中 ¥0.05/百万 vs 未命中 ¥1.5/百万，差 30 倍）。实测对照 12 条真实 AP：
- 全词表：input 18,374 tok / 命中率 98.4% / 单次 ¥0.00141 / 外推 16,136 条 ≈ ¥22.8
- top-50 候选：input 467 tok / 0% 命中 / 单次 ¥0.00075 / 外推 ≈ ¥12.1

全词表单次贵约 88%，但召回率 100% vs 93%、产出**领域真实方法名**
（Repli-seq / BrdU Labeling）而非通用聚类（K-Means）；T2 输出直接喂 T3，方法名
不准会沿链路放大 → 选质量优先。

词表为实例级快照（`lexicon()`），同一进程内稳定；`sorted()` 保证顺序固定 → system
前缀逐字节不变，缓存命中可复现。`extractor` 可注入测试桩（见 tests 的 FakeExtractor）。
"""
import json

from apps.knowledge.models import Application, Method, OriginChoices
from apps.knowledge.services.llm_extractor import _strip_fence

MAX_OBJ_CHARS = 300


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

    def __init__(self, extractor):
        self.extractor = extractor
        # 实例级缓存：build_item（主线程）预热，worker 子线程只读缓存，
        # 规避 pytest 事务测试下子线程读不到未提交数据。
        self._lexicon = None
        self._system_prompt = None

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

    def system_prompt(self):
        """完整词表作为**固定前缀**（2026-09-04 实测选定，取代 top-50 候选）。

        实测对照（12 条真实 AP，明细见 C:/tmp/cache_probe.log）：

        | 结构                 | input      | 缓存命中率        | 单次成本   | 外推 16,136 条 |
        |----------------------|------------|-------------------|-----------|----------------|
        | top-50 候选（旧）    | 467 tokens | 0%（前缀早分叉）  | ¥0.00075  | ¥12.1          |
        | **全词表固定前缀**   | 18,374 tok | **98.4%**（第3条起稳定） | ¥0.00141 | ¥22.8     |

        全词表单次贵约 88%，但**召回率 100% vs 93%**，实测质量明显更好：
        对 AP「Clustering of Replication Timing Profiles」，top-50 给
        "K-Means Clustering"（通用聚类），全词表给
        "Repli-seq / BrdU Labeling / Flow Cytometry"（领域真实方法名）。
        T2 产出直接喂 T3，方法名不准会沿链路放大 → 宁可贵一点也要准。

        吃缓存的前提：本字符串在整个跑批期间**逐字节不变**。
        - lexicon() 是实例级快照 → 同一进程内词表固定（T2 新建的 Method 不会
          在本次跑批中混入，下次启动才是新快照）
        - sorted() 保证顺序稳定
        故 system 成为稳定的公共前缀，系统在识别后按 ¥0.05/百万 计价。
        """
        if self._system_prompt is None:
            lex = sorted(self.lexicon())
            self._system_prompt = (
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
        return self._system_prompt

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

        词表（lexicon）在主线程预热，worker 子线程只读缓存、只做 LLM 调用，
        规避 pytest 事务测试下子线程读不到未提交数据（T3 已踩同款坑）。
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
                self.system_prompt(),
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
