"""build_protocol_q_cache —— 把「协议侧领域词集合 Q」离线预算成文件。

## 为什么需要

`auto_links.recommend_protocols_for_enrich` 的**草稿分支**（新品页 / AI 预览）要按
`P(品名或 usage) ∩ Q(每个协议)` 给**全库协议**打分，Q 由 `_extract_domains(_protocol_q_text(p))` 现算。
实测（2026-09-24，i7-13700KF，14,084 条协议）：

| 方式 | 耗时 |
|---|---|
| 实时全库预计算（`compute_q_cache`） | **21.97s** |
| 读本命令产出的文件 | **0.007s**（3,000×） |

该 21.97s 是**进程级冷启动**，`gunicorn --workers 2` ⇒ 每个 worker 各付一次；用户首次点
「AI AUTO MATCH」会直接卡住。本命令把它**移到离线**。

## 指纹（安全阀）

产出文件带 `_meta = {protocol_count, max_id}`。`auto_links._load_q_cache_from_file()` 读取时会与
**库中实测值**比对：**不符 ⇒ 回退实时计算**（慢一次，但结果永远正确）。
这保证「协议被策展新增/删除后缓存陈旧」不会产生错误推荐，也不会让新协议永远不被推荐。

## 用法

```bash
# 生成 / 刷新（默认写文件；原子替换）
python manage.py build_protocol_q_cache

# 只看规模与耗时，不写盘
python manage.py build_protocol_q_cache --dry-run

# 只校验现有文件是否与库一致（部署后核验 / CI 用；不一致 exit 1）
python manage.py build_protocol_q_cache --check
```
"""
import json
import os
import tempfile
import time

from django.core.management.base import BaseCommand

from apps.bridges.services import auto_links as A


class Command(BaseCommand):
    help = '离线预算协议侧领域词 Q 集合并写入 data/protocol_q_cache.json（消除 21.97s 冷启动）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只报告，不写盘')
        parser.add_argument('--check', action='store_true',
                            help='只校验现有文件与库是否一致；不一致 exit 1')

    def handle(self, *args, **options):
        path = A._Q_CACHE_PATH
        live = A._q_cache_fingerprint()

        if options['check']:
            if not os.path.isfile(path):
                self.stderr.write(self.style.ERROR(f'✘ 缓存文件不存在：{path}'))
                raise SystemExit(1)
            with open(path, encoding='utf-8') as fh:
                payload = json.load(fh)
            meta = payload.get(A._Q_CACHE_META_KEY) or {}
            # ★ 整体比较（与 `_load_q_cache_from_file` 同一口径）⇒ 词表哈希 / 协议文本指纹
            #   一并纳入；将来加字段自动生效，不会再出现"加载端改了、命令端忘了"的偏差。
            same = (meta == live)
            if same:
                self.stdout.write(self.style.SUCCESS(
                    f'✔ 缓存新鲜：{path}（{len(payload.get("q") or {})} 条，{meta}）'))
                return
            self.stderr.write(self.style.ERROR(
                f'✘ 缓存陈旧：文件 {meta} vs 实测 {live} ⇒ 请重跑 build_protocol_q_cache'))
            raise SystemExit(1)

        t0 = time.time()
        cache = A.compute_q_cache()
        elapsed = time.time() - t0
        trimmed = {str(k): sorted(v) for k, v in cache.items() if v}
        payload = {A._Q_CACHE_META_KEY: live, 'q': trimmed}
        blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        size_kb = len(blob.encode('utf-8')) / 1024.0

        self.stdout.write(
            f'协议总数={live["protocol_count"]} max_id={live["max_id"]} '
            f'Q 非空={len(trimmed)} 预算耗时={elapsed:.2f}s 体积={size_kb:.1f}KB')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run：未写盘'))
            return

        # 原子替换：先写临时文件再 os.replace ⇒ 别的进程绝不会读到半个文件
        d = os.path.dirname(path)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix='.qcache-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(blob)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        self.stdout.write(self.style.SUCCESS(f'✔ 已写入 {path}（{size_kb:.1f}KB）'))
