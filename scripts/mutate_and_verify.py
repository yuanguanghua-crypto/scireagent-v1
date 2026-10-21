#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""变异验证器 —— 一条命令完成「改坏 → 证明测试能红 → 复原」，每一步强制自证

## 为什么需要它
2026-10-21 一天做了 8 次变异验证，踩了 3 个坑，**全部是"假绿"性质**：
  ① **CRLF 锚点不匹配** ⇒ `replace()` 静默返回原串 ⇒ 报"注入成功"其实没改到文件
     （实测踩了两次，跑出来 20 passed 是假的）
  ② 只看"测试跑了"就下结论 ⇒ 没红就说"测试太强"，实际可能是变异根本没生效
  ③ 复原后不校验 ⇒ 曾遇到 `git checkout --` 后文件 sha 变了（CRLF→LF 归一化）
     但 `git diff` 为空 —— 只看 sha 会误判"改坏了"
人眼几乎无法区分「变异没生效」和「测试太强所以不红」。只有工具能立刻发现。
所以把这三步变成**强制自证**，任何一步不自证就退出，不给"看起来成功"的机会。

## 用法
```bash
# 在 src_claude/ 下
python scripts/mutate_and_verify.py \\
    --file backend/apps/inventory/services.py \\
    --old ".select_for_update()" --new "" \\
    --test apps/inventory/tests/test_pg_concurrency.py

# 需要 PG 的用例：先在环境里导好 DB_*，脚本会原样继承
DB_ENGINE=django.db.backends.postgresql DB_NAME=scireagent_l4 \\
DB_USER=scireagent DB_HOST=127.0.0.1 DB_PORT=5433 \\
python scripts/mutate_and_verify.py --file ... --old ... --test ...
```

## 退出码
0 = 变异有效（测试确实变红）且已复原且无残留
2 = 参数/文件问题    3 = 变异没生效（锚点未命中或内容未变）
4 = 测试没抓到（变异后仍然全绿 ⇒ 这些测试是摆设，或变异点选错了）
5 = 复原失败（文件内容与原内容不一致 —— **立即人工处理，别提交**）
6 = 复原后仍有 MUTATION 残留
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
BACKEND = os.path.join(PROJECT, 'backend')


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='要变异的源文件（相对 src_claude/ 或绝对路径）')
    ap.add_argument('--old', required=True, help='要替换掉的片段')
    ap.add_argument('--new', default='', help='替换成什么（默认空串 = 直接删掉）')
    ap.add_argument('--test', required=True, help='用来验证的 pytest 目标（相对 backend/）')
    ap.add_argument('--count', type=int, default=0, help='只替换前 N 处（默认 0 = 全部）')
    ap.add_argument('--keep', action='store_true', help='验证完**不复原**（调试用，慎用）')
    args = ap.parse_args()

    path = args.file if os.path.isabs(args.file) else os.path.join(PROJECT, args.file)
    if not os.path.exists(path):
        print(f'❌ 文件不存在：{path}')
        return 2

    # ── 0. 备份原始字节（复原要用原样 bytes，不能用归一化后的）───────────
    original_bytes = open(path, 'rb').read()
    original_md5 = _md5(original_bytes)

    # ── 1. 归一化 CRLF 后再匹配（坑①：不归一化则锚点静默不命中）─────────
    content = original_bytes.decode('utf-8')
    normalized = content.replace('\r\n', '\n')
    hits = normalized.count(args.old)
    if hits == 0:
        print('❌ 变异没生效：锚点未命中（0 处）。')
        print('   ⚠️ 这是 2026-10-21 踩过两次的坑 —— CRLF 与 \\n 不匹配会让')
        print('   replace() 静默返回原串，而脚本却报"注入成功"。')
        print(f'   检查 --old 是否与文件内容逐字一致（含缩进）。文件行数 {normalized.count(chr(10)) + 1}')
        return 3
    line_nos = [i + 1 for i, l in enumerate(normalized.splitlines()) if args.old in l]
    print(f'✅ 锚点命中 {hits} 处，行号 {line_nos[:10]}')

    if args.old == args.new:
        print('❌ --old 与 --new 相同，无法产生变异。')
        return 2
    new_content = normalized.replace(args.old, args.new, args.count or -1)

    # ── 2. 写回并**确认内容真的变了**（坑①的第二道防线）──────────────────
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    mutated_md5 = _md5(open(path, 'rb').read())
    if mutated_md5 == original_md5:
        print('❌ 变异没生效：写入后文件 md5 未变化。')
        return 3
    print(f'✅ 变异已落地（md5 {original_md5[:8]} → {mutated_md5[:8]}），开始跑测试…')

    exit_code = 0
    try:
        # ── 3. 跑测试，**必须变红**，且必须是 FAILED 而不是 ERROR ─────────
        cmd = [os.path.join(BACKEND, 'venv', 'Scripts', 'python.exe'),
               '-m', 'pytest', args.test, '-q', '-p', 'no:cacheprovider']
        r = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
        out = (r.stdout or '') + (r.stderr or '')
        tail = '\n'.join(out.splitlines()[-6:])

        if r.returncode == 0:
            print('❌ 测试没抓到变异（仍然全绿）⇒ 这些测试是摆设，或变异点选错了。')
            print('   这不是"测试太强"，而是"测试没在测这个"。')
            print(tail)
            exit_code = 4
        elif 'FAILED' not in out:
            # 红是因为代码坏了（语法/导入错误），不是断言失败 —— 这种"红"没有意义。
            # 反面教训：mutation_check.py 曾只数 FAILED 行，把整片 ERROR 当成"没问题"。
            print('❌ 变红的原因是 ERROR（代码坏了），不是断言失败 ⇒ 这次变异无效。')
            print(tail)
            exit_code = 3
        else:
            failed = [l.strip() for l in out.splitlines() if l.strip().startswith('FAILED')]
            print(f'✅ 测试如预期变红（{len(failed)} 条 FAILED）：')
            for l in failed[:5]:
                print(f'   {l}')
            exit_code = 0
    finally:
        # ── 4. 复原 + **校验内容逐字节回到原样**（坑③）──────────────────
        if args.keep:
            print('⚠️ --keep：未复原。文件仍是变异状态，别忘了手动处理！')
        else:
            with open(path, 'wb') as f:
                f.write(original_bytes)
            restored_md5 = _md5(open(path, 'rb').read())
            if restored_md5 != original_md5:
                print(f'❌ 复原失败：md5 {restored_md5[:8]} != 原始 {original_md5[:8]}')
                print('   **立即处理，不要提交**。建议：git diff <文件> 检查')
                return 5
            print(f'✅ 已复原（md5 回到 {original_md5[:8]}）')

            # ── 5. 残留检查 ─────────────────────────────────────────────
            body = open(path, encoding='utf-8').read()
            if 'MUTATION' in body and 'MUTATION' not in content:
                print('❌ 复原后文件里出现 MUTATION 字样 ⇒ 有残留，立即处理。')
                return 6

    if exit_code == 0:
        print('\n结论：变异有效 —— 这条测试确实能发现该缺陷；文件已复原。')
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
