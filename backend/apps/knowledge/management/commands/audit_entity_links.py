"""audit_entity_links — 知识实体链路审计（部署后一键复查）。

## 为什么有这个命令

2026-10-30 做了一次人工全链路走查（21 个页面逐个点 + 生产全量统计），
发现了 5 类问题（88 条 `{}` 脏值、RG 表格无分页、Materials 空、描述型应用空壳、恒空 tab）。
但走查过程也暴露了两类**方法论错误**，值得写进这个命令的设计里：

1. **拿错环境** —— 用生产库的 id 去访问本地 dev，页面全是 "not found"，
   差点误报「15 个产品页全坏」。
   ⇒ 本命令**只用 ORM / 自身 API**，环境由 `manage.py` 决定，不存在跨环境比对。
2. **选错 DOM 选择器** —— 产品页用的是自定义 tab 而非 `el-tabs`，
   按 `.el-tabs__item` 查得到 0 个，差点误报「产品页没有知识实体」。
   ⇒ 渲染层的问题不归本命令管，交给 `scripts/audit_frontend_links.cjs`（Playwright）。
   本命令只断「数据与接口是否自洽」，这两件事必须分开判。

## 查什么

| 层 | 判据 |
|---|---|
| 详情可达 | 抽样逐个 GET 详情端点，必须 200（非 200 即 FAIL） |
| 内容非空 | 每类实体的必需字段不能为空（空即 WARN，可 `--strict` 升为 FAIL） |
| **交叉链接可达** | 详情里返回的关联 id（如 method.protocols[].id）必须在目标表真实存在（不存在即 FAIL —— 这才是真死链） |
| 空值率 | ORM 聚合，给出各关键字段的空值比例（只报告，不判失败） |

## 用法

    # 本地（默认，抽样 300/类）
    python manage.py audit_entity_links

    # 生产（容器内）
    docker compose exec -T backend python manage.py audit_entity_links

    # 全量（慢，逐条打详情）
    python manage.py audit_entity_links --sample 0

    # CI 用：字段空也判失败
    python manage.py audit_entity_links --strict --json

退出码：有 FAIL 或（strict 模式下）有 WARN 则 1，否则 0。
"""
import json
import random
import time

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.knowledge.models import Application, Method, Protocol, ResearchGoal

# (模型, 列表路径, 详情路径, 必需字段)
SPECS = [
    (Method, 'methods', 'methods', ('name', 'summary')),
    (Protocol, 'protocols', 'protocols', ('name', 'steps')),
    (Application, 'applications', 'applications', ('name', 'summary')),
    (ResearchGoal, 'research-goals', 'research-goals', ('name', 'summary')),
]

# 交叉链接规则：(实体名, 详情响应里的关联字段, 目标模型名, 目标模型)
CROSS_LINKS = [
    ('Method', 'protocols', 'Protocol', Protocol),
    ('Method', 'products', 'Product', Product),
    ('Application', 'methods', 'Method', Method),
    ('Application', 'protocols', 'Protocol', Protocol),
    ('Application', 'products', 'Product', Product),
    ('ResearchGoal', 'application_collection', 'Application', Application),
    ('ResearchGoal', 'protocols', 'Protocol', Protocol),
    ('Protocol', 'methods', 'Method', Method),
    ('Protocol', 'products', 'Product', Product),
]


def public_qs(model):
    qs = model.objects.all()
    if hasattr(model, 'is_test_fixture'):
        qs = qs.filter(is_test_fixture=False)
    if model is Protocol:
        return qs.filter(status='published')
    if hasattr(model, 'status'):
        return qs.filter(status='active')
    return qs


class Command(BaseCommand):
    help = '知识实体链路审计：详情可达 + 内容非空 + 交叉链接可达'

    def add_arguments(self, parser):
        parser.add_argument('--sample', type=int, default=300,
                            help='每类抽样条数，0 = 全量（默认 300）')
        parser.add_argument('--strict', action='store_true',
                            help='字段为空也判失败（默认只是 WARN）')
        parser.add_argument('--json', action='store_true', help='机器可读输出')

    def handle(self, *args, **opts):
        client = APIClient()
        # ★ 生产配了 `AnonRateThrottle 100/hour`（settings/base.py:238-243），
        #   审计要打 数百~上千 次详情，匿名必然撞 429（首跑实测 4 类抽样 200 个全部 429）。
        #   用 staff 账号 force_authenticate 绕过：AnonRateThrottle 只对未认证请求生效。
        #
        # ⚠️ 这里必须是 `rest_framework.test.APIClient` —— Django 原生 `Client` **没有**
        #    `force_authenticate`，用它会在 AttributeError 后被 except 静默吞掉，
        #    表现为「认证仿佛生效了但仍在撞 429」。（这是第一版踩的坑，勿改成 django.test.Client）
        #
        # 副作用：staff 视角绕过 status 过滤，但抽样 id 取自 public_qs（已按公开态筛过）。
        from apps.accounts.models import User
        u = User.objects.filter(is_staff=True, is_active=True).first()
        if u is not None:
            client.force_authenticate(user=u)
            self.stdout.write(f'（已用 staff 账号 {u.username} 认证，绕过匿名限流）')
        else:
            # 不静默 —— 没有 staff 账号就明确告警，否则会全 429 且看不出原因
            self.stdout.write(self.style.WARNING(
                '⚠️ 库内无 is_staff 且 is_active 的用户，将以匿名身份请求，'
                '可能撞 AnonRateThrottle(100/hour) 而大面积 429'))
        sample_n = opts['sample']
        strict = opts['strict']
        report = {'fails': [], 'warns': [], 'sections': {}}

        for model, _list_path, detail_path, required in SPECS:
            qs = public_qs(model)
            ids = list(qs.values_list('id', flat=True))
            total = len(ids)
            if sample_n and total > sample_n:
                random.seed(hash(model.__name__) & 0xFFFF)
                ids = random.sample(ids, sample_n)

            sec = {'total': total, 'probed': len(ids), 'ok': 0,
                   'missing': [], 'bad_status': [], 'cross_broken': []}
            for pid in ids:
                resp = client.get(f'/api/v1/{detail_path}/{pid}/', HTTP_HOST='localhost')
                # 万一限流仍生效（无 staff 账号 / 配了 UserRateThrottle），退避重试一次
                if resp.status_code == 429:
                    time.sleep(1.2)
                    resp = client.get(f'/api/v1/{detail_path}/{pid}/', HTTP_HOST='localhost')
                if resp.status_code != 200:
                    sec['bad_status'].append((pid, resp.status_code))
                    continue
                data = (resp.json() or {}).get('data') or {}
                sec['ok'] += 1

                for f in required:
                    v = data.get(f)
                    empty = (v is None) or (v == '') or (v == []) or (v == {})
                    if empty:
                        sec['missing'].append((pid, f))

                # 交叉链接：关联 id 必须在目标表存在
                for ent, field, target_name, target_model in CROSS_LINKS:
                    if ent != model.__name__:
                        continue
                    rel = data.get(field) or []
                    tids = [x.get('id') for x in rel if isinstance(x, dict) and x.get('id')]
                    if not tids:
                        continue
                    found = set(target_model.objects.filter(id__in=tids)
                                .values_list('id', flat=True))
                    for tid in tids:
                        if tid not in found:
                            sec['cross_broken'].append((pid, field, target_name, tid))

            if sec['bad_status']:
                report['fails'].append(
                    f'{model.__name__}: {len(sec["bad_status"])} 个详情非 200  {sec["bad_status"][:5]}')
            if sec['cross_broken']:
                report['fails'].append(
                    f'{model.__name__}: {len(sec["cross_broken"])} 条交叉链接指向不存在的实体  {sec["cross_broken"][:5]}')
            if sec['missing']:
                msg = f'{model.__name__}: {len(sec["missing"])} 处必需字段为空  {sec["missing"][:5]}'
                (report['fails'] if strict else report['warns']).append(msg)

            report['sections'][model.__name__] = sec

        # 空值率（只报告）
        rates = {}
        for model, _lp, _dp, required in SPECS:
            qs = public_qs(model)
            t = qs.count()
            if not t:
                continue
            rates[model.__name__] = {
                f: qs.filter(Q(**{f: ''}) | Q(**{f + '__isnull': True})).count()
                if f != 'steps' else qs.annotate(_n=Count('steps', distinct=True)).filter(_n=0).count()
                for f in required
            }
        report['empty_rates'] = rates

        if opts['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=1))
        else:
            self._pretty(report)

        bad = bool(report['fails']) or (strict and bool(report['warns']))
        if bad:
            raise SystemExit(1)

    def _pretty(self, report):
        self.stdout.write('=' * 72)
        self.stdout.write('知识实体链路审计')
        self.stdout.write('=' * 72)
        for name, sec in report['sections'].items():
            self.stdout.write(
                f'\n{name}: 库内 {sec["total"]}，抽查 {sec["probed"]}'
                f'｜200 {sec["ok"]}'
                f'｜非200 {len(sec["bad_status"])}'
                f'｜字段空 {len(sec["missing"])}'
                f'｜交叉断链 {len(sec["cross_broken"])}')
            for tag, key in (('非200', 'bad_status'), ('字段空', 'missing'), ('交叉断链', 'cross_broken')):
                if sec[key]:
                    self.stdout.write(f'    {tag} 例: {sec[key][:5]}')

        self.stdout.write('\n' + '=' * 72)
        self.stdout.write('空值率（仅报告，不判失败）')
        self.stdout.write('=' * 72)
        for name, d in report.get('empty_rates', {}).items():
            parts = [f'{k}={v}' for k, v in d.items()]
            self.stdout.write(f'  {name}: ' + '  '.join(parts))

        self.stdout.write('\n' + '=' * 72)
        if report['fails']:
            self.stdout.write(self.style.ERROR(f'FAIL {len(report["fails"])} 项'))
            for m in report['fails']:
                self.stdout.write(self.style.ERROR('  ✗ ' + m))
        if report['warns']:
            self.stdout.write(self.style.WARNING(f'WARN {len(report["warns"])} 项'))
            for m in report['warns']:
                self.stdout.write(self.style.WARNING('  ! ' + m))
        if not report['fails'] and not report['warns']:
            self.stdout.write(self.style.SUCCESS('全部通过：详情可达、必需字段非空、交叉链接无断链'))
        self.stdout.write('=' * 72)
