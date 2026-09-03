# -*- coding: utf-8 -*-
"""ProtocolMethodGenerator —— T3：LLM 为悬空协议补 Method 关联（词表召回 + 候选选择）。

设计（对齐用户 2026-09-01 决策链「L1 词典效果不行再走 LLM」；L1 已实证耗尽：
annotate_method_protocols 对剩余 2,290 悬空只剩 6 条 STRONG 命中，且样本有错配风险）：

1. 词表 = Method 表（排除 deprecated/archived + `__` 前缀 e2e 垃圾）的 name，运行期实时查。
2. 召回：协议名分词 → token 倒排命中 → 词重合打分取 top-K（K=15）。
   召回为空 → 直接真空（不调 LLM，宁 miss + 省钱）。
3. LLM 只允许从候选编号选（返回 {"method_ids": [..]}），服务端映射回词表 name；
   越界/重复/非候选一律拒绝 —— 双保险宁 miss 不错配。
4. 落库：MethodProtocol bulk_create(ignore_conflicts=True)（unique_together=(method, protocol)），
   evidence_source='llm_reviewed'、explicit=False、status='active'。
5. **T2 教训**：任何异常（含 HTTP 429）→ error 行（methods 空），由命令侧排除出 checkpoint done，
   重启自动重跑，杜绝静默数据缺口。
"""
import json
import re

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, Protocol

# 召回分词停用词（协议标题里的高频无信息词）
STOP_WORDS = {
    'protocol', 'protocols', 'method', 'methods', 'the', 'a', 'an', 'of', 'and',
    'for', 'to', 'in', 'with', 'on', 'from', 'by', 'at', 'as', 'using', 'use',
    'via', 'et', 'al', 'its', 'their', 'this', 'that', 'into', 'after', 'before',
    'between', 'during', 'across', 'under', 'over', 'through', 'based', 'study',
    'studies', 'analysis', 'analyses', 'data', 'cell', 'cells', 'mouse', 'mice',
    'human', 'gene', 'genes', 'protein', 'proteins', 'rna', 'dna',
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


class ProtocolMethodGenerator:
    """T3 服务：悬空协议 → 词表召回 → LLM 选名 → 建 MethodProtocol 桥。"""

    MAX_OBJ_CHARS = 200
    TOP_K = 15

    def __init__(self, extractor):
        self.extractor = extractor
        # 词表/倒排实例级缓存：命令 handle() 主线程预热一次后，
        # 并发 worker 子线程直接复用——规避 pytest 事务测试下
        # 子线程新连接读不到未提交数据（召回被误判为空的根因）。
        # T3 只建桥不新建 Method，运行期词表不变，快照安全。
        self._lexicon = None
        self._inverted = None

    # ---------- 词表与召回 ----------

    def lexicon(self):
        """受控方法词表：ACTIVE+DRAFT 的 Method name，排除 __ 前缀 e2e 垃圾。

        实例级缓存（首次查询后快照）；命令启动时主线程预热，worker 复用。
        """
        if self._lexicon is None:
            qs = Method.objects.exclude(
                status__in=[Method.Status.DEPRECATED, Method.Status.ARCHIVED]
            ).exclude(name__startswith='__')
            self._lexicon = set(qs.values_list('name', flat=True))
        return self._lexicon

    def _inverted_index(self):
        """token -> [method name] 倒排（惰性构建并缓存）。"""
        if self._inverted is None:
            inverted = {}
            for name in self.lexicon():
                for tok in self._tokenize(name):
                    inverted.setdefault(tok, []).append(name)
            self._inverted = inverted
        return self._inverted

    @classmethod
    def _tokenize(cls, text):
        toks = [t for t in TOKEN_RE.findall((text or '').lower())
                if t not in STOP_WORDS and len(t) > 2 and not t.isdigit()]
        return list(set(toks))

    def candidates(self, protocol_name, top_k=None):
        """协议名分词 → token 倒排 → 词重合打分 → top-K 候选。"""
        top_k = top_k or self.TOP_K
        if not self.lexicon():
            return []
        inverted = self._inverted_index()
        # 协议 token 打分
        scores = {}
        for tok in self._tokenize(protocol_name):
            for name in inverted.get(tok, ()):
                scores[name] = scores.get(name, 0) + 1
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{'name': name, 'score': score} for name, score in ranked[:top_k]]

    # ---------- 池与上下文 ----------

    def fetch_pool(self):
        """悬空协议：PUBLISHED 且无 MethodProtocol 桥。"""
        return list(
            Protocol.objects.filter(status=Protocol.PublicationStatus.PUBLISHED)
            .exclude(method_protocols__isnull=False)
            .only('id', 'name', 'objective')
            .order_by('id')
        )

    def build_item(self, proto):
        return {
            'protocol_id': proto.id,
            'protocol_name': proto.name,
            'objective': (proto.objective or '')[:self.MAX_OBJ_CHARS],
        }

    # ---------- LLM ----------

    def system_prompt(self, candidate_names):
        lines = '\n'.join(
            f'  {i}: {name}' for i, name in enumerate(candidate_names)
        )
        return (
            '你是科研实验方法匹配助手。给定一个实验协议，从下方候选方法列表中选出最匹配的'
            '方法（可多选，最多 3 个）。\n'
            '铁律：只允许从候选编号中选择，严禁编造不在列表中的方法名；'
            '若没有任何候选合适，返回空数组（宁缺毋滥）。\n'
            f'候选方法列表：\n{lines}\n'
            '只输出 JSON，格式 {"method_ids": [0, 2]}。'
        )

    @staticmethod
    def _parse_method_ids(content):
        """解析 LLM 输出；只接受合法编号列表，其他一律视为空（宁 miss）。"""
        text = (content or '').strip()
        # 去除可能的代码围栏
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            return []
        raw = payload.get('method_ids', []) if isinstance(payload, dict) else []
        if not isinstance(raw, list):
            return []
        ids = []
        for v in raw:
            if isinstance(v, int) and v >= 0 and v not in ids:
                ids.append(v)
            elif isinstance(v, str) and v.isdigit() and int(v) not in ids:
                ids.append(int(v))
        return ids

    def probe_one(self, item):
        """单条：召回 → （空则真空）→ LLM 选名 → 落库名列表。异常 → error 行。"""
        try:
            cands = self.candidates(item['protocol_name'])
            if not cands:
                return {
                    'protocol_id': item['protocol_id'],
                    'protocol_name': item['protocol_name'],
                    'method_names': [],
                    'candidate_names': [],
                    'error': None,
                }
            names = [c['name'] for c in cands]
            user_prompt = (
                f"Protocol name: {item['protocol_name']}\n"
                f"Objective: {item.get('objective') or '(none)'}"
            )
            content = self.extractor.chat(
                self.system_prompt(names), user_prompt, temperature=0,
            )
            picked = []
            for i in self._parse_method_ids(content):
                if 0 <= i < len(names) and names[i] not in picked:
                    picked.append(names[i])
            return {
                'protocol_id': item['protocol_id'],
                'protocol_name': item['protocol_name'],
                'method_names': picked,
                'candidate_names': names,
                'error': None,
            }
        except Exception as exc:  # 网络/429/超时 → error 行（命令侧不进 done）
            return {
                'protocol_id': item['protocol_id'],
                'protocol_name': item['protocol_name'],
                'method_names': [],
                'candidate_names': [],
                'error': str(exc)[:300],
            }

    # ---------- 落库 ----------

    def apply_row(self, row):
        """按 method_names 建桥；空列表不建。返回新建数。"""
        if not row.get('method_names'):
            return 0
        pid = row['protocol_id']
        protocol = Protocol.objects.get(pk=pid)
        objs = []
        for order, name in enumerate(row['method_names']):
            # 同名 Method 可能有多条（T2 为每个 AP 各建一条：实测 21,302 行 /
            # 1,742 个唯一名）。用 filter().first() 而非 get()，否则
            # MultipleObjectsReturned 会让整批崩溃（且它不被 DoesNotExist 捕获）。
            # 取 id 最小的一条：同名方法指向同一实验方法，桥的语义等价。
            method = Method.objects.filter(
                name=name,
                status__in=[Method.Status.DRAFT, Method.Status.ACTIVE],
            ).order_by('id').first()
            if method is None:
                continue  # 词表已变（如归档）→ 宁 miss
            objs.append(MethodProtocol(
                method=method, protocol=protocol,
                display_order=order,
                explicit=False,
                status='active',
                evidence_source='llm_reviewed',
            ))
        if not objs:
            return 0
        created = MethodProtocol.objects.bulk_create(objs, ignore_conflicts=True)
        return len(created)
