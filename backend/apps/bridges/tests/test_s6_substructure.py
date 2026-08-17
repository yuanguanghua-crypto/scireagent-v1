"""S6 四轴子结构判定 —— 10 真值 100% 验证测试（硬闸门）。

直接内联真值集（不依赖根目录临时 JSON），对 substructure_backend 的四轴
SMARTS 判定做严格断言。RDKit 不可用时 skip（与 embedding_backend 的可移植
范式一致：CI/服务器无 s6 venv 时不失败，本地开发机 100% 通过）。

判定维度：base / sugar_sub / sugar_type / base_mod(5-Me) / propargyl / Biotin / NTP
"""
import pytest

from apps.bridges.services.substructure_backend import (
    detect_nucleotide_modifications,
    build_substructure_payload,
)

# 10 个已知真值商品：名称可读修饰 + DB 中 SMILES 完整（P=3）。
# 注：原 SC8015(Biotin-16-UTP) 的供应商 SMILES 糖环区与脱氧逐字节相同（数据质量问题），
# 已替换为 SC8026(Cy5-UTP, 干净核糖) 以守住 100% 真值闸门。
GROUND_TRUTH = [
    ("SC8035", "2'-Fluoro-dUTP",
     "C1=CN(C(=O)NC1=O)[C@H]2[C@@H]([C@@H]([C@H](O2)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)F",
     dict(base='U', base_mod=None, sugar_sub="2'-F", sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8036", "2'-Fluoro-dATP",
     "C1=NC(=C2C(=N1)N(C=N2)[C@H]3[C@@H]([C@@H]([C@H](O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)F)N",
     dict(base='A', base_mod=None, sugar_sub="2'-F", sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8037", "2'-Fluoro-dCTP",
     "C1=CN(C(=O)N=C1N)[C@H]2[C@@H]([C@@H]([C@H](O2)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)F",
     dict(base='C', base_mod=None, sugar_sub="2'-F", sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8038", "2'-Fluoro-dGTP",
     "[Li+].[Li+].[Li+].[Li+].C1=NC2=C(N1[C@H]3[C@@H]([C@@H]([C@H](O3)COP(=O)([O-])OP(=O)([O-])OP(=O)([O-])[O-])O)F)N=C(NC2=O)N",
     dict(base='G', base_mod=None, sugar_sub="2'-F", sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8045", "2'-Azido-dGTP",
     "[Li+].[Li+].[Li+].C1=NC2=C(N1[C@H]3C([C@H]([C@H](O3)COP(=O)([O-])OP(=O)([O-])OP(=O)(O)[O-])O)N=[N+]=[N-])N=C(NC2=O)N",
     dict(base='G', base_mod=None, sugar_sub="2'-Azido", sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8056", "5-Methyl-dCTP",
     "CC1=CN(C(=O)N=C1N)[C@H]2C[C@@H]([C@H](O2)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O",
     dict(base='C', base_mod='5-Methyl', sugar_sub=None, sugar_type='deoxy', biotin=False, ntp=True, propargyl=False)),
    ("SC8057", "5-Methyl-CTP",
     "CC1=CN(C(=O)N=C1N)[C@H]2[C@@H]([C@@H]([C@H](O2)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O",
     dict(base='C', base_mod='5-Methyl', sugar_sub=None, sugar_type='ribose', biotin=False, ntp=True, propargyl=False)),
    ("SC8016", "Biotin-11-dUTP",
     "C1[C@@H]([C@H](O[C@H]1N2C=C(C(=O)NC2=O)/C=C/CNC(=O)CCCCCNC(=O)CCCC[C@H]3[C@@H]4[C@H](CS3)NC(=O)N4)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O",
     dict(base='U', base_mod=None, sugar_sub=None, sugar_type='deoxy', biotin=True, ntp=True, propargyl=False)),
    ("SC8026", "Cy5-UTP",
     "CCN\\1C2=C(C=C(C=C2)S(=O)(=O)[O-])C(/C1=C/C=C/C=C/C3=[N+](C4=C(C3(C)C)C=C(C=C4)S(=O)(=O)O)CCCCCC(=O)NC/C=C/C5=CN(C(=O)NC5=O)[C@H]6[C@H]([C@H]([C@H](O6)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O)(C)C",
     dict(base='U', base_mod=None, sugar_sub=None, sugar_type='ribose', biotin=False, ntp=True, propargyl=False)),
    ("SC8021", "5‑Propargylamino‑dUTP",
     "C1[C@@H]([C@H](O[C@H]1N2C=C(C(=O)NC2=O)C#CCN)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O",
     dict(base='U', base_mod=None, sugar_sub=None, sugar_type='deoxy', biotin=False, ntp=True, propargyl=True)),
]


@pytest.fixture(scope="module")
def require_rdkit():
    try:
        detect_nucleotide_modifications("C")
    except Exception:
        pytest.skip("RDKit 不可用（s6 venv 未配置），跳过 S6 子结构判定测试")


@pytest.mark.usefixtures("require_rdkit")
def test_s6_four_axis_100pct():
    total = 0
    ok = 0
    failures = []
    for cat, name, smi, exp in GROUND_TRUTH:
        d = detect_nucleotide_modifications(smi)
        assert d is not None, f"{cat}: SMILES 解析失败"
        checks = {
            'base': d['base'] == exp['base'],
            'sugar_sub': d['sugar_sub'] == exp['sugar_sub'],
            'sugar_type': d['sugar_type'] == exp['sugar_type'],
            'base_mod(5-Me)': (d['base_mod'] == '5-Methyl') == bool(exp['base_mod']),
            'propargyl': d['propargyl'] == exp['propargyl'],
            'Biotin': d['biotin_label'] == exp['biotin'],
            'NTP': d['ntp'] == exp['ntp'],
        }
        for k, v in checks.items():
            total += 1
            ok += int(v)
            if not v:
                failures.append((cat, name, k, exp, d))
    assert ok == total, (
        f"S6 四轴判定未达 100%：{ok}/{total}\n"
        + "\n".join(f"  {c} {n}: {k} FAIL exp={e} pred={d}" for c, n, k, e, d in failures)
    )
    assert total == 70, f"预期 10×7=70 项断言，实际 {total}"


@pytest.mark.usefixtures("require_rdkit")
def test_s6_payload_labels_and_axes():
    """build_substructure_payload 生成前端友好的四轴标签 + axes。"""
    # 2'-Fluoro-dUTP (SC8035)：U / 2'-F / deoxy / NTP
    p = build_substructure_payload(GROUND_TRUTH[0][2])
    assert p['parsed'] is True
    assert p['labels'] == ['U', "2'-F", 'deoxy', 'NTP'], p['labels']
    a = p['axes']
    assert a['base'] == 'U' and a['sugar_sub'] == "2'-F" and a['sugar_type'] == 'deoxy'
    assert a['ntp'] is True and a['biotin_label'] is False and a['propargyl'] is False

    # 5-Methyl-dCTP (SC8056)：C / 5-Methyl / deoxy / NTP
    p2 = build_substructure_payload(GROUND_TRUTH[5][2])
    assert p2['labels'] == ['C', '5-Methyl', 'deoxy', 'NTP'], p2['labels']

    # Biotin-11-dUTP (SC8016)：U / deoxy / NTP / Biotin
    p3 = build_substructure_payload(GROUND_TRUTH[7][2])
    assert 'Biotin' in p3['labels']

    # 无效 SMILES → parsed False，labels 空，axes None（诚实占位）
    bad = build_substructure_payload('not-a-smiles')
    assert bad['parsed'] is False and bad['labels'] == [] and bad['axes'] is None

    # 空 SMILES → None（无数据可展示）
    assert build_substructure_payload('') is None
