#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把说明书 32 个操作流程 × 现有 e2e spec 做成覆盖矩阵，并算出缺口。

## 为什么映射表写在代码里
流程编号（F1-1…F7-9）与 spec 名不是一对一，只能人工判。把判断写进 `FLOWS` 表里，
好处是：① 可 diff、可复核；② 统计自动算，不会像手写表格那样越改越乱。

## 深度分级（关键：避免"有 spec"被当成"测过了"）
  FULL  该流程的**主路径**被完整走通并断言了业务结果（不是只看页面能开）
  PART  只覆盖了部分字段/分支/角色，或只断言了 UI 出现
  LOAD  只有"页面加载不崩"级别的覆盖
  NONE  没有任何针对性用例

用法：python scripts/flow_coverage_matrix.py [--md]
"""
from __future__ import annotations

import os
import sys

# (流程编号, 流程名, 深度, 现有 spec, 缺口说明)
FLOWS = [
    # ---- 第 1 章 匿名 ----
    ('F1-1',  '浏览首页',              'FULL', 'homepage, home-pills-cta, p2-public-interactions', ''),
    ('F1-2',  '产品列表与筛选',        'FULL', 'p2-public-interactions（排序带 ordering / 搜索带 search）',
     'L3 子分类不生效仍未锁（低优先，见说明书 §11.2 #13）'),
    ('F1-3',  '查看产品详情',          'FULL', 'product-detail-fields, product-detail-structure-image, product-detail-verified-methods',
     ''),
    ('F1-4',  '搜索',                  'FULL', 'search-result-docs, p2-public-interactions（suggest / grouped / Tab 不发请求）', ''),
    ('F1-5',  '浏览知识实体',          'PART', 'public-smoke, responsive, p1-public-pages',
     'chips 不筛数据已锁死；实体详情的交互（Tab/展开）仍只有加载级'),
    ('F1-6',  '加入购物车',            'FULL', 'cart-button-regression, cart-page-interactions, basket-local-merge-prune, basket-merge-over-limit',
     ''),
    ('F1-7',  '提交询价单（RFQ）',     'FULL',
     'p0-rfq（匿名提交+响应体侧证 / 必填拦截 / 匿名 401 / 只对提交人可见锁定）', ''),
    ('F1-8',  '注册（三步向导）',      'FULL', 'register-wizard',
     ''),
    ('F1-9',  '邮箱验证',              'FULL', 'verify-improvements, p2-auth-verify（无 token / 坏格式 500 锁 / 合法 400）', ''),
    ('F1-10', '静态页与 404',          'FULL', 'p1-public-pages（三页内容断言 + 404 非白屏）', ''),
    # ---- 第 2 章 未验证 ----
    ('F2-1',  '未验证登录被拒 + 重发', 'FULL',
     'p0-auth-orgadmin（403 文案 / 重发零请求锁定 / API 侧 403 原因）', ''),
    ('F2-2',  '重走验证链接',          'FULL', 'p2-auth-verify（重发接口 200 + UI 零请求锁）', ''),
    # ---- 第 3 章 客户 ----
    ('F3-1',  '登录',                  'FULL', 'permission-matrix, 以及全部 spec 的 login helper',
     ''),
    ('F3-2',  '管理个人资料（5 Tab）',  'FULL', 'settings-save-banner, p2-customer-flows（昵称落库 + 改密码零请求锁）', ''),
    ('F3-3',  '购物车（登录态）',      'FULL', 'cart-page-interactions, cart-checkout-regression',
     ''),
    ('F3-4',  '结账下单',              'FULL', 'checkout-validation, checkout-progressive-sections, cart-checkout-regression',
     ''),
    ('F3-5',  '查看订单列表',          'FULL', 'orders-pagination, order-status-filters',
     ''),
    ('F3-6',  '订单详情 + 报价应答',   'FULL', 'order-error-paths, p2-customer-flows（Accept 成功推进状态 + 越权 403/404）', ''),
    ('F3-7',  '提交 PO',               'FULL', 'po-lifecycle.api, po-lifecycle.fullflow, po-prod-sweep',
     ''),
    ('F3-8',  '查看 PO 单列表',        'FULL', 'order-status-filters, po-lifecycle.ui',
     ''),
    ('F3-9',  'PO 单详情与下载',       'FULL', 'po-lifecycle.ui, p2-customer-flows（发票区+RUO+下载请求+跨机构 403/404）', ''),
    ('F3-10', '地址簿 CRUD',           'FULL', 'po-addresses-crud',
     ''),
    ('F3-11', '下载中心',              'FULL',
     'p1-customer-pages（契约字段 + 列出发票号 + 点下载发请求 + PO 附件 + 无数据空态）', ''),
    ('F3-12', '再次订购',              'FULL', 'p1-customer-pages（列表含已完成单 + Re-order 跳转带参）', ''),
    ('F3-13', '收藏夹',                'FULL', 'p1-customer-pages（未登录提示 / 收藏落库 / 移除）', ''),
    # ---- 第 4 章 ----
    ('F4-1',  '确认机构管理员徽章',    'FULL',
     'p0-auth-orgadmin（与 researcher 逐项对比 + 徽章有无 + 越权 403）', ''),
    # ---- 第 5 章 采购 ----
    ('F5-1',  '审批 PO',               'FULL', 'po-lifecycle.fullflow, po-lifecycle.ui, ops-po-desk-gaps',
     ''),
    ('F5-2',  '发货',                  'FULL', 'po-lifecycle.fullflow, ops-po-desk-gaps',
     ''),
    ('F5-3',  '开票与收款',            'FULL', 'po-invoicing-queue, po-lifecycle.fullflow, ops-po-desk-gaps',
     ''),
    ('F5-4',  '看应收账龄',            'FULL', 'ops-po-desk-gaps, p2-ops-desk（四桶+总额+计数与 API 一致）', ''),
    ('F5-5',  '机构管理',              'FULL', 'ops-po-desk-gaps, p2-ops-desk（organization_id 参数 + 行数与 API 一致）', ''),
    ('F5-6',  '库存管理',              'FULL', 'ops-inventory',
     '并发正确性另由 PG 用例覆盖（run_pg_tests.py）'),
    # ---- 第 6 章 ----
    ('F6-1',  '指派销售',              'FULL',
     'p0-assign-rep（数字 id 成功+详情侧证 / 非数字 500 锁定 / 采购 403）', ''),
    # ---- 第 7 章 staff ----
    ('7.3',   '产品新建（含导入/AI/SKU/合规/SEO）', 'FULL',
     'product-new-*, product-edit-*, product-compliance-lifecycle, product-seo-publish',
     ''),
    ('7.4',   '产品管理（上下架/回收站/批量）', 'FULL',
     'product-list-*, product-batch-ai, product-save-keeps-links',
     ''),
    ('7.5',   '知识实体 CRUD',         'FULL', 'workspace-entity-crud, cascader-workflow',
     ''),
    ('7.6',   'Verified 审核',         'FULL', 'workspace-verified-review, verify-dialog-a11y, verify-dialog-style',
     ''),
    ('7.7',   '知识录入',              'FULL', 'knowledge-intake, workspace-entry-intake',
     ''),
    ('7.8',   '订单与 PO 八个台',      'FULL', 'po-lifecycle.*, ops-*, order-*',
     ''),
    # ---- 第 8 章 ----
    ('F8-1',  '物理删除产品（无 UI）', 'FULL',
     'apps/commerce/tests/test_hard_delete.py（超管可删 / staff 403 / 采购 403 / 匿名 / 404）', ''),
    ('F8-3',  'Django admin 角色分配', 'NONE', '—',
     '无自动化（此前判定为 C 类）；但"改完要重登"这条**完全没有验证过**'),
]

DEPTH_MARK = {'FULL': '🟩', 'PART': '🟨', 'LOAD': '🟦', 'NONE': '🟥'}


def main():
    as_md = '--md' in sys.argv
    total = len(FLOWS)
    cnt = {}
    for _, _, d, _, _ in FLOWS:
        cnt[d] = cnt.get(d, 0) + 1

    if as_md:
        print('| 流程 | 名称 | 深度 | 现有用例 | 缺口 |')
        print('|---|---|---|---|---|')
        for code, name, d, specs, gap in FLOWS:
            print('| `%s` | %s | %s %s | %s | %s |' % (
                code, name, DEPTH_MARK[d], d, specs, gap or '—'))
        print()
        print('**合计 %d 条流程：' % total
              + '、'.join('%s %d' % (k, cnt.get(k, 0)) for k in ('FULL', 'PART', 'LOAD', 'NONE'))
              + '**')
        return 0

    print('=== 说明书 %d 个操作流程 × 现有 E2E 覆盖 ===' % total)
    for k in ('FULL', 'PART', 'LOAD', 'NONE'):
        print('  %s %-5s %d' % (DEPTH_MARK[k], k, cnt.get(k, 0)))
    print('\n--- 需要补用例的流程（PART/LOAD/NONE）---')
    for code, name, d, specs, gap in FLOWS:
        if d == 'FULL':
            continue
        print('  %s %-6s %-28s 现：%s' % (DEPTH_MARK[d], code, name, specs[:44]))
        if gap:
            print('        缺口：%s' % gap)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
