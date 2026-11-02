# -*- coding: utf-8 -*-
"""
输出侧校验：你自己交回的判定文件格式对不对

只管格式，不判别定对错，不算 κ。

怎么用:
  python verify_annotator_output.py --batch 03_SAMPLES_33.json --mine 你的输出.jsonl


校验项（全部通过才 exit 0）:
  1. 每行是合法 JSON，且只有一个对象
  2. 行数与盲测批条数**完全一致**（条数取自 --batch，不写死）
  3. 只允许 bridge_id / verdict / why 三个字段（多一个都不行）
  4. bridge_id 与盲测批**逐条对得上**（不缺、不多、不重复）
  5. verdict ∈ {on_topic, tangential, wrong}
  6. why 非空、且不含中日韩字符（本项目的判定理由须英文）

纪律（本脚本做到的）:
  · 只读，不写任何文件
  · 不联网
  · **只读你自己那一份**，不读别人的，不算 κ、不算任何统计量
  · 正式 κ 只由组织方计算

⚠️ 不要拿自己的文件当两份输入去算 κ —— 那会得到毫无意义的 κ=1.000。
   组织方之所以不把 κ 计算器放进你的包，就是为了不给这个口子。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
def _default_batch():
    """自适应：优先当前目录的包内批 → 本轮新批 → 上一轮旧批。"""
    for c in ("03_SAMPLES_33.json",
              os.path.join(ROOT, "work", "_sds_v3_batch_20261102.json"),
              os.path.join(ROOT, "work", "p0_sds_page_kappa_batch.json")):
        if os.path.isfile(c):
            return c
    return "03_SAMPLES_33.json"


DEFAULT_BATCH = _default_batch()
LABELS = ("on_topic", "tangential", "wrong")
ALLOWED = {"bridge_id", "verdict", "why"}
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\uff00-\uffef]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", required=True)
    ap.add_argument("--batch", default=DEFAULT_BATCH)
    a = ap.parse_args()

    if not os.path.exists(a.mine):
        sys.exit("找不到你的判定文件: %s" % a.mine)
    if not os.path.exists(a.batch):
        sys.exit("找不到盲测批: %s" % a.batch)

    batch = json.load(open(a.batch, encoding="utf-8"))
    want = [r["bridge_id"] for r in batch]

    rows, errs = [], []
    for i, line in enumerate(open(a.mine, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append("第 %d 行不是合法 JSON: %s" % (i, e))
            continue
        if not isinstance(r, dict):
            errs.append("第 %d 行不是对象" % i)
            continue

        extra = set(r) - ALLOWED
        if extra:
            errs.append("第 %d 行有多余字段 %s（只允许 bridge_id / verdict / why）" % (i, sorted(extra)))
        miss = ALLOWED - set(r)
        if miss:
            errs.append("第 %d 行缺字段 %s" % (i, sorted(miss)))

        v = r.get("verdict")
        if v not in LABELS:
            errs.append("第 %d 行 verdict 非法: %r（只能是 %s）" % (i, v, list(LABELS)))

        w = r.get("why")
        if not isinstance(w, str) or not w.strip():
            errs.append("第 %d 行 why 为空" % i)
        elif CJK.search(w):
            errs.append("第 %d 行 why 含中日韩字符（判定理由须英文）" % i)

        rows.append((i, r.get("bridge_id")))

    if errs:
        print("❌ 格式问题 %d 处：" % len(errs))
        for e in errs:
            print("   -", e)
        return 1

    got = [b for _, b in rows]
    if len(got) != len(want):
        print("❌ 行数不对：你交了 %d 条，盲测批有 %d 条" % (len(got), len(want)))
        d = [b for b in want if b not in got]
        x = [b for b in got if b not in want]
        if d:
            print("   缺:", d)
        if x:
            print("   多:", x)
        return 1
    if len(set(got)) != len(got):
        dup = [b for b in set(got) if got.count(b) > 1]
        print("❌ bridge_id 重复:", dup)
        return 1
    if set(got) != set(want):
        print("❌ 编号与盲测批对不上")
        print("   缺:", sorted(set(want) - set(got)))
        print("   多:", sorted(set(got) - set(want)))
        return 1

    order = "顺序与批一致" if got == want else "顺序与批不同（可接受）"
    print("✅ 格式校验通过：%d/%d 条，编号逐条对得上，字段与 verdict 合法，why 均为英文非空。" % (len(got), len(want)))
    print("   %s" % order)
    print()
    print("⚠️ 这只是**格式**通过，不代表判定正确。正式 κ 由组织方计算，不要自己算。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
