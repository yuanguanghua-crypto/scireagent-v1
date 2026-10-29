#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md_to_pdf.py —— 把 Markdown 转成排版正确的中文 PDF。

## 为什么不用 pandoc / wkhtmltopdf
本机三者都没有（pandoc / wkhtmltopdf / weasyprint 皆无）。而项目里**已经有 Playwright
（msedge）**——用它把 HTML 打印成 PDF，中文字体走系统字体栈，表格/代码块/分页都能精确
控制，且**零新增系统依赖**。代价是要先装一个 Python 的 `markdown` 库（纯 Python，无二进制）。

## 为什么要单独写脚本而不是一行命令
项目里文档会持续产出（知识实体说明、口径文档、验收报告…），每次手写一遍 HTML 模板
必然漂移。这里把「打印样式」固定成一份，保证所有文档转出来长得一样。

## 用法
    backend/venv/Scripts/python.exe scripts/md_to_pdf.py docs/KNOWLEDGE_ENTITIES_BRIEF.md
    # 输出到 deliverables/KNOWLEDGE_ENTITIES_BRIEF.pdf
    ... scripts/md_to_pdf.py <in.md> -o out.pdf
    ... scripts/md_to_pdf.py <in.md> --open      # 转完用默认程序打开

## 排版约定
- A4 / 页边距 16mm / 1.6 行距
- 中文优先 `Microsoft YaHei`，代码 `Consolas`
- 表格：整表不跨页；代码块：浅灰底 + 左侧色条
- 页脚居中页码（`第 n / N 页`）—— playwright 的 footerTemplate 只在有页边距时显示
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ── 打印样式（唯一真相源）──────────────────────────────────────────────
CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; }
* { box-sizing: border-box; }
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB",
               "Source Han Sans SC", "Noto Sans CJK SC", sans-serif;
  font-size: 10.5pt; line-height: 1.62; color: #1f2937;
  margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 20pt; margin: 0 0 6pt; color: #111827; letter-spacing: -0.01em;
     border-bottom: 2.5pt solid #0ea5a4; padding-bottom: 6pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; color: #0f766e;
     border-left: 4pt solid #0ea5a4; padding-left: 8pt; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; color: #111827; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10pt 0 3pt; color: #374151; page-break-after: avoid; }
p  { margin: 0 0 7pt; }
a  { color: #0f766e; text-decoration: none; }
strong { color: #b91c1c; font-weight: 700; }
em { font-style: normal; background: #fef3c7; padding: 0 2pt; }
hr { border: none; border-top: 1pt solid #e5e7eb; margin: 14pt 0; }
ul, ol { margin: 0 0 8pt; padding-left: 18pt; }
li { margin: 0 0 3pt; }
blockquote {
  margin: 8pt 0; padding: 7pt 10pt; background: #f0fdfa;
  border-left: 3pt solid #14b8a6; color: #134e4a; font-size: 10pt;
}
blockquote p:last-child { margin-bottom: 0; }
code {
  font-family: Consolas, "Courier New", monospace; font-size: 9.5pt;
  background: #f3f4f6; padding: 1pt 3pt; border-radius: 2pt; color: #7c2d12;
}
pre {
  background: #f8fafc; border: 1pt solid #e2e8f0; border-left: 3pt solid #94a3b8;
  border-radius: 3pt; padding: 8pt 10pt; margin: 8pt 0; overflow: hidden;
  page-break-inside: avoid; font-size: 9pt; line-height: 1.5;
}
pre code { background: none; padding: 0; color: #334155; font-size: 9pt; }
table {
  width: 100%; border-collapse: collapse; margin: 8pt 0 10pt;
  font-size: 9.5pt; page-break-inside: avoid;
}
th, td { border: 0.75pt solid #d1d5db; padding: 4pt 6pt; text-align: left;
         vertical-align: top; }
/* 表格跨页时表头必须重复，否则第二页起读者不知道列是什么 */
thead { display: table-header-group; }
tfoot { display: table-footer-group; }
tr { page-break-inside: avoid; }
th { background: #f1f5f9; font-weight: 700; color: #0f172a; }
tbody tr:nth-child(even) { background: #fafafa; }
"""

HTML_SHELL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title><style>{css}</style></head>
<body>{body}</body></html>
"""

# ── playwright 打印（Node 一行）────────────────────────────────────────
# 注意：不用 headerTemplate（页头留空），只用 footer 打页码。
NODE_PRINT = r"""
const { chromium } = require('@playwright/test');
(async () => {
  const [htmlPath, pdfPath, title] = process.argv.slice(1);
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage();
  await page.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="width:100%;font-size:8pt;color:#6b7280;'
      + 'text-align:center;font-family:Microsoft YaHei,sans-serif;">'
      + '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: { top: '16mm', bottom: '18mm', left: '14mm', right: '14mm' },
  });
  await browser.close();
})();
"""


def md_to_html(md_text: str) -> tuple[str, str]:
    """返回 (title, body_html)。"""
    try:
        import markdown  # 纯 Python 依赖，见脚本 docstring
    except ImportError:
        sys.exit('缺少 markdown 库：backend/venv/Scripts/python.exe -m pip install markdown')

    title = 'Document'
    for line in md_text.splitlines():
        m = re.match(r'^#\s+(.+)$', line.strip())
        if m:
            title = m.group(1).strip()
            break
    body = markdown.markdown(
        md_text,
        extensions=['tables', 'fenced_code', 'sane_lists', 'toc'],
        output_format='html5',
    )
    return title, body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Markdown → 中文排版 PDF')
    ap.add_argument('src', help='输入的 .md 文件')
    ap.add_argument('-o', '--out', default=None, help='输出 .pdf（默认 deliverables/<name>.pdf）')
    ap.add_argument('--open', action='store_true', help='转换后用默认程序打开')
    args = ap.parse_args(argv)

    src = Path(args.src).resolve()
    if not src.is_file():
        sys.exit(f'找不到输入文件：{src}')
    out = Path(args.out).resolve() if args.out else (REPO / 'deliverables' / (src.stem + '.pdf'))
    out.parent.mkdir(parents=True, exist_ok=True)

    title, body = md_to_html(src.read_text(encoding='utf-8'))
    page = HTML_SHELL.format(title=html.escape(title), css=CSS, body=body)

    tmp_html = Path(tempfile.gettempdir()) / f'_mdtmp_{src.stem}.html'
    tmp_html.write_text(page, encoding='utf-8')

    node_dir = REPO / 'frontend'  # 在 frontend 里跑，才能 require 到 @playwright/test
    if not (node_dir / 'node_modules' / '@playwright' / 'test').is_dir():
        sys.exit('找不到 @playwright/test（需要 frontend/node_modules 已安装）')

    proc = subprocess.run(
        ['node', '-e', NODE_PRINT, str(tmp_html), str(out), title],
        cwd=str(node_dir), capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180,
    )
    if proc.returncode != 0 or not out.is_file():
        print(proc.stdout[-1500:], file=sys.stderr)
        print(proc.stderr[-1500:], file=sys.stderr)
        sys.exit('PDF 生成失败')

    size_kb = out.stat().st_size / 1024
    print(f'✅ {src.name} → {out}  ({size_kb:.0f} KB)')
    tmp_html.unlink(missing_ok=True)

    if args.open:
        os.startfile(str(out))  # Windows
    return 0


if __name__ == '__main__':
    sys.exit(main())
