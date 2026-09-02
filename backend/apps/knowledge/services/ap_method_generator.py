"""AP → Method 补链 — ApMethodGenerator 服务（T2）。

为无 Method 的 AP 生成实验方法：新建 Method 实体（status=draft、FK 挂 AP、
origin=ai_extracted 诚实标注 AI 生成来源）。范围守卫：ACTIVE + 非 fixture +
无 methods（draft/archived/fixture/已有方法的 AP 一律不动）。

词表：Method 表 ACTIVE+DRAFT 的 name 集合，**每次调用实时查询** → 全量过程
中新名 Method 创建后自动进词表（词表自增，后续批次与 T3 复用）。

prompt（探针 ap_method_probe.py 实测版）：优先从词表选 1-3 个方法名；词表无
合适项才允许新名（规范化英文）；应用模糊且上下文无信息 → 空数组（宁缺毋滥）。
LLM 输出 STRICT JSON：{"methods": ["Name One", "Name Two"]}。

用法：由 generate_ap_methods 命令调用；extractor 可注入测试桩
（见 tests/test_generate_ap_methods.py 的 FakeExtractor）。
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

    @classmethod
    def lexicon(cls):
        """词表：Method 表 ACTIVE+DRAFT 的 name 集合（实时查询，随全量自增）。"""
        return set(
            Method.objects.exclude(status=Method.Status.ARCHIVED)
            .values_list('name', flat=True)
        )

    def system_prompt(self):
        lex = sorted(self.lexicon())
        return (
            'You are a scientific knowledge graph curator. Given an application '
            'scenario (an experimental technique or assay) and its supporting context, '
            'identify the most common experimental methods used to perform it.\n'
            'Rules:\n'
            '- Output 1-3 method names, most relevant first.\n'
            '- PREFER names from the provided method lexicon when one fits well.\n'
            '- If no lexicon entry fits, you MAY propose a concise new method name '
            '(a standard experimental method name, capitalized).\n'
            '- NEVER invent methods unrelated to the application.\n'
            '- Output STRICT JSON only, no markdown, no commentary: '
            '{"methods": ["Name One", "Name Two"]}\n'
            '- If the application is too vague and the context provides no clue, '
            'output {"methods": []}.\n'
            f'\nMethod lexicon ({len(lex)} entries):\n'
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
        """构建单 AP 任务（主线程预取完数据，worker 只做 LLM 调用）。"""
        sources, lines = [], []
        for rg in list(ap.research_goal_collections.all()[:2]):
            _append_context(sources, lines, 'research goal', rg.name)
            for p in list(rg.protocols.all()[:2]):
                _append_context(sources, lines, 'protocol',
                                p.name, trunc(p.objective))
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
            raw = self.extractor.chat(self.system_prompt(), item['user_prompt'],
                                      temperature=0)
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
