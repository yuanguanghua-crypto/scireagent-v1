"""Protocol → Method 补链 — ProtocolMethodGenerator 服务（T3）。

为无 Method 关联的协议（MethodProtocol 桥为空）补实验方法关联：在**规范方法词表**
（Method 表排除 ai_extracted + 排除 archived 的 name 集合）上做**闭集分类**，
新建 MethodProtocol 桥表行（evidence_source='llm_reviewed'），**不新建 Method 行**。

为何是闭集：T2 已为每个 AP 新建 draft Method（全表炸到 66k），但那些是 AP 实例级方法，
不是规范方法分类法。T3 只把协议挂到规范方法分类法（~90 个），桥表
unique_together(method, protocol) 防重。

词表为实例级快照（lexicon()），同进程固定 → system 前缀逐字节不变命中 DeepSeek 上下文缓存。
"""
import json

from apps.knowledge.models import Protocol, Method, OriginChoices
from apps.bridges.models import MethodProtocol
from apps.knowledge.services.llm_extractor import _strip_fence

MAX_OBJ_CHARS = 400


def trunc(text, n=MAX_OBJ_CHARS):
    text = (text or '').strip()
    return text if len(text) <= n else text[:n].rstrip() + '…'


class ProtocolMethodGenerator:
    """Protocol 方法补链服务：取数 + 闭集分类 prompt + 单协议识别 + 落库桥表。

    extractor 需提供 chat(system_prompt, user_prompt, temperature=0) -> 纯文本
    （真实 LLMExtractor 已实现；测试注入 FakeExtractor）。
    """

    def __init__(self, extractor):
        self.extractor = extractor
        # 实例级缓存：build_item（主线程）预热，worker 子线程只读缓存。
        self._lexicon = None
        self._system_prompt = None
        self._canonical_map = None  # name/canonical-name-lowered -> 规范 Method 对象

    def lexicon(self):
        """规范方法词表（闭集）：Method 排除 ai_extracted + 排除 archived 的 name 集。"""
        if self._lexicon is None:
            self._lexicon = set(
                Method.objects.exclude(origin=OriginChoices.AI_EXTRACTED)
                .exclude(status=Method.Status.ARCHIVED)
                .values_list('name', flat=True)
            )
        return self._lexicon

    def canonical_map(self):
        """name -> 规范 Method 对象（排除 ai_extracted + archived），用于落库解析。

        同时建小写键兜底（LLM 偶尔改大小写），提升召回不破正确性。
        """
        if self._canonical_map is None:
            m = {}
            for meth in (Method.objects.exclude(origin=OriginChoices.AI_EXTRACTED)
                         .exclude(status=Method.Status.ARCHIVED)):
                m[meth.name] = meth
                m[meth.name.lower()] = meth
            self._canonical_map = m
        return self._canonical_map

    def system_prompt(self):
        """完整规范词表作为**固定前缀**（与 T2 同策略，命中 DeepSeek 上下文缓存）。"""
        if self._system_prompt is None:
            lex = sorted(self.lexicon())
            self._system_prompt = (
                'You are a scientific knowledge graph curator. Given a laboratory protocol '
                '(its name and objective), identify which experimental METHODS from the fixed '
                'candidate list below the protocol uses.\n'
                'Rules:\n'
                '- You MUST only select method names that appear EXACTLY in the candidate list. '
                'Do NOT invent, rephrase, abbreviate, or propose new method names.\n'
                '- Output 1-4 method names, most relevant first.\n'
                '- If the protocol objective is too vague to determine any method, '
                'output {"methods": []}.\n'
                '- Output STRICT JSON only, no markdown, no commentary: '
                '{"methods": ["Name One", "Name Two"]}\n'
                f'\nCandidate method names ({len(lex)} entries):\n'
                + '\n'.join(f'- {n}' for n in lex)
            )
        return self._system_prompt

    def fetch_pool(self):
        """范围守卫取数：published + 无 MethodProtocol 桥的协议。"""
        return list(
            Protocol.objects.filter(status='published')
            .exclude(method_protocols__isnull=False)
            .order_by('id')
        )

    def build_item(self, protocol):
        """构建单协议任务（主线程预取完数据，worker 只做 LLM 调用）。"""
        user_prompt = (
            f'Protocol to analyze:\n'
            f'--- name: {protocol.name}\n'
            f'objective: {trunc(protocol.objective)}\n'
        )
        if getattr(protocol, 'principle', None):
            user_prompt += f'principle: {trunc(protocol.principle)}\n'
        user_prompt += '\nIdentify the experimental methods per the instructions.'
        return {
            'protocol_id': protocol.id,
            'protocol_name': protocol.name,
            'user_prompt': user_prompt,
        }

    def probe_one(self, item):
        """单协议方法识别（供并发 worker）：返回 JSONL 行（含 error 字段）。"""
        base = {
            'protocol_id': item['protocol_id'],
            'protocol_name': item['protocol_name'],
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

    def apply_row(self, row):
        """apply：为该协议在规范词表内建 MethodProtocol 桥（get_or_create 幂等）。

        返回 (created, skipped_out_of_lexicon)。落库解析用 self.canonical_map()。
        """
        names = [m['name'] for m in row.get('methods') or [] if m.get('name')]
        if not names:
            return 0, 0
        proto = Protocol.objects.get(pk=row['protocol_id'])
        cmap = self.canonical_map()
        created = 0
        skipped = 0
        for name in names:
            meth = cmap.get(name) or cmap.get(name.lower())
            if not meth:
                skipped += 1
                continue
            _, was_created = MethodProtocol.objects.get_or_create(
                method=meth, protocol=proto,
                defaults={'evidence_source': 'llm_reviewed'},
            )
            if was_created:
                created += 1
        return created, skipped
