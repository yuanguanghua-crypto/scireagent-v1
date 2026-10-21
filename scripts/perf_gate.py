#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L7 性能闸门 —— 关键端点耗时 p95 基线 + 绝对上限

## 为什么这样设计（三个刻意的取舍）

### ① 进程内测（Django test client），不起服务、不打网络
性能数字最怕噪声。起 `runserver` + HTTP 打请求，会把**端口、连接复用、DNS、
本机防火墙**都算进去，同一台机器两次能差 3 倍。进程内测的是"视图 + ORM +
序列化"的真实 CPU/IO 成本，重复测量稳定得多。
代价：不含网络栈开销，所以**绝对值不能当 SLA 用**，只能用于**同环境前后对比**。

### ② 绝不进 CI 做「相对基线」比较，只做「绝对上限」
单机测量天然有波动（GC、文件缓存、后台进程）。拿 p95 与基线做精确比较，
在共享 CI runner 上会**频繁假红** —— 那比没有闸门更糟，因为人会开始忽略它。
所以：
  · **CI / 随手跑**：只查绝对上限（防灾难性退化，如某端点从 30ms 变 30s）
  · **发版前 / 改完优化后**：`--update` 刷新基线，用 `--strict` 做相对对比

### ③ 必须先断言 status == 200，否则测的是错误页
这不是理论风险 —— 本脚本第一版就踩了：`ALLOWED_HOSTS` 不含 testserver ⇒ 全部
端点返回 **400**，而 400 的耗时只有 8ms，看起来"性能极好"。
**测量脚本不校验状态码，等于给自己造了一份假数据。**
现在任何非 200 直接判该端点数据无效并 FAIL。

## 判据
| 级别 | 条件 |
|---|---|
| FAIL | 状态码非 200（数据无效） |
| FAIL | p95 > 绝对上限（见 `ABSOLUTE_CEILING_MS`） |
| FAIL（仅 `--strict`） | p95 > 基线 × `--factor`（默认 2.0）|
| WARN | 端点不在基线里（需 `--update` 纳入） |

## 用法
```bash
cd backend
venv/Scripts/python.exe ../scripts/perf_gate.py               # 查绝对上限（默认）
venv/Scripts/python.exe ../scripts/perf_gate.py --strict      # 加查相对基线
venv/Scripts/python.exe ../scripts/perf_gate.py --update      # 刷新基线（看清 diff 再提交）
venv/Scripts/python.exe ../scripts/perf_gate.py --repeat 30   # 采样更多次
```

## ⚠️ 已知局限（必须知道，否则会误读数字）
1. **本机是 sqlite，生产是 PostgreSQL** ⇒ 绝对耗时不可直接外推到生产；
   基线的意义是"同一环境下不退步"。
2. 只覆盖**匿名端点**。登录态端点（订单列表/工作台）需要造用户，会污染 dev 库，
   暂不纳入。
3. 性能基线与机器强相关。**换机器 / 改 docker 资源限制后必须 `--update` 重做**
   （旧数字在新机器上没有意义）。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), 'backend')
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

BASELINE = os.path.join(PROJECT_DOCS := os.path.join(os.path.dirname(HERE), 'docs', 'e2e'),
                        'PERF_BASELINE.json')

#: 被测端点。只挑**匿名可访问**且**有代表性**的（公网主要流量都在这里）。
#: 刻意不测 robots.txt / organizations（<2ms，测了也没有信息量）。
#: `{product_id}` 会在运行时替换成真实存在的产品 id —— 写死 id=1 会 404
#: （产品在回收站 / id 不连续），而"永远 FAIL 一条假问题"会让闸门被忽略。
ENDPOINTS = [
    '/api/v1/products/',
    '/api/v1/search?q=a',
    '/api/v1/search/grouped?q=a',
    '/api/v1/search/suggest?q=ab',
    '/api/v1/categories',
    '/api/v1/site/home',
    '/api/v1/site/navigation',
    '/api/v1/sitemap.xml',
    '/api/v1/graph?type=product&id={product_id}',
]

#: 绝对上限（毫秒，p95）。**只防灾难**，不是 SLA。
#: 普通 JSON API 2s、重聚合端点 3s —— 这样正常波动不会误报，
#: 但"某端点从 30ms 变成 30s"一定被抓到。
ABSOLUTE_CEILING_MS = {
    'default': 2000,
    '/api/v1/site/home': 3000,
    '/api/v1/site/navigation': 3000,
    '/api/v1/sitemap.xml': 4000,
}


def _setup():
    import django
    logging.disable(logging.CRITICAL)   # 抑制 DisallowedHost 等整段 traceback 刷屏
    django.setup()


def measure(client, path: str, repeat: int) -> dict:
    """跑 repeat 次，返回 p50/p95/max/bytes/status。"""
    samples, status, size = [], None, 0
    for _ in range(repeat):
        t0 = time.perf_counter()
        resp = client.get(path)
        samples.append((time.perf_counter() - t0) * 1000.0)
        status = resp.status_code
        size = len(resp.content)
    samples.sort()
    return {
        'p50_ms': round(statistics.median(samples), 1),
        'p95_ms': round(samples[max(0, int(len(samples) * 0.95) - 1)], 1),
        'max_ms': round(max(samples), 1),
        'bytes': size,
        'status': status,
    }


def _load_baseline() -> dict:
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding='utf-8') as f:
            return json.load(f)
    return {'endpoints': {}, 'note': ''}


def _pick_product_id(client):
    """取一个真实存在的产品 id 用于 graph 端点。

    为什么不写死 1：产品可能被归档 / id 不连续（本仓库产品 id 从 66 起）。
    拿不到时返回 None，调用方会跳过该端点并说明 —— 而不是让它永远 404 假红。
    """
    try:
        resp = client.get('/api/v1/products/?page_size=1')
        if resp.status_code != 200:
            return None
        body = json.loads(resp.content)
        data = body.get('data')
        if isinstance(data, dict):
            data = data.get('results') or []
        if data:
            return data[0].get('id')
    except Exception:                                          # noqa: BLE001
        return None
    return None


def _save_baseline(data: dict) -> None:
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeat', type=int, default=15, help='每个端点采样次数（默认 15）')
    ap.add_argument('--update', action='store_true', help='刷新基线')
    ap.add_argument('--strict', action='store_true', help='额外检查「p95 > 基线 × factor」')
    ap.add_argument('--factor', type=float, default=2.0, help='相对退化阈值倍率（默认 2.0）')
    args = ap.parse_args()

    _setup()
    from django.test import Client

    # ★ SERVER_NAME='localhost'：默认是 'testserver'，而 ALLOWED_HOSTS 不含它 ⇒
    #   全部端点 400（错误页只要 8ms，看起来"很快"）。这条踩过。
    client = Client(SERVER_NAME='localhost')

    print('=' * 84)
    print('L7 性能闸门（进程内测量 / 非 SLA，只用于同环境前后对比）')
    print('=' * 84)
    print(f'采样 {args.repeat} 次/端点 ｜ 基线：{os.path.relpath(BASELINE, os.path.dirname(HERE))}')

    baseline = _load_baseline()
    base_ep = baseline.get('endpoints', {})

    product_id = _pick_product_id(client)
    if product_id is None:
        print('⚠️ 拿不到可用产品 id ⇒ 跳过 graph 端点（不让它变成永久假红）')

    rows, fails, warns, skipped = [], [], [], []
    print(f'\n{"端点":<40} {"p50":>9} {"p95":>9} {"上限":>8} {"大小":>10}')
    print('-' * 84)
    for tpl in ENDPOINTS:
        if '{product_id}' in tpl:
            if product_id is None:
                skipped.append(tpl)
                continue
            path = tpl.replace('{product_id}', str(product_id))
        else:
            path = tpl
        m = measure(client, path, args.repeat)
        ceiling = ABSOLUTE_CEILING_MS.get(tpl, ABSOLUTE_CEILING_MS['default'])
        m['path'] = path
        m['template'] = tpl
        rows.append(m)

        kb = m['bytes'] / 1024.0
        size_txt = f'{kb:.1f}KB' if kb < 1024 else f'{kb / 1024:.2f}MB'
        flags = []
        if m['status'] != 200:
            flags.append(f'状态{m["status"]}')
            fails.append((path, f'状态码 {m["status"]}，数据无效'))
        if m['p95_ms'] > ceiling:
            flags.append('超上限')
            fails.append((path, f'p95 {m["p95_ms"]}ms > 上限 {ceiling}ms'))
        if tpl not in base_ep:
            warns.append((tpl, '不在基线里（跑 --update 纳入）'))
        print(f'{path:<40} {m["p50_ms"]:8.1f} {m["p95_ms"]:8.1f} '
              f'{ceiling:7d} {size_txt:>10} {" ".join(flags)}')

    if args.strict:
        print('\n相对基线（--strict）')
        print('-' * 84)
        for m in rows:
            name = m['template']
            old = (base_ep.get(name) or {}).get('p95_ms')
            if not old:
                continue
            ratio = m['p95_ms'] / old if old else 0
            flag = ''
            if ratio > args.factor:
                flag = '  ⚠️ 退化'
                fails.append((name, f'p95 {m["p95_ms"]}ms = 基线 {old}ms 的 {ratio:.1f}x'))
            print(f'  {name:<40} 基线 {old:7.1f}ms → 现在 {m["p95_ms"]:7.1f}ms  {ratio:4.1f}x{flag}')

    if args.update:
        new_ep = {}
        for m in rows:
            if m['status'] != 200:
                print(f'\n⚠️ {m["path"]} 状态 {m["status"]}，**不写入基线**（无效数据）')
                continue
            new_ep[m['template']] = {'p50_ms': m['p50_ms'], 'p95_ms': m['p95_ms'],
                                     'bytes': m['bytes']}
        _save_baseline({
            'endpoints': new_ep,
            'note': '进程内测量（Django test client），非 SLA。与机器强相关：'
                    '换机器或改 docker 资源限制后必须 --update 重做。',
            'measured_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        })
        print(f'\n基线已刷新：{len(new_ep)} 个端点')

    print('\n' + '=' * 84)
    if skipped:
        print(f'跳过 {len(skipped)} 个端点：')
        for t in skipped:
            print(f'  {t} —— 缺少运行时可用的参数（见上方提示）')
    if warns and not args.update:
        print(f'WARN {len(warns)} 条（不阻塞）：')
        for path, why in warns:
            print(f'  {path} —— {why}')
    if fails:
        print(f'FAIL {len(fails)} 条：')
        for path, why in fails:
            print(f'  {path} —— {why}')
        return 1
    print('PASS —— 全部端点 200，且 p95 未超绝对上限')
    return 0


if __name__ == '__main__':
    sys.exit(main())
