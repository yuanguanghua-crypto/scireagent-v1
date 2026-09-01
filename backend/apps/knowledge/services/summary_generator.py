"""知识实体 summary 回填 — SummaryGenerator 服务（T1，prompt v2）。

为 ResearchGoal / Application 的空 summary 生成英文摘要。范围守卫：
ACTIVE + 非 fixture + summary=''（draft / archived / deprecated / fixture /
已 summary 一律不动）。

上下文（pilot 实测验证）：
- RG：protocols M2M ≤3（name + objective，objective 截断 ~300 字符）；
  无协议时回退 application_collection ≤3 的 AP name。
- AP：research_goal_collections 反向 M2M ≤2（RG 名 + 每 RG protocols ≤2）。
  AP 无 RG 集合（孤儿）→ 空上下文，交由 prompt v2 名称自描述处理
  （全量池不过滤 RG 集合，覆盖全部空 summary AP，见 test_dry_run）。

prompt v2（宁缺毋滥铁律）：entity name 本身权威自描述，可基于领域知识
解释；上下文只用于佐证具体协议细节；NEVER 编造上下文未提及的协议步骤/
试剂/仪器/引文；仅当名称含糊且上下文无用才输出空字符串。

用法：由 generate_knowledge_summaries 命令调用；extractor 可注入测试桩
（见 tests/test_generate_knowledge_summaries.py 的 FakeExtractor）。
"""
import json

from apps.knowledge.models import Application, ResearchGoal

MAX_OBJ_CHARS = 300

# summary 专用 system prompt（v2：防细节臆造，不防名称自描述）
SYSTEM_PROMPT = (
    'You are a scientific knowledge graph curator. Given a knowledge entity '
    '(a research goal or an application scenario) and its supporting context, '
    'write a concise English summary of that entity.\n'
    'Rules:\n'
    '- Write the summary in English ONLY.\n'
    '- Write exactly 1-2 sentences, 30-60 words in total.\n'
    '- The entity name itself is authoritative and self-describing: you MAY '
    'explain what the named technique or research area is from domain knowledge. '
    'Use the provided context to corroborate and add concrete protocol details '
    'when it is relevant.\n'
    '- NEVER invent specific protocol steps, reagents, instruments, or cited '
    'studies that are absent from the context. Concrete technical details must '
    'come from the context only.\n'
    '- Output an empty string ONLY if the entity name is too vague to describe '
    'on its own AND the context provides no usable information.\n'
    '- Output PLAIN TEXT summary only — no JSON, no markdown, no quotes, no commentary.'
)

# 上下文数量上限（与 pilot 一致）
RG_PROTOCOLS_MAX = 3
RG_AP_FALLBACK_MAX = 3
AP_RGS_MAX = 2
AP_RG_PROTOCOLS_MAX = 2


def trunc(text, n=MAX_OBJ_CHARS):
    text = (text or '').strip()
    return text if len(text) <= n else text[:n].rstrip() + '…'


def _append_context(sources, lines, label, name, objective=''):
    """把一段上下文追加到 sources（JSONL 记录用）与 lines（prompt 用）。"""
    sources.append(label)
    if objective:
        lines.append(f'{label} name: {name}\n  objective: {objective}')
    else:
        lines.append(f'{label} name: {name}')


class SummaryGenerator:
    """summary 生成服务：取数 + 上下文构建 + 单实体摘要。

    extractor 需提供 chat(system_prompt, user_prompt, temperature=0) ->
    纯文本（真实 LLMExtractor 已实现；测试注入 FakeExtractor）。
    """

    def __init__(self, extractor):
        self.extractor = extractor

    def fetch_pool(self):
        """范围守卫取数：ACTIVE + 非 fixture + summary='' 的 RG 与 AP 合并列表。"""
        rgs = list(
            ResearchGoal.objects
            .filter(status=ResearchGoal.Status.ACTIVE,
                    is_test_fixture=False, summary='')
            .order_by('id')
            .prefetch_related('protocols', 'application_collection')
        )
        aps = list(
            Application.objects
            .filter(status=Application.Status.ACTIVE,
                    is_test_fixture=False, summary='')
            .order_by('id')
            .prefetch_related('research_goal_collections__protocols')
        )
        return rgs + aps

    def build_item(self, entity_type, entity):
        """构建单实体任务（主线程预取完数据，worker 只做 LLM 调用）。"""
        sources, lines = [], []
        if entity_type == 'research_goal':
            protocols = list(entity.protocols.all()[:RG_PROTOCOLS_MAX])
            if protocols:
                for p in protocols:
                    _append_context(sources, lines, 'protocol',
                                    p.name, trunc(p.objective))
            else:
                for a in list(entity.application_collection.all()[:RG_AP_FALLBACK_MAX]):
                    _append_context(sources, lines, 'related application', a.name)
        else:  # application — 上下文走 research_goal_collections 反向 M2M（两级）
            for rg in list(entity.research_goal_collections.all()[:AP_RGS_MAX]):
                _append_context(sources, lines, 'research goal', rg.name)
                for p in list(rg.protocols.all()[:AP_RG_PROTOCOLS_MAX]):
                    _append_context(sources, lines, 'protocol',
                                    p.name, trunc(p.objective))
        user_prompt = (
            f'Entity to summarize:\n'
            f'--- type: {entity_type}\n'
            f'--- name: {entity.name}\n'
            '\nSupporting context:\n' + ('\n'.join(lines) if lines else '(none)') +
            '\n\nWrite the summary per the instructions.'
        )
        return {
            'entity_type': entity_type,
            'entity_id': entity.id,
            'entity_name': entity.name,
            'context_sources': sources,
            'user_prompt': user_prompt,
        }

    def summarize_one(self, item):
        """单实体摘要（供并发 worker 调用）：返回 JSONL 行（含 error 字段）。"""
        base = {
            'entity_type': item['entity_type'],
            'entity_id': item['entity_id'],
            'entity_name': item['entity_name'],
            'context_sources': item['context_sources'],
        }
        try:
            raw = self.extractor.chat(SYSTEM_PROMPT, item['user_prompt'],
                                      temperature=0)
            return {**base, 'summary': (raw or '').strip(), 'error': None}
        except Exception as e:  # noqa: BLE001 —— 批级兜底，失败就记录不崩溃
            return {**base, 'summary': '', 'error': str(e)}

    @staticmethod
    def apply_row(row):
        """apply：单行落库（空 summary 不落库——宁缺毋滥保留空态）。"""
        if not row['summary']:
            return 0
        if row['entity_type'] == 'research_goal':
            return ResearchGoal.objects.filter(id=row['entity_id']).update(
                summary=row['summary'])
        return Application.objects.filter(id=row['entity_id']).update(
            summary=row['summary'])

    @staticmethod
    def to_jsonl_line(row):
        return json.dumps(row, ensure_ascii=False)
