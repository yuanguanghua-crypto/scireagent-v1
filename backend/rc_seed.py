"""Reagent Class Seed（Step 2-4，dev）

Step 2: 35 approved RC + 2 deprecated 父类（RC-19/RC-20），19A/19B/20A/20B.replaced_from 指向父类
Step 3: 15 Method × RC 映射（Mapping V1.0 修正版：RC-16→Gibson 已删、M23b 用 RC-19B）
Step 4: 126 PRC 候选（关键词规则 → 全部 pending_review，RC-10）

默认 dry-run；--apply 写库。幂等：已存在跳过。
"""
import os, sys, json, re

BASE = os.environ.get('RC_DATA_DIR', r'C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp')
DRY = '--apply' not in sys.argv

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.apps import apps
from django.db import transaction

RC = apps.get_model('knowledge', 'ReagentClass')
Method = apps.get_model('knowledge', 'Method')
Product = apps.get_model('commerce', 'Product')
MRC = apps.get_model('bridges', 'MethodReagentClass')
PRC = apps.get_model('bridges', 'ProductReagentClass')

# ---- 数据 ----
rc_data = json.load(open(os.path.join(BASE, 'reagent_classes.json'), encoding='utf-8'))
ents = json.load(open(os.path.join(BASE, 'step6_method_entities.json'), encoding='utf-8'))
code2slug = {e['id_code']: e['slug'] for e in ents}

# RC-19/RC-20 deprecated 父类（词表 35 类不含；作为 lineage 根）
PARENT_RC = [
    ('RC-19', 'Protease / Protease Inhibitor', 'protease-protease-inhibitor',
     '蛋白酶及其抑制剂合并类（已拆分为 RC-19A/RC-19B）'),
    ('RC-20', 'Kinase / Phosphatase', 'kinase-phosphatase',
     '激酶及其磷酸酶合并类（已拆分为 RC-20A/RC-20B）'),
]
# 子类 → 父类
REPLACED_FROM = {'RC-19A': 'RC-19', 'RC-19B': 'RC-19', 'RC-20A': 'RC-20', 'RC-20B': 'RC-20'}

# Step 3 映射（Mapping V1.0 修正版）：
# (method_id_code, rc_id_code, dependency_type, scope, dependency_group)
MRC_MAP = [
    ('M15', 'RC-01', 'essential', 'canonical', 'dntp_substrate'),
    ('M15', 'RC-12', 'essential', 'canonical', 'primer'),
    ('M15', 'RC-13', 'essential', 'canonical', 'polymerase'),
    ('M15', 'RC-29', 'enabling', 'common', ''),
    ('M16', 'RC-15', 'essential', 'canonical', 'reverse_transcriptase'),
    ('M16', 'RC-01', 'essential', 'canonical', 'dntp_substrate'),
    ('M16', 'RC-12', 'enabling', 'common', ''),
    ('M16', 'RC-29', 'enabling', 'common', ''),
    ('M10', 'RC-02', 'essential', 'canonical', 'modified_nucleotide'),
    ('M10', 'RC-13', 'essential', 'canonical', 'polymerase'),
    ('M10', 'RC-17', 'essential', 'canonical', 'ligase'),
    ('M10', 'RC-12', 'enabling', 'common', ''),
    ('M11', 'RC-15', 'essential', 'canonical', 'reverse_transcriptase'),
    ('M11', 'RC-02', 'essential', 'canonical', 'modified_nucleotide'),
    ('M11', 'RC-13', 'essential', 'canonical', 'polymerase'),
    ('NEW-RNAISH', 'RC-03', 'essential', 'canonical', 'fluorescent_nucleotide'),
    ('NEW-RNAISH', 'RC-12', 'essential', 'canonical', 'probe'),
    # RC-16→Gibson 已删（V1.0.1 审计：内切酶非 Gibson 核心）
    ('NEW-GibsonAssembly', 'RC-17', 'essential', 'canonical', 'ligase'),
    ('NEW-GibsonAssembly', 'RC-25', 'essential', 'canonical', 'vector'),
    ('M38', 'RC-22', 'essential', 'canonical', 'primary_antibody'),
    ('M38', 'RC-23', 'enabling', 'common', ''),
    ('M38', 'RC-11', 'enabling', 'common', ''),
    ('M38', 'RC-28', 'enabling', 'common', ''),
    ('M36', 'RC-22', 'essential', 'canonical', 'primary_antibody'),
    ('M36', 'RC-23', 'enabling', 'common', ''),
    ('M36', 'RC-09', 'enabling', 'common', ''),
    ('M36', 'RC-07', 'enabling', 'common', ''),
    ('M37', 'RC-22', 'essential', 'canonical', 'primary_antibody'),
    ('M37', 'RC-23', 'enabling', 'common', ''),
    ('M37', 'RC-09', 'enabling', 'common', ''),
    # M23b 用 RC-19B（RC-19 已 deprecated，RC-06 不继承）
    ('M23b', 'RC-30', 'essential', 'canonical', 'purification_medium'),
    ('M23b', 'RC-19B', 'enabling', 'common', ''),
    ('M32', 'RC-07', 'enabling', 'common', ''),
    ('M32', 'RC-08', 'enabling', 'common', ''),
    ('M29', 'RC-07', 'enabling', 'common', ''),
    ('M29', 'RC-22', 'enabling', 'common', ''),
    ('M29', 'RC-23', 'enabling', 'common', ''),
    ('M19', 'RC-25', 'enabling', 'common', ''),
    ('M21', 'RC-25', 'enabling', 'common', ''),
]

# ---- Step 4 分类器 v2（RC-10 抽检修正）----
# 修正 1：unmodified 必须负向过滤（抽检 20/20 误配：fluoro/azido/thio/methyl/iodo/aza 等被子串 'dctp'/'utp' 吸走）
# 修正 2：'rox' 误匹配 'hydroxy' → 荧光信号用 'rox-'，hydroxy 归修饰

# 修饰/荧光/终止信号（命中即非 unmodified）
MOD_SIGNALS = ['biotin', 'digoxigenin', 'amino', 'aminoallyl', 'azido', 'azide', 'alkyne',
               'thio', 'methyl', 'formyl', 'hydroxy', 'methoxy', 'aza', 'deaza', 'propargyl',
               'fluoro', 'iodo', 'bromo', 'chloro', 'dd', 'cy3', 'cy5', 'cy-', 'atto', 'alexa',
               'fluorescein', 'fam', 'rox-', 'texas', 'dylight', 'sulfo', 'dabcyl', 'f-ara',
               'nh2', '7-deaza', '5-bromo', '2-amino', '5-methyl', '6-aza', '2-thio', '5-iodo',
               '5-formyl', '5-hydroxy', '5-methoxy', '2-fluoro', '2-azido', '5-aa', '6-aza', 'aa-utp',
               # v2.1 补：剩余修饰信号（RC-10 复验 13 条中 12 条仍为修饰）
               'carboxy', 'ethynyl', 'propynyl', 'oxo', 'indolyl', 'pseudo', 'pseudouridine']
FLUOR_SIGNALS = ['cy3', 'cy5', 'cy-', 'atto', 'alexa', 'fluorescein', 'fam', 'rox-',
                 'texas red', 'dylight', 'sulfo-cy']
TERM_SIGNALS = ['ddntp', 'ddatp', 'ddctp', 'ddgtp', 'ddttp', 'terminator']
BASE_SIGNALS = ['dntp', 'datp', 'dctp', 'dgtp', 'dttp', 'ntp', 'gtp', 'ctp', 'utp',
                'amp', 'gmp', 'cmp', 'ump']

# rule_id → (rc, confidence)
RULE_TARGET = {
    'nucleotide.terminator': ('RC-04', 'high'),
    'nucleotide.fluorescent': ('RC-03', 'high'),
    'nucleotide.modified': ('RC-02', 'high'),
    'nucleotide.unmodified': ('RC-01', 'high'),
}


def classify(text):
    """返回 [(rule_id, rc, confidence, assignment_type)]——优先级：终止>荧光>修饰>未修饰。"""
    t = text.lower()
    hits = []
    if any(k in t for k in TERM_SIGNALS):
        r, c = RULE_TARGET['nucleotide.terminator']
        hits.append(('nucleotide.terminator', r, c, 'primary'))
    if any(k in t for k in FLUOR_SIGNALS):
        r, c = RULE_TARGET['nucleotide.fluorescent']
        hits.append(('nucleotide.fluorescent', r, c,
                     'primary' if not hits else 'secondary'))
    if any(k in t for k in MOD_SIGNALS):
        r, c = RULE_TARGET['nucleotide.modified']
        hits.append(('nucleotide.modified', r, c,
                     'primary' if not hits else 'secondary'))
    if any(k in t for k in BASE_SIGNALS):
        # 负向过滤：含任何修饰/荧光/终止信号 → 不是 unmodified
        if not any(k in t for k in MOD_SIGNALS + FLUOR_SIGNALS + TERM_SIGNALS):
            r, c = RULE_TARGET['nucleotide.unmodified']
            hits.append(('nucleotide.unmodified', r, c,
                         'primary' if not hits else 'secondary'))
    return hits


def main():
    # 预载 DB 已有关系（code 级，兼容 dry-run 未保存实例）
    existing_mrc = set(MRC.objects.select_related('method', 'reagent_class')
                       .values_list('method__slug', 'reagent_class__id_code'))
    existing_prc = set(PRC.objects.select_related('reagent_class')
                       .values_list('product_id', 'reagent_class__id_code'))

    with transaction.atomic():
        # ---- Step 2: RC ----
        rc_created = rc_skipped = 0
        code2obj = {}
        # 父类（deprecated）
        for idc, name, slug, desc in PARENT_RC:
            obj = RC.objects.filter(id_code=idc).first()
            if obj:
                rc_skipped += 1
            else:
                obj = RC(id_code=idc, name=name, slug=slug, definition=desc,
                         behavior_type='context_dependent', status='deprecated')
                if not DRY:
                    obj.save()
                rc_created += 1
            code2obj[idc] = obj
        # 35 类
        for r in rc_data:
            obj = RC.objects.filter(id_code=r['id_code']).first()
            if obj:
                rc_skipped += 1
            else:
                obj = RC(id_code=r['id_code'], name=r['name'], slug=r['slug'],
                         definition=r.get('definition', ''), behavior_type=r['behavior_type'],
                         status='approved')
                if not DRY:
                    obj.save()
                rc_created += 1
            code2obj[r['id_code']] = obj
        # replaced_from（子→父）
        for child, parent in REPLACED_FROM.items():
            c = code2obj[child]
            if c and c.replaced_from_id is None:
                if not DRY:
                    c.replaced_from = code2obj[parent]
                    c.save(update_fields=['replaced_from'])
        # 父类 deprecated 确认
        for idc, *_ in PARENT_RC:
            c = code2obj[idc]
            if c and c.status != 'deprecated':
                if not DRY:
                    c.status = 'deprecated'
                    c.save(update_fields=['status'])

        # ---- Step 3: MRC ----
        mrc_created = mrc_skipped = 0
        for mid, rcid, dep, scope, grp in MRC_MAP:
            m = Method.objects.filter(slug=code2slug.get(mid)).first()
            rc = code2obj.get(rcid)
            if not m or not rc:
                print(f'  [SKIP] 缺实体: {mid}→{rcid} (m={bool(m)} rc={bool(rc)})')
                continue
            if (m.slug, rcid) in existing_mrc:
                mrc_skipped += 1
                continue
            existing_mrc.add((m.slug, rcid))
            if not DRY:
                MRC.objects.create(method=m, reagent_class=rc, dependency_type=dep,
                                   scope=scope, dependency_group=grp, evidence_type='method_definition',
                                   evidence_strength='high' if dep == 'essential' else 'medium')
            mrc_created += 1

        # ---- Step 4: PRC（分类器 v2）----
        prc_created = prc_skipped = 0
        products = Product.objects.all().values('id', 'name', 'catalog_no')
        prod_hit = 0
        for p in products:
            text = f"{p['name'] or ''} {p['catalog_no'] or ''}".lower()
            hits = classify(text)
            if not hits:
                continue
            prod_hit += 1
            for rule_id, rcid, conf, atype in hits:
                rc = code2obj.get(rcid)
                if not rc:
                    continue
                if (p['id'], rcid) in existing_prc:
                    prc_skipped += 1
                    continue
                existing_prc.add((p['id'], rcid))
                if not DRY:
                    PRC.objects.create(
                        product_id=p['id'], reagent_class=rc,
                        assignment_type=atype,
                        classification_method='rule', classification_rule=rule_id,
                        classification_rule_version='1.1', confidence=conf,
                        evidence=f"分类器 v1.1 规则 {rule_id} 命中（{p['name'][:40]}）",
                        status='pending_review')
                prc_created += 1

        if DRY:
            transaction.set_rollback(True)

        print('=== Reagent Class Seed (dry-run)' if DRY else '=== Reagent Class Seed (apply)')
        print(f'Step2 RC: 新建 {rc_created} / 跳过 {rc_skipped}（终态应 37：35 approved + 2 deprecated）')
        print(f'Step3 MRC: 新建 {mrc_created} / 跳过 {mrc_skipped}')
        print(f'Step4 PRC: 新建 {prc_created} / 跳过 {prc_skipped} / 命中产品 {prod_hit}')
        print('提示：dry-run 已回滚（未写库）' if DRY else '提示：已写库')


if __name__ == '__main__':
    main()
