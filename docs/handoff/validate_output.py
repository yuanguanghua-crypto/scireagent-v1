#!/usr/bin/env python3
"""validate_output.py — 接收第三方模型产出的第一道闸。

三个模式：
  --check       格式与覆盖率校验（Gate 1）
  --calibrate   金标准评分（Gate 2）
  --cross       与既有双模型交叉比对（Gate 3）

不依赖任何第三方库，直接 python3 运行。

用法：
  python validate_output.py --check     --input out.jsonl --expect 14975
  python validate_output.py --calibrate --input gold_out.jsonl --gold gold_set.jsonl
  python validate_output.py --cross     --input out.jsonl --flash flash.jsonl --pro pro.jsonl
"""
import argparse
import json
import sys
from collections import Counter, defaultdict

VALID_A = {'on_topic', 'tangential', 'wrong'}
VALID_CONF = {'high', 'medium', 'low'}
VALID_OVERALL = {'accept', 'accept_with_edits', 'reject'}
RULE_SET = {f'R{i}' for i in range(1, 8)}


def load_jsonl(path):
    rows, bad = [], []
    with open(path, encoding='utf-8-sig') as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((i, json.loads(line)))
            except json.JSONDecodeError as exc:
                bad.append((i, f'JSON 解析失败: {exc}'))
    return rows, bad


def err(errors, line, msg):
    errors.append(f'line {line}: {msg}')


def check_task_a(line, r, errors):
    for k in ('task', 'method_id', 'protocol_id', 'verdict',
              'confidence', 'reason'):
        if k not in r:
            err(errors, line, f'缺字段 {k}')
            return
    if r['verdict'] not in VALID_A:
        err(errors, line, f'非法 verdict {r["verdict"]!r}')
    if r['confidence'] not in VALID_CONF:
        err(errors, line, f'非法 confidence {r["confidence"]!r}')
    reason = (r.get('reason') or '').strip()
    if len(reason) < 5:
        err(errors, line, 'reason 过短')
    elif len(reason) > 240:
        err(errors, line, f'reason 过长 ({len(reason)} 字符)')


def check_task_b(line, r, errors, input_lines):
    for k in ('task', 'method_id', 'field', 'findings', 'overall'):
        if k not in r:
            err(errors, line, f'缺字段 {k}')
            return
    if r['field'] not in ('advantages', 'limitations'):
        err(errors, line, f'非法 field {r["field"]!r}')
    if r['overall'] not in VALID_OVERALL:
        err(errors, line, f'非法 overall {r["overall"]!r}')
    fs = r.get('findings')
    if not isinstance(fs, list) or not fs:
        err(errors, line, 'findings 必须是非空数组')
        return
    want = input_lines.get((r['method_id'], r['field']))
    seen = set()
    for f in fs:
        if 'line_index' not in f or 'pass' not in f or 'rule_violations' not in f:
            err(errors, line, 'finding 缺 line_index/pass/rule_violations')
            continue
        li = f['line_index']
        if isinstance(li, int):
            if li in seen:
                err(errors, line, f'finding 重复 line_index={li}')
            seen.add(li)
            if want is not None and not (0 <= li < want):
                err(errors, line, f'line_index={li} 超出范围 (共 {want} 行)')
        for rv in f.get('rule_violations') or []:
            if rv not in RULE_SET:
                err(errors, line, f'非法规则编号 {rv!r}')
        if f.get('pass') is False and not (f.get('rule_violations') or []):
            err(errors, line, f'line_index={li} pass=false 但未给规则编号')
    if want is not None and len(seen) != want:
        err(errors, line, f'finding 数 {len(seen)} ≠ 输入行数 {want}')


def mode_check(args):
    rows, bad = load_jsonl(args.input)
    errors = [f'line {ln}: {m}' for ln, m in bad]

    input_lines = {}
    if args.task_b_input:
        for _, r in load_jsonl(args.task_b_input)[0]:
            input_lines[(r['method_id'], r['field'])] = len(r.get('lines') or [])

    keys = Counter()
    counts = Counter()
    for ln, r in rows:
        task = r.get('task')
        counts[task] += 1
        if task == 'A':
            check_task_a(ln, r, errors)
            keys[(r.get('method_id'), r.get('protocol_id'))] += 1
        elif task == 'B':
            check_task_b(ln, r, errors, input_lines)
        else:
            err(errors, ln, f'未知 task {task!r}')

    dups = [k for k, v in keys.items() if v > 1]
    for k in dups[:10]:
        errors.append(f'重复 (method_id, protocol_id) = {k}')

    print('=' * 74)
    print('Gate 1 — 格式与覆盖率')
    print('=' * 74)
    print(f'  文件      {args.input}')
    print(f'  有效行    {len(rows):,}')
    print(f'  task 分布 {dict(counts)}')
    if args.expect:
        got = counts.get('A', 0)
        ok = got == args.expect
        print(f'  期望 A 行 {args.expect:,}｜实际 {got:,}  '
              f'{"OK" if ok else "MISMATCH"}')
        if not ok:
            errors.append(f'A 行数 {got} ≠ 期望 {args.expect}')
    print(f'  重复键    {len(dups)}')
    print(f'  错误      {len(errors)}')
    for e in errors[:15]:
        print(f'    ! {e}')
    if len(errors) > 15:
        print(f'    ... 另 {len(errors) - 15} 条')
    print()
    print('  结论：' + ('通过' if not errors else '不通过 — 整批退回'))
    return 0 if not errors else 1


def mode_calibrate(args):
    gold = {}
    for _, r in load_jsonl(args.gold)[0]:
        gold[(r['method_id'], r['protocol_id'])] = (r['expected_verdict'], r.get('tier', '?'))

    rows, bad = load_jsonl(args.input)
    by_key = {}
    for _, r in rows:
        if r.get('task') == 'A':
            by_key[(r.get('method_id'), r.get('protocol_id'))] = r.get('verdict')

    stat = defaultdict(lambda: [0, 0])
    conf = defaultdict(Counter)
    by_exp = Counter()   # (expected, predicted) → count
    missing = 0
    for k, (exp, tier) in gold.items():
        pred = by_key.get(k)
        if pred is None:
            missing += 1
            continue
        ok = pred == exp
        by_exp[(exp, pred)] += 1
        stat[tier][1] += 1
        stat['ALL'][1] += 1
        if ok:
            stat[tier][0] += 1
            stat['ALL'][0] += 1
        conf[exp][pred] += 1

    print('=' * 74)
    print('一致性分析（不是考试：两边判断的吻合程度）')
    print('=' * 74)
    print(f'  比对基准 {len(gold)} 条｜对方漏判 {missing} 条')
    print('  ⚠️ 基准来自同一作者：author_read 是作者自读、model_agreement 是作者调用的')
    print('     两个模型互相同意。**没有任何一条来自独立人类专家**。')
    print('     所以下面的一致性百分比只说明"两边有多像"，不说明"谁对"。')
    for tier in ('author_read', 'model_agreement', 'ALL'):
        if tier not in stat:
            continue
        c, n = stat[tier]
        acc = c / n if n else 0
        print(f'  {tier:<10} {c:>3}/{n:<3} = {acc * 100:>5.1f}%  '
              )

    # 三档分别看：tangential 是最难的一档，单独报
    print()
    print('  按期望判定分档：')
    for lab in ('on_topic', 'wrong', 'tangential'):
        tot = sum(v for (e, _p), v in by_exp.items() if e == lab)
        ok = sum(v for (e, p), v in by_exp.items() if e == lab and p == lab)
        if tot:
            print(f'    {lab:<11} {ok:>2}/{tot:<2} = {ok * 100 / tot:>5.1f}%'
                  + ('  ← 最难的一档，单独看' if lab == 'tangential' else ''))
    print()
    print('  混淆矩阵（行=期望，列=实际）：')
    labels = ['on_topic', 'tangential', 'wrong']
    print('  ' + ' ' * 12 + ''.join(f'{x:>12}' for x in labels))
    for a in labels:
        print(f'  {a:<12}' + ''.join(f'{conf[a].get(b, 0):>12}' for b in labels))

    acc_all = stat['ALL'][0] / stat['ALL'][1] if stat['ALL'][1] else 0
    acc_h = stat.get('author_read', [0, 0])
    acc_c = stat.get('model_agreement', [0, 0])
    gap = (acc_c[0] / acc_c[1] - acc_h[0] / acc_h[1]) if acc_c[1] and acc_h[1] else 0
    print()
    print(f'  总体一致性 {acc_all * 100:.1f}%｜author_read↔model_agreement 落差 {gap * 100:+.1f}pp')
    print()
    print('  怎么读这个数字：')
    print('    · 一致性高 ≠ 判得对。两个模型可能同时错。')
    print('    · 一致性低 ≠ 判得错。很可能是我这边的判据有问题。')
    print('    · 真正有价值的产出是【分歧清单】—— 那才是需要人工看的地方。')
    if acc_all >= 0.85:
        print('    · 当前一致性较高，可以放量，但结果仍需抽样人工核。')
    else:
        print('    · 当前一致性偏低。先别放量：优先复查是不是判据本身有歧义。')
    return 0


def mode_cross(args):
    def loadmap(p):
        d = {}
        for _, r in load_jsonl(p)[0]:
            d[(r.get('method_id'), r.get('protocol_id'))] = r.get('verdict') or r.get('label')
        return d

    third = loadmap(args.input)
    fl = loadmap(args.flash) if args.flash else {}
    pr = loadmap(args.pro) if args.pro else {}

    pat = Counter()
    escalate = []
    for k, v in third.items():
        f, p = fl.get(k), pr.get(k)
        if not f or not p:
            continue
        s = {f, p, v}
        if len(s) == 1:
            pat['三方一致'] += 1
        elif len(s) == 2:
            odd = [x for x in (f, p, v) if list(s).count(x) == 1]
            if odd and odd[0] == 'tangential':
                pat['2:1 且少数派是 tangential'] += 1
            else:
                pat['2:1 且少数派是 wrong/on_topic'] += 1
                escalate.append((k, f, p, v))
        else:
            pat['三方全不一致'] += 1
            escalate.append((k, f, p, v))

    n = sum(pat.values())
    print('=' * 74)
    print('Gate 3 — 三方交叉结构')
    print('=' * 74)
    print(f'  可比对 {n:,} 条')
    for k, v in pat.most_common():
        print(f'    {k:<28} {v:>7,} ({v * 100 / max(1, n):>5.1f}%)')
    print()
    print(f'  需人工仲裁 {len(escalate):,} 条'
          + (f'（前 10 例）' if escalate else ''))
    for k, f, p, v in escalate[:10]:
        print(f'    method={k[0]} protocol={k[1]}  flash={f} pro={p} third={v}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--cross', action='store_true')
    ap.add_argument('--input', required=True)
    ap.add_argument('--gold', default='gold_answers.jsonl',
                    help='答案文件（gold_answers.jsonl，**不要发给对方**）')
    ap.add_argument('--flash', default='')
    ap.add_argument('--pro', default='')
    ap.add_argument('--task-b-input', default='input_task_b.jsonl')
    ap.add_argument('--expect', type=int, default=0)
    a = ap.parse_args()
    if a.check:
        return mode_check(a)
    if a.calibrate:
        return mode_calibrate(a)
    if a.cross:
        return mode_cross(a)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
