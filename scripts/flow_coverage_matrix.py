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
    ('F1-1',  '浏览首页',              'PART', 'homepage, home-pills-cta, public-smoke',
     '分类胶囊点击、知识区展开未断言'),
    ('F1-2',  '产品列表与筛选',        'PART', 'public-smoke',
     '三级分类/排序/搜索联动、L3 子分类不生效(已知缺陷)未锁'),
    ('F1-3',  '查看产品详情',          'FULL', 'product-detail-fields, product-detail-structure-image, product-detail-verified-methods',
     ''),
    ('F1-4',  '搜索',                  'PART', 'search-result-docs',
     '`/search/suggest` 建议接口、按类型 Tab 过滤未单独测'),
    ('F1-5',  '浏览知识实体',          'LOAD', 'public-smoke, responsive',
     '方法/方案列表的状态 chips **点击不筛数据**(已知缺陷)**无用例锁定**'),
    ('F1-6',  '加入购物车',            'FULL', 'cart-button-regression, cart-page-interactions, basket-local-merge-prune, basket-merge-over-limit',
     ''),
    ('F1-7',  '提交询价单（RFQ）',     'NONE', '（仅 responsive 的加载级）',
     '**整条链路无功能用例**：匿名提交、必填校验、失败提示缺失'),
    ('F1-8',  '注册（三步向导）',      'FULL', 'register-wizard',
     ''),
    ('F1-9',  '邮箱验证',              'PART', 'verify-improvements, verify-field-normalize',
     '链接过期/无 token 分支、失败态无重发入口未测'),
    ('F1-10', '静态页与 404',          'LOAD', 'manual-pages-smoke',
     '只验渲染，无内容断言（三份法务文案）'),
    # ---- 第 2 章 未验证 ----
    ('F2-1',  '未验证登录被拒 + 重发', 'NONE', '（manual-facts F-06 只记录现象，无断言）',
     '**登录 403 分支 + 重发按钮死链无回归用例**（已知缺陷）'),
    ('F2-2',  '重走验证链接',          'PART', 'verify-improvements',
     '过期 token 路径未覆盖'),
    # ---- 第 3 章 客户 ----
    ('F3-1',  '登录',                  'FULL', 'permission-matrix, 以及全部 spec 的 login helper',
     ''),
    ('F3-2',  '管理个人资料（5 Tab）',  'PART', 'settings-save-banner',
     'Shipping/Contact 两个 Tab 的保存、**改密码假成功**未锁定'),
    ('F3-3',  '购物车（登录态）',      'FULL', 'cart-page-interactions, cart-checkout-regression',
     ''),
    ('F3-4',  '结账下单',              'FULL', 'checkout-validation, checkout-progressive-sections, cart-checkout-regression',
     ''),
    ('F3-5',  '查看订单列表',          'FULL', 'orders-pagination, order-status-filters',
     ''),
    ('F3-6',  '订单详情 + 报价应答',   'PART', 'order-error-paths, state-branches-commerce',
     '`quoted` 状态下 Accept/Reject 报价的**成功路径**未单独测'),
    ('F3-7',  '提交 PO',               'FULL', 'po-lifecycle.api, po-lifecycle.fullflow, po-prod-sweep',
     ''),
    ('F3-8',  '查看 PO 单列表',        'FULL', 'order-status-filters, po-lifecycle.ui',
     ''),
    ('F3-9',  'PO 单详情与下载',       'PART', 'po-lifecycle.ui, state-branches-po',
     '发票 PDF / PO 附件下载的**权限与内容**未断言'),
    ('F3-10', '地址簿 CRUD',           'FULL', 'po-addresses-crud',
     ''),
    ('F3-11', '下载中心',              'LOAD', 'manual-pages-smoke',
     '**零功能用例**：只渲染过，没有"能下载到文件"的断言'),
    ('F3-12', '再次订购',              'LOAD', 'manual-pages-smoke',
     '**零功能用例**：Re-order 跳转与预填未测'),
    ('F3-13', '收藏夹',                'LOAD', 'manual-pages-smoke',
     '**零功能用例**：收藏/取消/清空、未登录提示均未测'),
    # ---- 第 4 章 ----
    ('F4-1',  '确认机构管理员徽章',    'NONE', '—',
     '**"is_org_admin 零影响"没有任何用例锁定**；将来有人给它加权限也不会报警'),
    # ---- 第 5 章 采购 ----
    ('F5-1',  '审批 PO',               'FULL', 'po-lifecycle.fullflow, po-lifecycle.ui, ops-po-desk-gaps',
     ''),
    ('F5-2',  '发货',                  'FULL', 'po-lifecycle.fullflow, ops-po-desk-gaps',
     ''),
    ('F5-3',  '开票与收款',            'FULL', 'po-invoicing-queue, po-lifecycle.fullflow, ops-po-desk-gaps',
     ''),
    ('F5-4',  '看应收账龄',            'PART', 'ops-po-desk-gaps',
     '分桶金额计算未断言（只验了页面出现）'),
    ('F5-5',  '机构管理',              'PART', 'ops-po-desk-gaps',
     '按机构查单的**过滤正确性**未断言'),
    ('F5-6',  '库存管理',              'FULL', 'ops-inventory',
     '并发正确性另由 PG 用例覆盖（run_pg_tests.py）'),
    # ---- 第 6 章 ----
    ('F6-1',  '指派销售',              'NONE', '（manual-facts 只测了 403 与 500 现象）',
     '**成功路径无用例**；且"填用户名 → 500"这个缺陷无回归'),
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
    ('F8-1',  '物理删除产品（无 UI）', 'NONE', '—',
     '**无端点级用例**；超管专属能力，误删不可逆'),
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
