#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成说明书第 12 章「页面索引（按页面反查）」。

数据来源（全部已有，不猜）：
  frontend/src/router/index.js        → 52 个页面的 path / name / guard
  docs/e2e/PAGE_ROLE_MATRIX.json      → 29 个组件 × 8 身份的 DEAD/READONLY/OK 实测判定
  docs/e2e/PAGE_API_MAP.json          → 每页进入即发的请求 + 写操作数

输出：docs/e2e/_page_index_generated.md（供人工复核后并入正文）
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')
ROLE_MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'PAGE_ROLE_MATRIX.json')
API_MAP = os.path.join(ROOT, 'docs', 'e2e', 'PAGE_API_MAP.json')
OUT = os.path.join(ROOT, 'docs', 'e2e', '_page_index_generated.md')

# 组件 → 中文页名（人工维护，确保可读）
NICE = {
    'HomePage': '首页', 'ProductIndex': '产品列表', 'ProductDetail': '产品详情',
    'SearchPage': '搜索', 'ApplicationIndex': '应用列表', 'ApplicationDetail': '应用详情',
    'MethodIndex': '方法列表', 'MethodDetail': '方法详情', 'ProtocolIndex': '方案列表',
    'ProtocolDetail': '方案详情', 'ResearchGoalIndex': '研究目标列表',
    'ResearchGoalDetail': '研究目标详情', 'ConvergenceClassDetail': '收敛类详情',
    'CartPage': '购物车', 'CheckoutPage': '结账下单', 'OrderListPage': '我的订单',
    'OrderDetailPage': '订单详情', 'SettingsPage': '设置', 'LoginPage': '登录',
    'RegisterPage': '注册', 'VerifyEmailPage': '邮箱验证', 'QuoteRequestPage': '提交询价',
    'WishlistPage': '收藏夹', 'AboutPage': '关于', 'PrivacyPolicyPage': '隐私政策',
    'TermsPage': '服务条款', 'NotFound': '404',
    'PoSubmit': '提交 PO', 'PoOrderList': 'PO 单列表', 'PoOrderDetail': 'PO 单详情',
    'PoAddressList': '地址簿', 'PoDownloadCenter': '下载中心', 'PoReorder': '再次订购',
    'AdminOrdersPage': '订单管理', 'AdminOrderDetail': '订单详情（内部）',
    'PoReviewDesk': 'PO 审核台', 'PoShipmentDesk': '发货台', 'PoInvoicingDesk': '开票台',
    'PoArReport': 'AR 账龄', 'PoOrgManagement': '机构管理', 'InventoryDesk': '库存台',
    'DashboardPage': '工作台首页', 'ProductsPage': '产品管理', 'ProductEditPage': '产品新建/编辑',
    'VerifiedPage': 'Verified 审核', 'GoalsPage': '研究目标', 'AppsPage': '应用',
    'MethodsPage': '方法', 'ProtocolsPage': '方案', 'ReferencesPage': '文献',
    'KnowledgeIntake': '知识录入',
}


def parse_router():
    """返回 [(path, name, guard)]，guard ∈ {public, auth, admin}"""
    src = io.open(ROUTER, encoding='utf-8').read()
    recs = []
    ws_start = src.index("path: '/workspace'")
    ws_end = src.index("path: '/:pathMatch(.*)*'")
    for m in re.finditer(r"path:\s*'([^']*)'", src):
        tail = src[m.end(): m.end() + 500]
        nm = re.search(r"name:\s*'([^']+)'", tail)
        mt = re.search(r"meta:\s*\{([^{}]*)\}", tail)
        if not nm:
            continue
        meta = mt.group(1) if mt else ''
        in_ws = ws_start <= m.start() < ws_end
        if 'requiresAdmin' in meta or in_ws:
            g = 'admin'
        elif 'requiresAuth' in meta:
            g = 'auth'
        else:
            g = 'public'
        recs.append((m.group(1), nm.group(1), g))
    return recs


def main():
    pages = parse_router()
    rm = json.load(io.open(ROLE_MATRIX, encoding='utf-8'))
    am = json.load(io.open(API_MAP, encoding='utf-8'))

    # 组件文件 basename → 角色判定
    verdict = {}
    for p in rm['pages']:
        comp = os.path.basename(p['file']).replace('.vue', '')
        v = {}
        for role, r in p['roles'].items():
            v[role] = r['verdict']
        writes = p['roles'].get('staff', {}).get('write', '0/0')
        mount = p['roles'].get('staff', {}).get('mount', '0/0')
        verdict[comp] = {'v': v, 'write': writes, 'mount': mount}

    lines = []
    lines.append('| 页面 | 路由 | 守卫 | 客户能进 | 采购/admin能进 | 进入即发 | 写操作 | 详见 |')
    lines.append('|---|---|---|---|---|---|---|---|')

    for path, name, guard in pages:
        comp = name
        nice = NICE.get(comp, comp)
        # 客户能否进（路由层）
        cust = '✅' if guard != 'admin' else '❌ 跳首页'
        # 采购能否进（路由层都行，但要有实测判定）
        if guard != 'admin':
            proc = '—'
        else:
            proc = '✅ 能进'
        v = verdict.get(comp)
        if v:
            pv = v['v'].get('procurement', '')
            if pv == 'DEAD':
                proc = '⚠️ 能进但不可用'
            elif pv == 'READONLY':
                proc = '⚠️ 能进但只读'
            elif pv == 'OK':
                proc = '✅ 可用'
            mount = v['mount']
            write = v['write']
        else:
            mount, write = '—', '—'
        lines.append('| %s | `%s` | %s | %s | %s | %s | %s | %s |' % (
            nice, ('/' + path if path and not path.startswith('/') else path) or '—',
            {'public': '无', 'auth': '需登录', 'admin': '需内部'}[guard],
            cust, proc, mount, write, ''))

    io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(lines))
    print('生成 %d 行 → %s' % (len(lines), OUT))
    # 打印前 12 行供核对
    print('\n'.join(lines[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
