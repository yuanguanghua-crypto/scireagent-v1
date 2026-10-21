# -*- coding: utf-8 -*-
"""外部数据源 HTTP 录制 / 回放（cassette）—— 让依赖外网的流程可离线、可复现测试

## 为什么需要它
平台的 AUTO MATCH / enrich / 文献验证 / COA 补全都依赖**外部 API**
（PubChem、PubMed、ChEMBL、Europe PMC、Bioz）。这些调用此前在测试里只有两种处理：
  ① 完全不测（外网不通就跳过）—— 于是容错逻辑、解析逻辑、降级链从来没被验证过；
  ② 手写 mock 响应  —— 手写的 JSON 与真实响应**必然有差异**，测通不代表真能跑通。

而且外网本身不可靠：实测同一台机器，PubChem 有时 1.8s 返回，有时 20s 超时，
走代理还可能 SSL 失败。**同一个测试今天绿、明天红**，没人能判断是代码坏了还是网坏了。

cassette（录音带）解决的就是这个：把**真实响应**录下来，之后回放。
- 录制一次，之后离线可跑
- 回放的是真实字节，不是手写的假数据
- 回放模式**绝不回源**：没录到就显式报错，而不是"悄悄去联网"

## 三种模式（环境变量 `SCIREAGENT_HTTP_MODE`）
| 值 | 行为 |
|---|---|
| `off`（默认） | 完全不介入，行为与引入本模块之前**完全一致** |
| `record` | 真发请求，成功后把响应追加进 cassette；请求行为不变 |
| `replay` | **不发请求**，只从 cassette 取；未命中抛 `CassetteMiss` |

## 为什么默认是 off
这是硬要求：生产、开发、E2E 全都依赖真实外部数据。任何"默认开"的设计
都会在某天悄悄返回旧数据（录了 3 个月的 PubChem 分子式），而且没人看得出来。
只显式声明才会启用。

## key 的设计（最容易出错的地方）
key 必须**只由请求语义决定**，不能含任何随时间/随机变化的东西，否则永远 miss：
- 纳入：method、scheme+host、path、**排序后**的 query、body
- 剔除：headers（含 UA / 时间戳）、cookies、令牌
- query **排序**：`?a=1&b=2` 与 `?b=2&a=1` 是同一个请求，实测外部 API 的
  调用方拼参顺序不统一（`params` dict 顺序、手拼字符串都有）
- `params` dict 与 URL 里已有的 query **合并后**再排序（requests 会这么做）

## cassette 格式
按数据源分文件 `cassettes/<source>.jsonl`，一行一条：
```json
{"key": "<sha256[:32]>", "method": "GET", "url": "...", "status": 200,
 "headers": {"content-type": "application/json"}, "body_b64": "...",
 "recorded_at": "2026-10-21T09:40:00Z"}
```
- `headers` 走**白名单**：只留 content-type / retry-after。绝不落 Authorization / cookie
- body 超过 `MAX_BODY_BYTES` 的**整条跳过录制**并发 warning ——
  不存半截数据（那会让回放"成功"但内容残缺，比 miss 更危险）

## 用法
```bash
SCIREAGENT_HTTP_MODE=record python scripts/record_datasources.py   # 录
SCIREAGENT_HTTP_MODE=replay python -m pytest ...                   # 回放（离线）
```
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

logger = logging.getLogger(__name__)

MODE_ENV = 'SCIREAGENT_HTTP_MODE'
DIR_ENV = 'SCIREAGENT_CASSETTE_DIR'

MODE_OFF = 'off'
MODE_RECORD = 'record'
MODE_REPLAY = 'replay'
_VALID_MODES = (MODE_OFF, MODE_RECORD, MODE_REPLAY)

#: 单条响应体上限。超过则**整条跳过录制**（不存半截数据）。
MAX_BODY_BYTES = 2 * 1024 * 1024

#: 只保留这些响应头。其余（Authorization / Set-Cookie / Date / X-Request-Id …）
#: 一律不落盘 —— 既有安全考虑（cassette 可能进仓库），也因为它们会让回放不稳定。
HEADER_ALLOWLIST = ('content-type', 'retry-after')

_write_lock = threading.Lock()


class CassetteMiss(LookupError):
    """回放模式下 cassette 里没有这条请求的记录。

    ★ 故意做成**异常**而不是"回源"：静默回源会让 CI 重新依赖外网，
    而且测试表面是绿的、实际走的是网络 —— 那正是本模块要消灭的假绿。
    """

    def __init__(self, source: str, key: str, url: str):
        self.source = source
        self.key = key
        self.url = url
        super().__init__(
            f'cassette 未命中：source={source} key={key}\n'
            f'  请求：{url}\n'
            f'  处置：用 SCIREAGENT_HTTP_MODE=record 重跑以录制该请求，'
            f'或确认这条路径本来就该离线跳过。'
        )


def http_mode() -> str:
    """当前模式。非法值直接报错 —— 静默回落 off 会让人以为在录制却什么都没录。"""
    raw = (os.getenv(MODE_ENV) or MODE_OFF).strip().lower()
    if raw not in _VALID_MODES:
        raise ValueError(
            f'{MODE_ENV}={raw!r} 非法，可选：{", ".join(_VALID_MODES)}'
        )
    return raw


def cassette_dir() -> str:
    """cassette 根目录。默认 `backend/cassettes`（相对本文件两级向上）。"""
    configured = os.getenv(DIR_ENV)
    if configured:
        return configured
    here = os.path.dirname(os.path.abspath(__file__))          # .../backend/core
    return os.path.join(os.path.dirname(here), 'cassettes')     # .../backend/cassettes


def cassette_path(source: str) -> str:
    """按数据源分文件。source 会进文件名，做一次白名单化防路径穿越。"""
    safe = ''.join(ch if (ch.isalnum() or ch in '-_') else '_' for ch in (source or 'unknown'))
    return os.path.join(cassette_dir(), f'{safe}.jsonl')


# ── key 计算 ──────────────────────────────────────────────────────────
def _normalized_query(url: str, params) -> str:
    """URL 自带 query + requests 的 params 参数，合并后排序。

    requests 实际会把 params 追加到 URL 的 query 上；不合并就会算出与真实请求
    不一致的 key（录制与回放两次算法的输入不同 ⇒ 永远 miss）。
    """
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if params:
        if isinstance(params, dict):
            items = params.items()
        else:                                  # list[tuple] / 已编码字符串
            items = params if isinstance(params, (list, tuple)) else []
        pairs = pairs + [(str(k), str(v)) for k, v in items]
    return urlencode(sorted(pairs))


def _normalized_body(kwargs) -> str:
    """body 的稳定表示。只取 requests 真正会发出去的内容。"""
    if kwargs.get('json') is not None:
        return json.dumps(kwargs['json'], sort_keys=True, ensure_ascii=False)
    data = kwargs.get('data')
    if data is None:
        return ''
    if isinstance(data, dict):
        return urlencode(sorted((str(k), str(v)) for k, v in data.items()))
    if isinstance(data, bytes):
        return base64.b64encode(data).decode('ascii')
    return str(data)


def cassette_key(method: str, url: str, **kwargs) -> str:
    """请求语义的稳定指纹（32 位十六进制）。

    刻意**不含** headers / cookies / 超时 / 重试次数 —— 它们不影响"拿到什么数据"，
    只会让 key 变得不稳定从而永远 miss。
    """
    parts = urlsplit(url)
    material = '\n'.join([
        (method or 'GET').upper(),
        f'{parts.scheme}://{parts.netloc}',
        parts.path,
        _normalized_query(url, kwargs.get('params')),
        _normalized_body(kwargs),
    ])
    return hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]


# ── 录制 ──────────────────────────────────────────────────────────────
def _recordable_headers(resp) -> dict:
    out = {}
    for name in HEADER_ALLOWLIST:
        value = resp.headers.get(name)
        if value is not None:
            out[name] = value
    return out


def build_record(method: str, url: str, key: str, resp) -> dict | None:
    """把响应转成可落盘的一条记录。返回 None 表示"不该录"（body 过大）。

    ★ `url` 存 **`resp.url`（真实发出的完整 URL，含 params）**，不是调用方传入的
      那个。实测 PubMed 的调用是 `request_with_resilience('GET', EPMC/efetch,
      params={...})` —— 传入的 url 只有 `efetch.fcgi`，params 在另一个参数里。
      若存传入值，回放出来的 `resp.url` 就缺了检索条件，任何"从 url 反推参数"
      的下游代码都会拿到错的 URL。`resp.url` 是 requests 拼好的最终地址，没有这个问题。
      （key 仍由「传入 url + params」算出，与此处存什么无关 —— 两者职责不同。）
    """
    body = resp.content or b''
    if len(body) > MAX_BODY_BYTES:
        logger.warning(
            'cassette 跳过录制：响应体 %d 字节超过上限 %d（url=%s）',
            len(body), MAX_BODY_BYTES, url,
        )
        return None
    final_url = getattr(resp, 'url', None) or url
    return {
        'key': key,
        'method': (method or 'GET').upper(),
        'url': final_url,
        'status': resp.status_code,
        'headers': _recordable_headers(resp),
        'body_b64': base64.b64encode(body).decode('ascii'),
        'encoding': resp.encoding or 'utf-8',
    }


def save(source: str, record: dict) -> None:
    """追加一条到 cassette。同一 key 已存在则跳过（保留首次录制，避免重复膨胀）。"""
    path = cassette_path(source)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _write_lock:
        if _existing_keys(path).__contains__(record['key']):
            return
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        # newline='\n'：Windows 下避免写出 CRLF（会让 diff 与跨平台读取都变脏）
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write(line + '\n')


def _existing_keys(path: str) -> set:
    if not os.path.exists(path):
        return set()
    keys = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                keys.add(json.loads(line)['key'])
            except (ValueError, KeyError):
                continue
    return keys


# ── 回放 ──────────────────────────────────────────────────────────────
def lookup(source: str, key: str) -> dict | None:
    path = cassette_path(source)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get('key') == key:
                return record
    return None


def build_response(record: dict) -> requests.Response:
    """把一条记录还原成 `requests.Response`。

    调用方会读 `status_code` / `headers` / `text` / `json()` / `raise_for_status()`，
    所以 `_content`、`url`、`encoding` 都要设好；`request` 也补上，
    否则 `raise_for_status()` 拼错误信息时会碰 `resp.request` 为 None。
    """
    resp = requests.models.Response()
    resp.status_code = record['status']
    resp.url = record['url']
    resp.encoding = record.get('encoding') or 'utf-8'
    resp._content = base64.b64decode(record.get('body_b64') or '')
    for name, value in (record.get('headers') or {}).items():
        resp.headers[name] = value
    resp.request = requests.Request(
        record.get('method', 'GET'), record['url']
    ).prepare()
    return resp
