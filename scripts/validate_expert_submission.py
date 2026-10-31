#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""专家提交校验器 —— 读回填 CSV，出「通过 / 待裁决 / 退回」回执。

用法：
    python scripts/validate_expert_submission.py <回传目录> [--out 报告.md]

设计要点（每条都对应一次真实踩坑）：
1. **按表分派判定枚举** —— 已挂载表只认「正确/错误/不确定」，未挂载表只认「应挂/不适用/不确定」，
   实体字段表只认「正确/错误/缺失待补/不确定」。三种混用必被退回（旧版一张表的实测结论）。
2. **引用校验一律用编号** —— 产品必须命 catalog_no，实体必须落在候选池内。
   专家写实体简称（qPCR）会退回并给出"是否指 XXX"的提示。
3. **依据做粗筛** —— 拦「根据我的经验/业内共识/我觉得」这类不可核查表述；拦不住的（DOI 真实但结论不符）交人工。
4. **冲突不自动裁决** —— 同实体同字段两个不同值，两条都转「待裁决」，绝不替人挑一个。
5. 只读，不连数据库、不写库。
"""
import argparse
import csv
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLAB = os.path.join(BASE, 'docs', 'expert-collab')
DUMP = os.path.join(BASE, '_audit_tmp', 'prod_dump.json')

ENUM_ROLE = {'试剂', '缓冲液', '对照', '酶', '标记物', '溶剂', '其他'}
ENUM_EVID = {'文献DOI', '厂家说明书', '数据库条目', '标准或教科书', '不确定'}
ENUM_CONF = {'高', '中', '低'}
ENUM_FIELD = {'英文规范名', '定义', '实验目的', '用途', '优势', '局限性', '成本区间', '时间线'}

FILLER = re.compile(r'(根据.{0,4}经验|业内共识|众所周知|一般认为|我觉得|应该是|大概)')

TABLE_RULES = {
    '01a': {'name': '已挂载', 'judge': {'正确', '错误', '应删', '不确定'}},
    '01b': {'name': '未挂载', 'judge': {'应挂', '不适用', '不确定'}},
    '01c': {'name': '实体字段', 'judge': {'正确', '错误', '缺失待补', '不确定'}},
}


def load_ref():
    if not os.path.exists(DUMP):
        sys.exit(f'缺少引用数据 {DUMP}（应从生产库导出产品与候选实体清单）')
    d = json.load(io.open(DUMP, encoding='utf-8'))
    prods = {p['catalog_no']: p for p in d['products']}
    methods = {str(m['id']): m for m in d['methods']}
    # 原表行号集合：防止专家自行增行（增的行没有对应的系统现状，无法核对）
    orig = {}
    for kind in TABLE_RULES:
        for f in os.listdir(COLLAB):
            if f.startswith(kind) and f.endswith('.csv') and '回填' not in f:
                orig[kind] = {(r.get('行号') or '').strip() for r in read_csv(os.path.join(COLLAB, f))}
                break
    return prods, methods, orig


def read_csv(path):
    with io.open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def check(fname, rows, prods, methods, orig):
    kind = fname[:3]
    rule = TABLE_RULES.get(kind)
    if not rule:
        return [{'rid': '?', 'status': 'REJECT', 'cat': '文件', 'msg': f'无法识别的表类型：{fname}'}]
    allowed = rule['judge']
    valid_rids = orig.get(kind, set())
    out = []
    seen = {}

    def add(rid, status, cat, msg=''):
        out.append({'rid': rid, 'status': status, 'cat': cat, 'msg': msg})

    for r in rows:
        rid = (r.get('行号') or '').strip()
        if not rid:
            continue
        if valid_rids and rid not in valid_rids:
            add(rid, 'REJECT', '行号', f'行号 {rid} 不存在于原表（请不要自行增行，缺项请走 02 表）')
            continue
        judge = (r.get('判定') or '').strip()

        if not judge:
            add(rid, 'REJECT', '未填', '「判定」列是空的'); continue
        if judge not in allowed:
            add(rid, 'REJECT', '枚举',
                f'判定「{judge}」不适用于本表（{rule["name"]}只能填 {" / ".join(sorted(allowed))}）'); continue

        ev_type = (r.get('依据类型') or '').strip()
        ev = (r.get('依据') or '').strip()
        conf = (r.get('置信度') or '').strip()
        if conf and conf not in ENUM_CONF:
            add(rid, 'REJECT', '枚举', f'置信度「{conf}」非法'); continue

        need_evid = judge in ('错误', '缺失待补', '应挂')
        if need_evid:
            if not ev_type or ev_type not in ENUM_EVID:
                add(rid, 'REJECT', '依据',
                    '判「%s」但依据类型未填或不在允许值' % judge); continue
            if not ev:
                add(rid, 'REJECT', '依据', f'判「{judge}」但依据为空'); continue
            if FILLER.search(ev):
                add(rid, 'REJECT', '依据', f'依据「{ev[:24]}…」属经验性表述，不可核查'); continue
            if len(ev) < 8:
                add(rid, 'REJECT', '依据', f'依据过短（{len(ev)} 字），无法复核'); continue

        # ── 01a 已挂载 ──
        if kind == '01a':
            cat_no = (r.get('产品编号') or '').strip()
            mid = (r.get('实体编号') or '').strip()
            if cat_no not in prods:
                add(rid, 'REJECT', '引用', f'产品编号 {cat_no} 不在产品清单内'); continue
            if mid not in methods:
                add(rid, 'REJECT', '引用', f'实体编号 {mid} 不在候选实体清单内'); continue
            if judge == '正确':
                add(rid, 'PASS', '通过'); continue
            if judge == '不确定':
                add(rid, 'REVIEW', '待裁决', f'专家自评不确定：{ev[:40] or "未写原因"}'); continue
            if judge == '应删':
                add(rid, 'REVIEW', '待二审', f'建议解除该挂载（原角色 {r.get("当前角色","")}），需确认')
                continue
            role = (r.get('建议角色') or '').strip()
            if role not in ENUM_ROLE:
                add(rid, 'REJECT', '枚举', f'建议角色「{role}」非法（{" / ".join(sorted(ENUM_ROLE))}）'); continue
            key = (mid, '角色')
            seen.setdefault(key, []).append((rid, role))
            add(rid, 'REVIEW', '待二审', f'角色 {r.get("当前角色","")} → {role}，需专业确认依据是否支持')
            continue

        # ── 01b 未挂载 ──
        if kind == '01b':
            cat_no = (r.get('产品编号') or '').strip()
            if cat_no not in prods:
                add(rid, 'REJECT', '引用', f'产品编号 {cat_no} 不在产品清单内'); continue
            if prods[cat_no]['mounted_methods']:
                add(rid, 'REJECT', '逻辑', f'{cat_no} 已经挂了方法，应走 01a 表'); continue
            if judge == '不确定':
                add(rid, 'REVIEW', '待裁决', f'专家自评不确定：{ev[:40] or "未写原因"}'); continue
            if judge == '不适用':
                add(rid, 'PASS', '通过'); continue
            mid = (r.get('应挂实体编号') or '').strip()
            if not mid:
                add(rid, 'REJECT', '逻辑', '判「应挂」但没填应挂实体编号'); continue
            if mid not in methods:
                add(rid, 'REJECT', '引用', f'应挂实体编号 {mid} 不在候选实体清单内'); continue
            role = (r.get('建议角色') or '').strip()
            if role not in ENUM_ROLE:
                add(rid, 'REJECT', '枚举', f'建议角色「{role}」非法'); continue
            key = (cat_no, '应挂-' + mid)
            seen.setdefault(key, []).append((rid, role))
            add(rid, 'REVIEW', '待二审', f'建议挂到「{methods[mid]["name"][:30]}」({role})，需确认')
            continue

        # ── 01c 实体字段 ──
        if kind == '01c':
            mid = (r.get('实体编号') or '').strip()
            field = (r.get('字段') or '').strip()
            cur = (r.get('当前值') or '').strip()
            if mid not in methods:
                add(rid, 'REJECT', '引用', f'实体编号 {mid} 不在候选实体清单内'); continue
            if field not in ENUM_FIELD:
                add(rid, 'REJECT', '枚举', f'字段「{field}」不在允许值'); continue
            if judge == '正确':
                add(rid, 'PASS', '通过'); continue
            if judge == '不确定':
                add(rid, 'REVIEW', '待裁决', f'专家自评不确定：{ev[:40] or "未写原因"}'); continue
            val = (r.get('正确值') or '').strip()
            if judge == '缺失待补' and cur != '（空）':
                add(rid, 'REJECT', '逻辑', f'当前值已有内容（{cur[:16]}…），应判「错误」而非「缺失待补」'); continue
            if not val:
                add(rid, 'REJECT', '逻辑', f'判「{judge}」但没填正确值'); continue
            key = (mid, field)
            seen.setdefault(key, []).append((rid, val))
            add(rid, 'REVIEW', '待二审', f'{field} 将改为「{val[:28]}…」，需确认')
            continue

    # 冲突回写
    conflicts = {k: v for k, v in seen.items() if len({x[1] for x in v}) > 1}
    ids = {r for vals in conflicts.values() for r, _ in vals}
    for it in out:
        if it['rid'] in ids and it['status'] in ('PASS', 'REVIEW'):
            it['status'] = 'REVIEW'
            it['cat'] = '待裁决-冲突'
            it['msg'] = '与另一条对同一对象给出了不同值，需人工裁决'
    return out, conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('subdir', help='回传目录（含 01a/01b/01c 回填文件）')
    ap.add_argument('--out', default=None, help='报告输出路径')
    a = ap.parse_args()

    prods, methods, orig = load_ref()
    sub = a.subdir if os.path.isabs(a.subdir) else os.path.join(COLLAB, a.subdir)
    files = sorted(f for f in os.listdir(sub) if f.lower().endswith('.csv'))
    if not files:
        sys.exit(f'{sub} 下没有 CSV')

    allres, allconf = [], {}
    for f in files:
        res, conf = check(f, read_csv(os.path.join(sub, f)), prods, methods, orig)
        allres += res
        allconf.update({(f, k[0], k[1]): v for k, v in conf.items()})

    from collections import Counter
    c = Counter(x['status'] for x in allres)
    L = ['# 校验回执\n', f'**回传目录**：`{a.subdir}`（{len(files)} 个文件，{len(allres)} 条）\n',
         '## 一、总体\n', '| 结论 | 条数 | 含义 |', '|---|---|---|',
         f'| ✅ 通过 | {c.get("PASS",0)} | 可进入待批准队列（仍需人工 approve） |',
         f'| ⚠️ 待裁决 | {c.get("REVIEW",0)} | 不自动入库，交人判断 |',
         f'| ❌ 退回 | {c.get("REJECT",0)} | 需修正后重交 |', '',
         '## 二、逐条\n', '| 行号 | 结论 | 分类 | 说明 |', '|---|---|---|---|']
    icon = {'PASS': '✅', 'REVIEW': '⚠️', 'REJECT': '❌'}
    for x in allres:
        L.append(f"| {x['rid']} | {icon[x['status']]} | {x['cat']} | {x['msg']} |")
    L.append('')
    L.append('## 三、冲突\n')
    if allconf:
        for (f, mid, field), vals in allconf.items():
            L.append(f"- {f} / 实体{mid} / {field}：" + '；'.join(f'{r} → 「{v}」' for r, v in vals))
    else:
        L.append('本批未发现冲突。')
    L.append('')
    L.append('## 四、退回类型\n')
    for k, v in Counter(x['cat'] for x in allres if x['status'] == 'REJECT').most_common():
        L.append(f'- {k}：{v} 条')

    rep = '\n'.join(L)
    out = a.out or os.path.join(sub, '校验回执.md')
    io.open(out, 'w', encoding='utf-8').write(rep)
    print(rep)
    print(f'\n报告已写入 {out}', file=sys.stderr)
    return 0 if c.get('REJECT', 0) == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
