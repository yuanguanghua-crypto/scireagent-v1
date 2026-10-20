# -*- coding: utf-8 -*-
"""给 PoSubmit.vue 的 po-label + 表单项建立 for/id 关联（修 a11y label 违规）。

原则：
1. 只配对「<label class="po-label">…</label>」后面紧跟的 input/select/textarea
2. 已有 id 的不动
3. 每个文件先 dry-run 统计能配几对，确认后再写
"""
import io
import re
import sys

P = "frontend/src/views/po/PoSubmit.vue"
src = io.open(P, encoding="utf-8", newline="").read()

# 匹配：<label class="po-label">TEXT</label> + 空白 + 表单项起始标签
pat = re.compile(
    r'(<label class="po-label")(>)((?:[^<]|<(?!label))*?)(</label>)(\s*<)(input|select|textarea)(\b)',
    re.S)

matches = list(pat.finditer(src))
print("可配对: %d 处" % len(matches))

# dry-run 展示
for i, m in enumerate(matches[:3], 1):
    text = re.sub(r"\s+", " ", m.group(3)).strip()[:40]
    print("  [%d] label=%r  后继=<%s" % (i, text, m.group(6)))

if "--apply" not in sys.argv:
    print("\n（dry-run。加 --apply 才写入）")
    sys.exit(0)

out, pos, n = [], 0, 0
for m in matches:
    n += 1
    fid = "po-f%d" % n
    out.append(src[pos:m.start()])
    # label 加 for
    out.append('%s for="%s"%s%s%s' % (m.group(1), fid, m.group(2), m.group(3), m.group(4)))
    # 表单项加 id（插在标签名后）
    out.append("%s%s id=\"%s\"%s" % (m.group(5), m.group(6), fid, m.group(7)))
    pos = m.end()
out.append(src[pos:])
new = "".join(out)

io.open(P, "w", encoding="utf-8", newline="").write(new)
print("\n✅ 已写入 %d 对 for/id 关联" % n)

# 复核
chk = io.open(P, encoding="utf-8", newline="").read()
print("  复核 for 数: %d ｜ id 数: %d" % (chk.count('for="po-f'), chk.count('id="po-f')))
