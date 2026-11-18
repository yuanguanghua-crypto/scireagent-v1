"""
protocol_steps_parser — 纯程序化解析 hierarchical_protocol 树为有序步骤列表（零 LLM）。

hierarchical_protocol 结构（实测样本）：
    {
      '1':     {'title': 'Bacterial Growth Under ...'},   # dict = 章节，只有 title
      '1.1':   {'title': 'Plate Preparation'},             # dict = 子章节
      '1.1.1': 'Spread a fresh H1 minimal medium ...',     # str  = 叶子步骤正文
      '1.1.2': 'Incubate at the appropriate temperature and time.',
      '1.2':   {'title': 'Overnight Culture'},
      '1.2.1': 'Start a fresh 3mL overnight culture ...',
    }

规则：
- 值为 dict  = 章节（只含 title，不是可执行步骤）
- 值为 str   = 叶子步骤（真正要入库的正文）
- 自然排序：'1.2' 必须排在 '1.10' 前（按数字分段排序，不能字符串排序）
- title 继承最近的父级章节 title（'1.1.1' 继承 '1.1'，无则继承 '1'，都没有则空）
- 空 / 纯空白 body 跳过
- 超长 title 截断到 255
- 空 dict / None / 非预期类型不崩

输出：list[{'step_no','title','body'}]，step_no 从 1 连续编号。

另一个入口见文末 `parse_plain_text_steps(text)`：把人手填的自由文本解析成同一形状。
两者形状一致，写入方（intake）只依赖该形状，不关心来源。

历史（A-070 根因）：表单的 `protocol_steps` 此前被直接写进 `Protocol.objective`
（"目标"字段），步骤既没进 `protocol_step` 表，还污染了目标字段。
"""
import html
import re
from typing import Any, Dict, List

TITLE_MAX = 255

# 已知 HTML 标签名（仅用于清理被上游吃掉尖括号后的残片，避免误伤正常英文词）
_KNOWN_TAGS = r'strong|em|b|i|u|br|p|div|span|table|tr|td|th|ul|ol|li|h[1-6]|a|img|sup|sub|small|code|pre'
_TAG_RE = re.compile(r'<[^>]*>')                 # 完整标签 <...>
_FRAG_LT_RE = re.compile(r'</?[a-zA-Z][\w]*')     # 左尖括号在、右尖括号被吃：<strong / </strong
_FRAG_GT_RE = re.compile(r'/?[a-zA-Z][\w]*>')     # 右尖括号在、左尖括号被吃：strong> / /strong>
_FRAG_START_RE = re.compile(r'^/?(' + _KNOWN_TAGS + r')\b')  # 行首紧贴内容的标签名残片


def _clean_title(s: str) -> str:
    """清洗章节标题：去 HTML 标签/残片、还原实体、压缩空白。

    上游清洗吃掉了左尖括号，残留形如 `strong>`、`</strong`、`/strong>`；也可能残留
    完整标签 `<strong>...</strong>` 或 HTML 实体 `&amp;`。正常标题（如
    `Lung section preparation`）不含 `<`/`>` 与标签名，应原样保留。清洗后为空返回 ''。
    """
    if not s:
        return ''
    s = html.unescape(s)                       # &amp; -> &, &lt; -> <
    s = _TAG_RE.sub('', s)                     # 完整标签 <...>
    s = _FRAG_LT_RE.sub('', s)                 # <strong / </strong（右>被吃）
    s = _FRAG_GT_RE.sub('', s)                 # strong> / /strong>（左<被吃）
    s = _FRAG_START_RE.sub('', s)              # 行首标签名残片（强/斜体等）
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def natural_key(key: Any):
    """自然排序键：'1.10' -> [1,10]，使 '1.2' 排在 '1.10' 之前。

    每个 '.' 分段若全为数字则按整数比较，否则按字符串比较；混合时也安全。
    """
    parts = str(key).split('.')
    out = []
    for p in parts:
        if p.isdigit():
            out.append((0, int(p), ''))
        else:
            out.append((1, 0, p))
    return out


def _section_title(val: Any) -> str:
    """从章节 dict 中提取 title（清洗 HTML 残片 + 去首尾空白）；非 dict 或缺失则返回空串。"""
    if isinstance(val, dict):
        return _clean_title((val.get('title') or '').strip())
    return ''


def _inherited_title(key: str, section_titles: Dict[str, str]) -> str:
    """叶子 key（如 '1.1.1'）向上找最近的、含非空 title 的祖先章节。

    祖先顺序：'1.1' -> '1'。全部无 title 则返回空串。
    """
    parts = str(key).split('.')
    for i in range(len(parts) - 1, 0, -1):
        prefix = '.'.join(parts[:i])
        t = section_titles.get(prefix, '')
        if t:
            return t
    return ''


def parse_hierarchical_protocol(hp: Any) -> List[Dict[str, Any]]:
    """将 hierarchical_protocol 树解析为有序步骤列表。

    入参非 dict（None / str / 数字 / list 等）一律返回空列表，不抛异常。
    """
    if not isinstance(hp, dict):
        return []

    # 1) 收集章节标题（dict 值）
    section_titles: Dict[str, str] = {}
    for k, v in hp.items():
        if isinstance(v, dict):
            section_titles[str(k)] = _section_title(v)

    # 2) 按自然序遍历：仅 str 值算叶子步骤
    steps: List[Dict[str, Any]] = []
    step_no = 0
    for key in sorted(hp.keys(), key=natural_key):
        key_s = str(key)
        val = hp[key]
        if not isinstance(val, str):
            # dict 章节或任何非预期类型（None/list/数字）一律跳过
            continue
        body = val.strip()
        if not body:
            # 空 / 纯空白正文跳过
            continue
        title = _inherited_title(key_s, section_titles)
        # 瑕疵2：无父级章节标题时，回退取 body 前 60 字符（截取自身正文，非编造）
        if not title:
            title = body[:60].strip()
        if len(title) > TITLE_MAX:
            title = title[:TITLE_MAX]
        step_no += 1
        steps.append({'step_no': step_no, 'title': title, 'body': body})
    return steps


# ── 入口二：表单自由文本 → 步骤（A-070 写入路径接入）──────────────────────
#
# 为什么需要它：`KnowledgeIntake` 页面只有一个 textarea 让人手填步骤
# （占位符示例就是「1. Prepare RNA 2. Add reagents 3. Incubate 4. Purify」）。
# 这类输入既可能是**每行一步**，也可能是**一行写完**，都要能吃下。
# 但绝不能"解析不了就整段塞 objective" —— 那正是 A-070 的原始缺陷。

# 行首编号：`1.` / `1)` / `1、` / `Step 1:` / `1：`
_LEADING_NO_RE = re.compile(r'^\s*(?:step\s*)?\d{1,3}\s*[.)、,:：]\s*', re.I)
# 内联编号：行首或空白之后 + 数字 + 后缀 + **至少一个空白** + 非空白
#   ⇒ `1.5 mL buffer` 不会被切开（`1.` 后面紧跟数字不是空白），
#      `1. Prepare` 才会命中。
_INLINE_NO_RE = re.compile(r'(?:^|(?<=\s))\d{1,3}\s*[.)、]\s+(?=\S)')

TITLE_SPLIT_MAX = 40        # 冒号在前 40 字符内才认作「标题：正文」分隔
TITLE_FALLBACK_CHARS = 60   # 与层级入口的回退长度保持一致（body[:60]）


def _split_title_body(item: str):
    """把一条步骤拆成 (title, body)。规则确定性，可逐条断言：

    1. 冒号（`:` 或 `：`）出现在**前 40 字符**内且两侧都非空
       ⇒ 冒号前 = title，冒号后 = body
    2. 否则 title 取正文前 60 字符（截取自身正文，**不编造**），body = 完整正文
    3. 返回的 title 可能为空串，由调用方兜底（保持与层级入口一致）
    """
    for sep in ('：', ':'):
        idx = item.find(sep)
        if 0 < idx <= TITLE_SPLIT_MAX:
            head, tail = item[:idx].strip(), item[idx + 1:].strip()
            if head and tail:
                return head, tail
    return item[:TITLE_FALLBACK_CHARS].strip(), item


def parse_plain_text_steps(text: Any) -> List[Dict[str, Any]]:
    """把表单里手填的步骤文本解析成 `[{step_no, title, body}]`（与层级入口同形状）。

    切分规则：
      - 多行 ⇒ 每个非空行 = 一步
      - 单行且含 ≥2 个行首/内联编号（`1.` `2)` `3、`）⇒ 按编号切开
      - 单行且无编号 ⇒ 整体算一步（宁可一步，也不凭标点瞎切）
      - 切完去残留编号、压缩空白；空项丢弃；step_no 从 1 连续编号
    非 str（None/数字/list）一律返回 []，不抛异常。
    """
    if not isinstance(text, str):
        return []
    raw = text.strip()
    if not raw:
        return []

    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if len(lines) == 1:
        hits = list(_INLINE_NO_RE.finditer(lines[0]))
        # 行首必须就是第一个编号，且至少两个编号，才认作"一行多步"
        items = _INLINE_NO_RE.split(lines[0]) if (len(hits) >= 2 and hits[0].start() == 0) else lines
    else:
        items = lines

    steps: List[Dict[str, Any]] = []
    for it in items:
        s = _LEADING_NO_RE.sub('', (it or '').strip())
        s = re.sub(r'\s+', ' ', s).strip()
        if not s:
            continue
        title, body = _split_title_body(s)
        title = _clean_title(title) or s[:TITLE_FALLBACK_CHARS]
        if len(title) > TITLE_MAX:
            title = title[:TITLE_MAX]
        steps.append({'step_no': len(steps) + 1, 'title': title, 'body': body})
    return steps
