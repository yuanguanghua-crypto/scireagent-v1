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
"""
from typing import Any, Dict, List

TITLE_MAX = 255


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
    """从章节 dict 中提取 title（去首尾空白）；非 dict 或缺失则返回空串。"""
    if isinstance(val, dict):
        return (val.get('title') or '').strip()
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
        if len(title) > TITLE_MAX:
            title = title[:TITLE_MAX]
        step_no += 1
        steps.append({'step_no': step_no, 'title': title, 'body': body})
    return steps
