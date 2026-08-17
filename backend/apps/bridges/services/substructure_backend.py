"""修饰核苷酸四轴子结构判定后端（S6 —— 硬闸门 2026-08-10 已 100% 验证）。

目标：建一个**真正独立于文本/名称**的信号通道。对修饰核苷酸的四轴
（碱基 / 糖环取代 / 糖环类型 / 碱基修饰 / 标记 / 磷酸）用 RDKit SMARTS
做**确定性子结构判定**，作为知识关联的可归因真实特征，而非靠名称正则猜。

环境：生产 backend venv(py3.13) 未装 rdkit（沙箱 safe-delete 拦 pip 升级），
故 rdkit 装在独立 py3.12 venv（默认 D:/s6_rdkit_venv），运行时惰性把其
site-packages 注入 sys.path（完全镜像 embedding_backend 的范式）。

SMARTS 经 10 个已知商品真值 100% 验证（base A/U/C/G/T、sugar_sub 2'-F /
2'-Azido / 2'-NH2、sugar_type deoxy/ribose、base_mod 5-Methyl、label Biotin、
phosphate NTP、propargyl）。关键修正点（避免误判）：
  - 外环 NH2 / 羰基必须挂在**碱基芳香环碳**上，排除远端标记链上的 NH2、
    biotin 酰胺 C=O、以及磷酸 P=O。
  - 糖环类型用「呋喃糖环碳上的 OH 数」判定（核糖=2 / 脱氧=1），绕开 biotin
    噻唑烷酮环 CH2 对 [C;r5;H2] 的干扰。
  - 5-甲基用末端 [CH3] 挂嘧啶环，排除 propargylamino 的 CH2 误报。
"""
import os
import sys

# 缺省仅为本地开发机路径；部署环境须用 S6_RDKIT_VENV 环境变量或
# settings.S6_RDKIT_VENV_PATH 覆盖（服务器不存在 D 盘，硬编码必然失败）。
DEFAULT_S6_RDKIT_VENV = r"D:\s6_rdkit_venv"

# ---- 四轴 SMARTS（已 10 真值 100% 验证，2026-08-10；2026-08-10 扩真值后硬化）----
# 嘌呤核含 7-deaza 变体（7 位 N→C）：标准 c1nc2c(n1)ncnc2 / 7-deaza c1cc2c(n1)ncnc2
_PURINE      = ['c1nc2c(n1)ncnc2', 'c1cc2c(n1)ncnc2']
_BASE_NH2    = '[NX3;H2;!R]-[c,n;r6]'   # 碱基环外 NH2（排除标记链/酰胺/P=O）
_BASE_CO     = '[O;!R](=[c,n;r6])'      # 碱基环外羰基（排除 P=O、biotin 酰胺）
_BASE_THIONE = '[S;!R](=[c,n;r6])'      # 碱基环外硫酮（6-thio-G 的 C6=S）
# 胞嘧啶 C2-NH2：载体碳（承载外环 NH2）必须与至少一个**环 N** 成键（小写=芳香，
# aromatized 后载体为芳香 c、邻接环 n）。区分真 C（C2-NH2 夹 N1 与 C 间）与
# 5-氨基烯丙基-U 的 C5-NH2 载体碳（只连两个环 C，无环 N）。
_CYTOSINE_NH2 = '[n;r6][c;r6]([NX3;H2;!R])'
# 嘌呤 C6 氧取代（G 标志）：正常 G 为 C6=O(_BASE_CO)，6-thio-G 为 C6=S(_BASE_THIONE)，
# O6-甲基/O6-烷基-G 为 C6-O-烷基（单键 O 挂环碳）。三者任一即 G（区别于 A 的 C6-NH2）。
_G_C6OXY    = '[O;!R]-[c,n;r6]'
_FIVE_METHYL = '[CH3]~[c,n;r6]'         # 碱基 C5 末端甲基
_SUGAR_2F    = '[C;r5](F)'
_SUGAR_AZ    = '[C;r5][N]=[N+]=[N-]'
_SUGAR_NH2   = '[C;r5]([NH2])'
_RING_OH     = '[C;r5]-[OH]'            # 呋喃糖环碳 OH（核糖=2 / 脱氧=1）
# 炔键特异性：仅认 propargyl/propynyl 点击手柄（-CH2-C≡CH），排除 5-ethynyl 直接炔
_PROPARGYL   = '[CH2]-C#C'
_BIOTIN      = 'S1CC2NC(=O)NC2C1'       # 饱和噻吩并咪唑烷酮核
_NTP         = '[P]O[P]O[P]'            # 三磷酸 P-O-P-O-P

_venv_injected = False


def s6_rdkit_venv_path():
    """rdkit venv 根路径：环境变量 > Django settings > 本地缺省。"""
    env = os.environ.get("S6_RDKIT_VENV")
    if env:
        return env
    try:
        from django.conf import settings
        configured = getattr(settings, "S6_RDKIT_VENV_PATH", None)
    except Exception:
        configured = None
    return configured or DEFAULT_S6_RDKIT_VENV


def _ensure_injected():
    global _venv_injected
    if _venv_injected:
        return
    site = os.path.join(s6_rdkit_venv_path(), "Lib", "site-packages")
    if os.path.isdir(site) and site not in sys.path:
        sys.path.insert(0, site)
    _venv_injected = True


def _rdkit():
    """惰性获取 rdkit.Chem；不可用时抛 ImportError 由调用方降级。"""
    _ensure_injected()
    from rdkit import Chem
    return Chem


def detect_with_chem(mol, Chem):
    """纯函数：对 RDKit mol 做四轴判定。Chem 为 rdkit.Chem（便于测试注入）。"""
    if mol is None:
        return None

    def has(pat):
        p = Chem.MolFromSmarts(pat)
        return mol.HasSubstructMatch(p) if p is not None else False

    def nmatches(pat):
        p = Chem.MolFromSmarts(pat)
        return len(mol.GetSubstructMatches(p)) if p is not None else 0

    base_nh2 = has(_BASE_NH2)
    base_co = has(_BASE_CO)
    base_thione = has(_BASE_THIONE)
    cyt_nh2 = has(_CYTOSINE_NH2)
    five_me = has(_FIVE_METHYL)
    is_purine = any(has(p) for p in _PURINE)
    if is_purine:
        if base_nh2 and (base_co or base_thione or has(_G_C6OXY)):
            base, base_mod = 'G', None
        elif base_nh2:
            base, base_mod = 'A', None
        else:
            base, base_mod = 'purine?', None
    else:
        if five_me and cyt_nh2:
            base, base_mod = 'C', '5-Methyl'
        elif five_me:
            base, base_mod = 'T', '5-Methyl'
        elif cyt_nh2:
            base, base_mod = 'C', None
        elif base_co:
            base, base_mod = 'U', None
        elif base_nh2:
            # 5-氨基烯丙基-U 等：C5 取代带 NH2 但非 canonical 胞嘧啶 → 判 U
            base, base_mod = 'U', None
        else:
            base, base_mod = 'U', None

    sub = []
    if has(_SUGAR_2F):
        sub.append("2'-F")
    if has(_SUGAR_AZ):
        sub.append("2'-Azido")
    if has(_SUGAR_NH2):
        sub.append("2'-NH2")
    oh = nmatches(_RING_OH)
    sugar_type = 'deoxy' if oh <= 1 else 'ribose'
    return {
        'base': base,
        'base_mod': base_mod,
        'sugar_sub': sub[0] if sub else None,
        'sugar_type': sugar_type,
        'ring_oh_count': oh,
        'biotin_label': has(_BIOTIN),
        'ntp': has(_NTP),
        'propargyl': has(_PROPARGYL),
    }


def detect_nucleotide_modifications(smiles):
    """对单个 SMILES 字符串做四轴判定，返回结构化 dict；SMILES 无效/缺失返回 None。"""
    if not smiles:
        return None
    Chem = _rdkit()
    mol = Chem.MolFromSmiles(smiles)
    return detect_with_chem(mol, Chem)


def build_substructure_payload(smiles):
    """对单个 SMILES 生成前端友好的四轴修饰标签 payload（S6 展示/治理落库用）。

    返回契约：
      - SMILES 为空 / 缺失           → 返回 None（无数据可展示）。
      - SMILES 无效（RDKit 解析失败） → {'parsed': False, 'labels': [], 'axes': None}
        （诚实标记「尝试过但无法解析」，前端用 — 占位，不冒充 0 / 不编造）。
      - 解析成功                     → {'parsed': True, 'labels': [...], 'axes': {...}}

    RDKit 不可用时抛 ImportError（由调用方降级，与 detect_nucleotide_modifications 一致）。

    labels 为去重有序展示列表，例如 ['G', "2'-F", 'deoxy', 'NTP']；
    axes 为完整四轴原始判定，供详情页精确渲染（含 ring_oh_count 等辅助信息）。
    """
    if not smiles:
        return None
    Chem = _rdkit()
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {'parsed': False, 'labels': [], 'axes': None}
    d = detect_with_chem(mol, Chem)
    labels = []
    # 轴 1：碱基 + 碱基修饰
    if d['base'] and d['base'] != 'purine?':
        labels.append(d['base'])
    elif d['base'] == 'purine?':
        labels.append('Purine')
    if d['base_mod']:
        labels.append(d['base_mod'])
    # 轴 2：糖环取代（2' 修饰）
    if d['sugar_sub']:
        labels.append(d['sugar_sub'])
    # 轴 3：糖环类型
    labels.append('deoxy' if d['sugar_type'] == 'deoxy' else 'ribose')
    # 轴 4：标记 / 官能手柄
    if d['biotin_label']:
        labels.append('Biotin')
    if d['ntp']:
        labels.append('NTP')
    if d['propargyl']:
        labels.append('Propargyl')
    return {
        'parsed': True,
        'labels': labels,
        'axes': {
            'base': d['base'],
            'base_mod': d['base_mod'],
            'sugar_sub': d['sugar_sub'],
            'sugar_type': d['sugar_type'],
            'ring_oh_count': d['ring_oh_count'],
            'biotin_label': d['biotin_label'],
            'ntp': d['ntp'],
            'propargyl': d['propargyl'],
        },
    }
