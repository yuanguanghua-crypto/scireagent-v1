#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""录制外部数据源的真实响应到 cassette（`backend/cassettes/*.jsonl`）

## 为什么要有这个脚本
`core/http_cassette.py` 提供录制/回放能力，但**必须有人先把真实响应录下来**，
否则回放模式永远 miss。这个脚本就是"录音"按钮。

## 关键设计：调**真实业务函数**，不手拼 URL
cassette 的 key 由 `method + host + path + 排序后的 query + body` 决定。
如果脚本里手写 URL，就与生产代码（`PubChemClient.lookup_by_cas` 等）构造的
URL/params 不一致 ⇒ key 不同 ⇒ 回放必然 miss。
所以这里一律调用**业务入口**，让录制与真实调用走同一条路径。

## 用法
```bash
cd backend
venv/Scripts/python.exe ../scripts/record_datasources.py          # 录全部目标
venv/Scripts/python.exe ../scripts/record_datasources.py --only pubchem
```

## 注意
- 录之前确认网络真的通（脚本会先探一次，不通就直接退出，不写半截 cassette）
- cassette 会进仓库 ⇒ 只录**公开数据**，不含任何凭据（header 走白名单，见 cassette 模块）
- 数据源响应变了想更新：删掉对应 `.jsonl` 里那一行（或整个文件）再重跑本脚本
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), 'backend')
sys.path.insert(0, BACKEND)

# 必须在 import 业务模块之前设好，否则模块级代码可能已读到旧值
os.environ['SCIREAGENT_HTTP_MODE'] = 'record'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402

django.setup()

from core import http_cassette  # noqa: E402

#: 录制目标：每个数据源挑一条**稳定、公开、可断言**的代表性请求。
#: 刻意不录"随机/时间相关"的接口 —— 那种录下来也没法断言。
TARGETS = {
    'pubchem': '阿司匹林（CAS 50-78-2）：CAS → CID → CanonicalSMILES 全链路',
    'pubmed': '按 PMID 取文献摘要（E-utilities efetch）',
}


def _count(source: str) -> int:
    path = http_cassette.cassette_path(source)
    if not os.path.exists(path):
        return 0
    with open(path, encoding='utf-8') as f:
        return sum(1 for line in f if line.strip())


def record_pubchem():
    """CAS → CID → CanonicalSMILES。走 `PubChemClient`（统一客户端）。"""
    from apps.commerce.services.validators.product_validator import PubChemClient

    client = PubChemClient(timeout=20)
    result = client.compare_smiles('CC(=O)OC1=CC=CC=C1C(=O)O', '50-78-2')
    print(f'  PubChem 结果: {json.dumps(result, ensure_ascii=False)}')
    if not result.get('cid'):
        raise RuntimeError('PubChem 未返回 CID —— 网络或 API 异常，本次不写入')
    return result


def record_pubmed():
    """按 PMID 取摘要。走 `PubMedClient`（统一客户端）。"""
    from apps.knowledge.services.pubmed_client import PubMedClient

    client = PubMedClient(timeout=20)
    # 24151172 是 PLOS ONE 一篇公开可访问的论文；选它只因为稳定、有摘要
    text = client.fetch_abstract('24151172', max_chars=1200)
    print(f'  PubMed 摘要长度: {len(text or "")}')
    if not text:
        raise RuntimeError('PubMed 未返回摘要 —— 网络或 API 异常，本次不写入')
    return text


RECORDERS = {
    'pubchem': record_pubchem,
    'pubmed': record_pubmed,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=sorted(RECORDERS), default=None)
    args = ap.parse_args()

    print('=' * 70)
    print('外部数据源录制（SCIREAGENT_HTTP_MODE=record）')
    print('=' * 70)
    print(f'cassette 目录: {http_cassette.cassette_dir()}')

    # 先验网络：录不通用显式失败，不留半截 cassette
    import requests
    try:
        probe = requests.get('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/cids/JSON',
                             timeout=10)
        print(f'网络探测: PubChem http={probe.status_code}（{probe.elapsed.total_seconds():.1f}s）')
        if probe.status_code != 200:
            raise RuntimeError(f'PubChem 返回 {probe.status_code}')
    except Exception as exc:                                   # noqa: BLE001
        print(f'\n❌ 网络不通，已中止（不写任何 cassette）：{exc}')
        return 2

    names = [args.only] if args.only else sorted(RECORDERS)
    failures = []
    for name in names:
        before = _count(name)
        print(f'\n── {name} ── {TARGETS.get(name, "")}')
        try:
            RECORDERS[name]()
        except Exception as exc:                               # noqa: BLE001
            print(f'  ❌ 失败：{exc}')
            failures.append(name)
            continue
        after = _count(name)
        print(f'  cassette: {before} → {after} 条（{http_cassette.cassette_path(name)}）')

    print('\n' + '=' * 70)
    if failures:
        print(f'❌ 未录制成功：{", ".join(failures)}')
        return 1
    print('✅ 录制完成')
    for name in names:
        print(f'  {name}: {_count(name)} 条')
    return 0


if __name__ == '__main__':
    sys.exit(main())
