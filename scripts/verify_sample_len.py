# -*- coding: utf-8 -*-
"""
输入侧校验：盲测批的 objective / steps 有没有被你的查看器截断

背景（2026-11-02）：曹操把一条 4,894 字符的 objective 看成截断版，漏读了一句
"size selected on a denaturing SDS-PAGE gel"，把该判 tangential 的判成了 wrong。
盲测批里最长的一条单行也有 3,167 字符，同一类风险存在。

怎么用:
  python scripts/verify_sample_len.py
  python verify_sample_len.py --batch 03_SAMPLES_33.json

输出:
  逐条打印 声明值 / 实测值 / 结论；全部相符才 exit 0，否则 exit 1。

纪律（本脚本做到的）:
  · 只读，不写任何文件
  · 不联网
  · 不读你的判定文件，不读别人的文件
  · 不算 κ、不算任何统计量

⚠️ 本脚本跑的是**原始 JSON 文件**，与你在某处"看"到的字符串是两回事。
   如果它全 ✅ 而你肉眼看到的长度不一样 —— 那是你的查看器在截断，请换工具重看。
"""
import argparse
import json
import os
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


DEFAULT = _default_batch()


def measure(rec):
    steps = rec.get("steps") or []
    if isinstance(steps, str):
        steps = json.loads(steps)
    return len(rec.get("objective") or ""), len(steps), sum(len(s.get("text") or "") for s in steps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=DEFAULT)
    a = ap.parse_args()

    if not os.path.exists(a.batch):
        sys.exit("找不到盲测批: %s" % a.batch)

    recs = json.load(open(a.batch, encoding="utf-8"))
    print("盲测批: %s  (%d 条)" % (os.path.basename(a.batch), len(recs)))
    print()
    print("  %-6s %-26s %-14s %s" % ("bridge", "objective_len 声明/实测", "n_steps", "steps_len 声明/实测  结论"))

    bad = []
    missing = []
    for r in recs:
        b = r.get("bridge_id")
        need = ("objective_len", "n_steps", "steps_len")
        if not all(k in r for k in need):
            missing.append(b)
            continue
        o, n, s = measure(r)
        ok = (r["objective_len"] == o and r["n_steps"] == n and r["steps_len"] == s)
        print("  %-6s %8d / %-8d %4d / %-3d %8d / %-8d  %s"
              % (b, r["objective_len"], o, r["n_steps"], n, r["steps_len"], s,
                 "✅" if ok else "❌ 不符"))
        if not ok:
            bad.append(b)

    print()
    if missing:
        print("❌ 有 %d 条缺三字段: %s" % (len(missing), missing))
        print("   ⇒ 这多半是**旧的、没有校验字段的批**。请联系组织方换新批，不要用旧批判定。")
        return 1
    if bad:
        print("❌ %d 条声明与实测不符: %s" % (len(bad), bad))
        print("   ⇒ 文件本身有问题，请把这份输出报给组织方，**先不要开始判**。")
        return 1

    print("✅ %d/%d 全部相符 —— 文件里的 objective 与 steps 是完整的。" % (len(recs), len(recs)))
    print()
    print("⚠️ 但这一步只证明**文件**是完整的，不证明**你看到的是完整的**。")
    print("   如果你在查看器里看到的 objective 明显比上面 objective_len 短，")
    print("   或步骤条数少于 n_steps —— 那是查看器截断，请换编辑器 / 用程序读，再看一遍。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
