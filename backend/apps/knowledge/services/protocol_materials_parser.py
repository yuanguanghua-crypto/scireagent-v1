"""
protocol_materials_parser — 把语料 `input` 字段解析为逐条材料清单（零 LLM、零网络）。

## 语料真实结构（2026-10-30 全量实测，勿凭印象改规则）

`input` 有三种形态，**不同语料源完全不同**：

1. **Bio-protocol（4,157 条，结构最规整）**
   第一个 `#` 之前是一段**无标题的编号清单**（85.5% 的记录有，80.6% 的条目带
   catalog number）—— 这一段就是 Materials & Reagents 主清单，只是没有标题。
   之后的 `# Equipment` / `# Software` / `# Recipes` / `# Solutions` 等是分节。
   条目形态：`1. Sodium chloride (NaCl) (J.T. Baker, catalog number: 3624-19)`

2. **Protocol-exchange（933 条）**
   没有编号，靠**空行分块**，每块一行一个条目。
   条目形态：`Sep-Pak C18 1 cc Vac Cartridge (Waters, WAT023590)`
   —— 括号里只有供应商（没有 "catalog number" 字样）时，货号不可信，**留空**。

3. **Protocol-io（9,585 条）**
   **原始 JSON 根本没有 `input` 字段** ⇒ 本模块对它无能为力，调用方应直接跳过。
   这不是解析失败，是数据不存在。

## 分节标题：1,800 种写法，没有受控词表

实测 4,048 条非空 `input` 共出现 **1,800 种不同标题词**，同一意思有无数写法：

    reagents / b.  reagents / c.reagents / B. Reagents / general reagents /
    molecular biology reagents / additional reagents for cryo-EXM protocol /
    chemicals and reagents / chemicals / antibodies / enzymes / kits / drugs ...

因此 `kind` 只能归一化成 8 类，**允许落 `material_or_reagent`（未细分）** ——
强行归一类会把「Biological materials」错标成试剂，那比不标更糟。

## 保真铁律

`raw_line` 只允许**拼接续行**，不允许改写。校验方式：
把原文的连续空白压缩成单空格后，必须 `contain` 该 `raw_line`
（不能直接 substring —— 续行在原文档里是 `\\n`，拼接后是单空格）。
"""
import re
from typing import Dict, List

NAME_MAX = 500
VENDOR_MAX = 200
CATALOG_MAX = 100
MODEL_MAX = 100
HEADING_MAX = 200

SEC_RE = re.compile(r'^#\s*(.+?)\s*$', re.M)
# 行首编号：1. / 2) / 3．(全角点)
ITEM_LINE_RE = re.compile(r'^\s*(\d{1,3})\s*[\.\)．]\s+(.*)$')
# 同一物理行里塞了多个编号 —— 分隔符必须用 [ \t]，**不能用 \s**
# （\s 会跨换行，把行首项重复计一次；实测会把 1.9% 误算成 43%）
INLINE_ITEM_RE = re.compile(r'(?<=[a-z\)\.\%\u00b0C])[ \t]{1,3}(\d{1,3})\s*[\.\)．]\s+(?=[A-Z(])')
ANY_ITEM_RE = re.compile(r'^\s*\d{1,3}\s*[\.\)．]\s+\S', re.M)

CAT_RE = re.compile(
    r'(?:catalog\s*(?:numbers?|no\.?|#)|cat\.?\s*no\.?)\s*[:：]?\s*([^,;)\s][^,;)]*)', re.I)
MODEL_RE = re.compile(r'model\s*(?:numbers?|no\.?)?\s*[:：]?\s*([^,;)]+)', re.I)
PAREN_RE = re.compile(r'\(([^()]*)\)')
WS_RE = re.compile(r'\s+')

# ── 分节标题 → 8 类。顺序即优先级（先匹配到的赢）──────────────────────────
HEADING_RULES = [
    ('equipment', re.compile(r'\b(equipment|equipments|apparatus|instrument|devices?)\b')),
    ('software', re.compile(r'\b(software|dataset|database|program|code)\b')),
    ('consumable', re.compile(r'\b(consumables?|suppl(?:y|ies)|tips?|glassware|plastics?)\w*')),
    ('biological_material', re.compile(
        r'\b(biological materials?|materials?|plasmids?|strains?|cell ?lines?|cell culture|'
        r'animals?|plants?|fly stocks?|viruses|virus|bacteri\w*|antibod\w*|serum|tissue|'
        r'organisms?|lipid)\w*')),
    ('reagent', re.compile(
        r'\b(reagents?|chemicals?|drugs?|enzymes?|kits?|dyes?|primers?|oligos?|peptides?|proteins?)\w*')),
    ('solution_recipe', re.compile(r'\b(solutions?|recipes?|buffers?|media|medium|stock)\w*')),
]
NOTE_HEADINGS = frozenset({'notes', 'note', 'optional', 'bio protocol', 'cite', 'general'})

# ── 前导无标题区 / 兜底的条目级内容判别。同样顺序即优先级 ──────────────────
# ⚠️ consumable 必须排在 equipment 之前：
#    `50mL centrifuge tube` 里的 centrifuge 是**修饰词**，主体是 tube（耗材）。
#    若 equipment 先匹配，把离心管标成设备，客户按设备找就永远找不到耗材。
ITEM_RULES = [
    ('consumable', re.compile(
        r'\b(microplates?|microtubes?|tubes?|plates?|tips?|flasks?|dishes?|slides?|coverslips?|filters?|membranes?|'
        r'columns?|syringes?|needles?|bottles?|beakers?|cylinders?|gloves?|petri|multiwell|'
        r'glass wool|parafilm|foil|papers?|cartridges?|septa|meshes?|mesh|grids?|'
        r'well plates?)\b', re.I)),
    ('equipment', re.compile(
        r'\b(centrifuges?|microscopes?|incubators?|cyclers?|thermomixer|shakers?|water bath|'
        r'balances?|spectrophotometers?|readers?|imagers?|electrophoresis|power suppl\w+|'
        r'pipett\w+|autoclaves?|freezers?|sonicators?|homogeni[sz]ers?|stirrers?|vortex|'
        r'peristaltic|pumps?|detectors?|scanners?|analy[sz]\w+|sequencers?|flow cytometers?|'
        r'hoods?|biosafety cabinets?|laminar)\w*', re.I)),
    ('software', re.compile(
        r'\b(software|ImageJ|Fiji|GraphPad|Prism|MATLAB|Python|R package|plugin|algorithm|'
        r'database|v\d+\.\d+)\b', re.I)),
    ('biological_material', re.compile(
        r'\b(cell ?lines?|cells?|strains?|plasmids?|antibod(?:y|ies)|ser(?:um|a)|mice|mouse|'
        r'rats?|zebrafish|drosophila|yeast|bacteri\w*|E\. coli|viruses|virus|phage|primers?|'
        r'oligos?|tissues?|embryos?|larvae|plants?|seeds?|leaves|roots?)\b', re.I)),
    ('reagent', re.compile(
        r'\b(acids?|bases?|salts?|buffers?|solutions?|medium|reagents?|kits?|dyes?|stains?|'
        r'solvents?|alcohols?|ethanol|methanol|chloroform|water|DMSO|DTT|EDTA|SDS|Tris|NaCl|'
        r'KCl|PBS|Tween|Triton|BSA|FBS|glucose|sucrose|glycerol|enzymes?|polymerase|ligase|'
        r'dNTPs?|ATP|GTP|antibiotics?|inhibitors?|substrate|standards?|markers?|ladder|'
        r'gels?|agarose|acrylamide)\b', re.I)),
]


def _s(value, limit):
    """截断到字段上限，避免 bulk_create 因超长报错。"""
    return (value or '')[:limit]


_NORM_TITLE_RE = re.compile(r'[^a-z0-9]+')


# 括号第一段是这类「占位词」时不是供应商名。
# 实测 `(e.g., Sigma-Aldrich, catalog number: E7023)` 出现 2,104 次（占 1.2%），
# 若直接把第一段当 vendor，会得到一堆 vendor='e.g.' 的脏数据，客户看到会以为抓错了。
_VENDOR_FILLER_RE = re.compile(r'^(?:e\.?\s?g\.?|i\.?\s?e\.?|etc\.?|see|such\s+as|eg)$', re.I)
_VENDOR_ATTR_RE = re.compile(r'^(?:catalogs?|cat\.?\s*no\.?|model|manuf\w*|part\s*no)\b', re.I)


def pick_vendor(parts) -> str:
    """从括号分段里挑出真正的供应商名。

    规则：跳过 `e.g.` / `i.e.` / `etc.` 这类占位词（含带逗号的变体），
    遇到 `catalog number:` / `model:` 这类属性段就停止（后面不再有供应商）。
    """
    for raw in parts:
        seg = (raw or '').strip()
        # 剥掉行首 e.g. / i.e. 前缀，可能是 `e.g. Sigma-Aldrich` 这种连写
        seg = re.sub(r'^(?:e\.?\s?g\.?|i\.?\s?e\.?|etc\.?)\s*[,:]?\s*', '', seg, flags=re.I)
        seg = seg.strip().rstrip(',').strip()
        if not seg or _VENDOR_FILLER_RE.match(seg):
            continue
        if _VENDOR_ATTR_RE.match(seg):
            return ''
        return seg[:VENDOR_MAX]
    return ''


def normalize_title(s: str) -> str:
    """标题归一化：小写 → 非字母数字折叠为空格 → 压缩空白。

    ★ 唯一实现，`backfill_protocol_provenance` 与 `import_protocol_materials`
    必须共用这一套规则 —— 两套规则会让「同一份语料匹配到不同协议」，
    导致溯源字段和材料清单对不上。
    实测三源 ↔ 生产库的匹配率：Bio-protocol 100%、Protocol-exchange 100%、
    Protocol-io 97.0%，就是在这一套规则下测出来的。
    """
    s = (s or '').strip().lower()
    s = _NORM_TITLE_RE.sub(' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def normalize_heading(heading: str) -> str:
    """去编号前缀（`a.` / `2.`）→ 小写 → 非字母转空格 → 压缩空白。"""
    s = (heading or '').strip().lower()
    s = re.sub(r'^[a-z]\.\s*', '', s)
    s = re.sub(r'^\d+\s*[\.\)．]\s*', '', s)
    s = re.sub(r'[_:：]+', ' ', s)
    s = re.sub(r'[^a-z ]+', ' ', s)
    return WS_RE.sub(' ', s).strip()


def classify_heading(heading: str) -> str:
    """分节标题 → kind。认不出的一律 `material_or_reagent`（诚实标注，不猜）。"""
    norm = normalize_heading(heading)
    if not norm:
        return 'material_or_reagent'
    for kind, rx in HEADING_RULES:
        if rx.search(norm):
            return kind
    if norm in NOTE_HEADINGS:
        return 'note'
    return 'material_or_reagent'


def classify_item(name: str) -> str:
    """按条目名内容判类别 —— 只用于「前导无标题区」和认不出标题的分节。"""
    text = name or ''
    for kind, rx in ITEM_RULES:
        if rx.search(text):
            return kind
    return 'reagent'


def split_parens(raw: str) -> Dict[str, str]:
    """从条目行里抽出 (name, vendor, catalog_no, model_no)。

    规则：遍历所有括号，取**第一个含 catalog/model 线索**的括号作为供应商段。
    这样 `PBS (Thermo Fisher, catalog number: 20012027), store at RT`
    这种「括号后面还跟着说明」的形态也能正确解析
    （v1 要求括号在行末，会漏掉 13.2% 的货号）。
    """
    for m in PAREN_RE.finditer(raw):
        inner = m.group(1)
        cat_m = CAT_RE.search(inner)
        model_m = MODEL_RE.search(inner)
        if not (cat_m or model_m or re.search(r'\bcatalog\b', inner, re.I)):
            continue
        name = raw[:m.start()].strip().rstrip(',').strip()
        parts = re.split(r',(?![^()]*\))', inner)
        vendor = pick_vendor(parts)
        return {
            'name': name or raw.strip(),
            'vendor': vendor,
            'catalog_no': (cat_m.group(1).strip() if cat_m else '')[:CATALOG_MAX],
            'model_no': (model_m.group(1).strip() if model_m else '')[:MODEL_MAX],
        }
    # 没有 catalog 线索：整行当名字，去掉尾随的存储/注意事项说明
    name = re.split(
        r'\s*\((?:store|storage|dissolve|shelf|note|caution|final|keep|use|see|prepare)\b',
        raw, flags=re.I)[0].strip()
    return {'name': name or raw.strip(), 'vendor': '', 'catalog_no': '', 'model_no': ''}


def _split_inline_items(line: str) -> List[str]:
    """把同一物理行里塞的多个编号项拆开（实测只占 1.9%，但会整条丢掉）。"""
    if not INLINE_ITEM_RE.search(line):
        return [line]
    out, last = [], 0
    for m in INLINE_ITEM_RE.finditer(line):
        out.append(line[last:m.start()])
        last = m.start()
    out.append(line[last:])
    return [seg.strip() for seg in out if seg.strip()]


def _item(heading, kind, ordinal, payload, raw_line, seq) -> Dict:
    payload = dict(payload)
    # 货号残缺就置空 —— 宁缺勿错。
    # 语料里存在括号未闭合的情况（`Inorganic ^13C (Sigma-Aldrich, catalog number:` 后面
    # 的编号被换行截断），抽出半截货号比没有更危险：客户拿去询价会查错货。
    cat = (payload.get('catalog_no') or '').strip()
    if cat and ('(' in cat or re.search(r'[\(\),;:]$', cat)):
        cat = ''
    return {
        'seq': seq,
        'kind': kind,
        'ordinal': ordinal,
        'name': _s(payload.get('name'), NAME_MAX),
        'vendor': _s(payload.get('vendor'), VENDOR_MAX),
        'catalog_no': _s(cat, CATALOG_MAX),
        'model_no': _s(payload.get('model_no'), MODEL_MAX),
        'section_heading': _s(heading, HEADING_MAX),
        'raw_line': raw_line,
    }


def parse_numbered(text: str) -> List[Dict]:
    """Bio-protocol 风格：`#` 分节 + 行首编号项，续行并入上一条。"""
    items: List[Dict] = []
    parts = SEC_RE.split(text)
    blocks = [('', parts[0])]
    for i in range(1, len(parts), 2):
        blocks.append((parts[i].strip(), parts[i + 1] if i + 1 < len(parts) else ''))

    seq = 0
    for heading, body in blocks:
        # 前导无标题区：kind 先留 None，最后按条目名内容判
        kind = classify_heading(heading) if heading else None
        current = None
        for line in body.splitlines():
            m = ITEM_LINE_RE.match(line)
            if m:
                for seg in _split_inline_items(m.group(2)):
                    seq += 1
                    ordinal = int(ITEM_LINE_RE.match(seg).group(1)) if ITEM_LINE_RE.match(seg) else int(m.group(1))
                    body_text = ITEM_LINE_RE.match(seg).group(2) if ITEM_LINE_RE.match(seg) else seg
                    current = _item(heading, kind, ordinal, split_parens(body_text), seg.strip(), seq)
                    items.append(current)
            elif line.strip() and current is not None:
                # 续行：只拼 raw_line，不重新解析属性（避免把续行里的括号当供应商）。
                # ★ 一律用**单空格**拼接，不做「行尾连字符直接相接」的特殊处理 ——
                #   保真校验的口径是「原文压缩连续空白后包含 raw_line」，
                #   若这里把 `pRS416M1-\nTEF1` 拼成 `pRS416M1-TEF1`，
                #   而原文压缩后是 `pRS416M1- TEF1`（中间有空格），就会假报不保真。
                current['raw_line'] = (current['raw_line'] + ' ' + line.strip()).strip()

    for it in items:
        if it['kind'] is None:
            it['kind'] = classify_item(it['name'])
    return items


def parse_blocks(text: str) -> List[Dict]:
    """Protocol-exchange 风格：`#` 分节 + 空行分块，每块一行（或多行）一条。"""
    items: List[Dict] = []
    parts = SEC_RE.split(text)
    blocks = [('', parts[0])]
    for i in range(1, len(parts), 2):
        blocks.append((parts[i].strip(), parts[i + 1] if i + 1 < len(parts) else ''))

    seq = 0
    for heading, body in blocks:
        kind = classify_heading(heading) if heading else None
        for chunk in re.split(r'\n\s*\n', body):
            merged = ' '.join(ln.strip() for ln in chunk.splitlines() if ln.strip()).strip()
            if len(merged) < 3:
                continue
            seq += 1
            payload = split_parens(merged)
            # Protocol-exchange 的括号常只写「供应商」或「供应商, 货号」（没有 catalog 字样）：
            #   `NaClO (Honeywell)` / `Sep-Pak C18 (Waters, WAT023590)`
            # split_parens 认不出 catalog 线索会退回整行当名字，这里补一次。
            # 货号只在**恰好两段、第二段是全大写字母数字编号**时才认 ——
            # 这样能覆盖 WAT023590，又能排除 `(Sigma-Aldrich, St. Louis, MO)` 这种地址。
            if not payload['vendor'] or payload['catalog_no'] == '':
                m = re.search(r'\(([A-Za-z][^()]{1,80})\)\s*$', merged)
                if m:
                    inner = m.group(1)
                    is_dose = re.search(r'\d+\s*(?:mg|ml|g|l|mm|um|µm|°c|%|x)\b', inner, re.I)
                    if not is_dose:
                        parts = [p.strip() for p in inner.split(',')]
                        if not payload['vendor']:
                            v = pick_vendor(parts)
                            if v:
                                payload['vendor'] = v
                        if (payload['catalog_no'] == '' and len(parts) == 2
                                and re.fullmatch(r'[A-Z0-9][A-Z0-9\-\.]{2,24}', parts[1])):
                            payload['catalog_no'] = parts[1]
                        head = merged[:m.start()].strip().rstrip(',').strip()
                        if head:
                            payload['name'] = head
            items.append(_item(heading, kind, None, payload, merged, seq))

    for it in items:
        if it['kind'] is None:
            it['kind'] = classify_item(it['name'])
    return items


def parse_materials(text: str) -> List[Dict]:
    """主入口：自动判别风格并解析。

    判别规则：`input` 里存在行首编号项 ⇒ numbered（Bio-protocol）；
    否则 ⇒ blocks（Protocol-exchange）。空文本返回 []。
    """
    if not text or not text.strip():
        return []
    if ANY_ITEM_RE.search(text):
        return parse_numbered(text)
    return parse_blocks(text)


def is_faithful(raw_line: str, original: str) -> bool:
    """保真校验：原文压缩空白后必须包含 raw_line（同样压缩空白）。

    不能直接 substring —— 续行在原文档里是换行，拼接后是单空格。
    """
    if not raw_line:
        return True
    return WS_RE.sub(' ', raw_line) in WS_RE.sub(' ', original or '')
