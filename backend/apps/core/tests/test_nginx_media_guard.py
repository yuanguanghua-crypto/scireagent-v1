"""F3 回归 — nginx `/media/` 直出绕过 Django 对象级授权（P1 越权读）。

背景（已核实）：
- `deploy/nginx.conf` 曾把 `/media/` 整棵按路径直出（`alias /usr/share/nginx/media/`），
  绕过四类**已有 Django 授权门**的敏感文件：
    * `media/invoices/INV-YYYY-NNNN.pdf` —— 发票号可枚举，绕过 `InvoicePdfDownloadView._is_order_viewer`
    * `media/po_attachments/YYYYMM/<原名>` —— 绕过 `PoAttachmentDownloadView`
    * `media/documents/coa/` —— 绕过 `CoaViewSet.download` 的「未 PUBLISHED 一律 404」
    * `media/documents/sds/` —— 绕过 `SdsRevisionViewSet.download` 同上
- 但**不能整体禁 `/media/`**：`media/pdfs/` 与 `media/documents/` 下的产品文档
  （`ProductDocument.file`，`upload_to='documents/'`）在序列化器里以 URL 返回，
  整体封禁会把产品页文档一起砍掉。

本文件是**配置守卫**：该 nginx 配置此前没有任何闸门，改回去不会有人发现。
用纯文本解析 `deploy/nginx.conf`（绝对路径定位，不依赖 cwd；文件缺失 skip 而非 fail）。
"""
import re
from pathlib import Path

import pytest

# backend/apps/core/tests/test_nginx_media_guard.py → parents[4] = 仓库根
NGINX_CONF = Path(__file__).parents[4] / 'deploy' / 'nginx.conf'

SENSITIVE_PATHS = [
    '/media/invoices/',
    '/media/po_attachments/',
    '/media/documents/coa/',
    '/media/documents/sds/',
]


@pytest.fixture(scope='module')
def conf_text():
    if not NGINX_CONF.is_file():
        pytest.skip(f'deploy/nginx.conf 不存在（CI 可能无 deploy/ 目录）：{NGINX_CONF}')
    return NGINX_CONF.read_text(encoding='utf-8')


def _lines(conf_text):
    return conf_text.splitlines()


def _find_media_location_index(lines):
    """定位 `location /media/ {`（非 ^~ 的那个）所在行号。"""
    for i, line in enumerate(lines):
        if re.match(r'^\s*location\s+/media/\s*\{\s*$', line):
            return i
    return -1


def _block_at(lines, start):
    """从 start 行（含 `{`）起按花括号配对取出整块文本。"""
    depth = 0
    started = False
    out = []
    for line in lines[start:]:
        out.append(line)
        depth += line.count('{')
        if '{' in line:
            started = True
        depth -= line.count('}')
        if started and depth <= 0:
            break
    return '\n'.join(out)


# ── 1. 四段敏感目录必须 deny all，且都在 /media/ 之前 ──
@pytest.mark.parametrize('path', SENSITIVE_PATHS)
def test_sensitive_prefix_denied(conf_text, path):
    lines = _lines(conf_text)
    media_idx = _find_media_location_index(lines)
    assert media_idx >= 0, 'nginx.conf 里找不到 `location /media/ {` 块'

    deny_idx = -1
    for i, line in enumerate(lines):
        # 形如: location ^~ /media/invoices/   { deny all; }  或换行写法
        if re.match(rf'^\s*location\s+\^~\s+{re.escape(path)}\s*\{{', line):
            block = _block_at(lines, i)
            if re.search(r'\bdeny\s+all\s*;', block):
                deny_idx = i
                break
    assert deny_idx >= 0, (
        f'缺少 `location ^~ {path} {{ deny all; }}` —— '
        f'该目录必须禁止 nginx 直出，改走 Django 授权视图')
    assert deny_idx < media_idx, (
        f'`{path}` 的 deny 块必须位于 `location /media/` 之前'
        f'（当前 deny 行 {deny_idx + 1}，/media/ 行 {media_idx + 1}）；'
        f'nginx 前缀匹配取最长前缀，虽然 ^~ 不依赖顺序，但顺序错说明配置被挪乱')


# ── 2. /media/ 块补 nosniff ──
def test_media_location_sets_nosniff(conf_text):
    lines = _lines(conf_text)
    idx = _find_media_location_index(lines)
    assert idx >= 0
    block = _block_at(lines, idx)
    assert 'X-Content-Type-Options' in block, '/media/ 块缺少 X-Content-Type-Options'
    m = re.search(r'add_header\s+X-Content-Type-Options\s+"?([^";]+)"?\s+always\s*;', block)
    assert m, '/media/ 块的 X-Content-Type-Options 必须带 always'
    assert m.group(1).strip().lower() == 'nosniff'


# ── 3. /media/ 块必须复制 server 级 CSP（nginx：有 add_header 就不再继承）──
def test_media_location_repeats_csp(conf_text):
    lines = _lines(conf_text)
    idx = _find_media_location_index(lines)
    block = _block_at(lines, idx)
    assert 'Content-Security-Policy-Report-Only' in block, (
        '/media/ 块一旦有自己的 add_header，就不再继承 server 级 CSP 头；'
        '必须把 server 级那条 CSP 原样复制进来（同 location = /index.html 的做法）')
    assert "default-src 'self'" in block
    assert "frame-ancestors 'none'" in block


# ── 4. 不得矫枉过正：整体封禁 /media/ 会把产品文档一起砍掉 ──
def test_media_not_blanket_denied(conf_text):
    lines = _lines(conf_text)
    for i, line in enumerate(lines):
        m = re.match(r'^\s*location\s+\^~\s+/media/\s*\{', line)
        if m:
            block = _block_at(lines, i)
            assert not re.search(r'\bdeny\s+all\s*;', block), (
                '禁止出现 `location ^~ /media/ { deny all; }` 整体封禁 —— '
                'media/pdfs/ 与 media/documents/ 下的产品文档依赖 /media/ 直出')
    # 也不能出现只匹配 /media/ 根的前缀 deny
    assert not re.search(r'^\s*location\s+\^~\s+/media/\s*\{\s*deny\s+all', conf_text, re.M)
