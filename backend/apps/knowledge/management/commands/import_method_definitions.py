# -*- coding: utf-8 -*-
"""
import_method_definitions — 把已签的方法定义 YAML 灌进 `method_definition`。

为什么需要它：0032 只建了表。在它之前，`MethodDefinition` 在代码里**只有模型和迁移，
没有任何读写入口** —— 表建好也等于没用。本命令是「文件 → 库」的唯一入口。

契约（与本仓既有命令一致）：
- **默认 dry-run**，只报告不落库；`--apply` 才写。
- **先全量校验，再统一写**：任一份不过规则 ⇒ 一份都不写（不许半灌）。
- **幂等**：按 (method, version) upsert，重复执行只更新、不新增。
- `version` 取 **YAML 原始 token**（`3.1`），**绝不用 float** —— float 会让 `3.10` 与 `3.1` 相等。
- `exclude` 由 `[{E1: 文本}]` **拍平为对象**（`{"E1": 文本}`）；YAML 仍是唯一源头。
- **不写 `Method.definition`**（已废弃列），写完会复核它仍为空。
- **不允许把定义直接置为 active**：除非显式 `--allow-active`，否则拒绝。
  规范要求 active 的跃迁须由组织方在满足证据条件后点头（见 0032 迁移头注释）。
- 方法定位：优先 `--map 名称=slug`；否则按 `Method.name` 唯一匹配，**匹配到多个即报错并列出候选**
  —— 宁可停下，也不猜着写错行。

示例：
    # 只报告（默认）
    manage.py import_method_definitions docs/methods/a.yaml docs/methods/b.yaml
    # 实际写入
    manage.py import_method_definitions ... --apply
    # 名字有歧义时显式指定
    manage.py import_method_definitions x.yaml --map SDS-PAGE=sds-page-781
"""
import hashlib
import os

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.definition_rules import check, flatten_exclude
from apps.knowledge.models import Method, MethodDefinition


def raw_version_token(path):
    """取 version 的**原始 token**（不经 safe_load 的 float 转换）。"""
    node = yaml.compose(open(path, encoding='utf-8'))
    for k, v in (node.value if node else []):
        if getattr(k, 'value', None) == 'version':
            return str(v.value), (getattr(v, 'style', None) is not None)
    raise CommandError('%s 里找不到 version' % path)


class Command(BaseCommand):
    help = '把方法定义 YAML 灌入 method_definition（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help='定义 YAML 路径')
        parser.add_argument('--apply', action='store_true', help='真正写入（默认只报告）')
        parser.add_argument('--map', action='append', default=[], metavar='NAME=SLUG',
                            help='方法名 → slug 映射，可重复')
        parser.add_argument('--status', default='reviewed',
                            help='写入的 status（默认 reviewed）')
        parser.add_argument('--verification', default='smoke_passed',
                            help='写入的 verification（默认 smoke_passed）')
        parser.add_argument('--allow-active', action='store_true',
                            help='允许 --status active（默认拒绝：active 须组织方单独点头）')

    def handle(self, *args, **opts):
        if opts['status'] == 'active' and not opts['allow_active']:
            raise CommandError(
                '拒绝把定义直接置为 active。'
                'active 的跃迁须先满足证据条件并由组织方点头；'
                '确需如此请显式加 --allow-active。')

        name2slug = {}
        for m in opts['map']:
            if '=' not in m:
                raise CommandError('--map 需形如 NAME=SLUG，收到 %r' % m)
            k, v = m.split('=', 1)
            name2slug[k.strip()] = v.strip()

        apply_ = opts['apply']
        prepared, problems = [], []

        for path in opts['paths']:
            if not os.path.exists(path):
                problems.append('%s：文件不存在' % path)
                continue
            data = yaml.safe_load(open(path, encoding='utf-8'))
            if not isinstance(data, dict):
                problems.append('%s：顶层不是字典' % path)
                continue
            token, quoted = raw_version_token(path)
            # 规则 11 需要**内容 md5**：未加引号的新版只能靠"文件是否已核"来判定，
            # 文件名键控会被改名绕过（已实测），故这里按字节现算。
            file_md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()
            ok, issues, ex_obj = check(data, token, quoted, file_md5)
            if not ok:
                problems.extend('%s：%s' % (os.path.basename(path), i) for i in issues)
                continue

            name = (data.get('method') or '').strip()
            slug = name2slug.get(name)
            if slug:
                m = Method.objects.filter(slug=slug).first()
                if m is None:
                    problems.append('%s：--map 指定的 slug=%s 不存在' % (path, slug))
                    continue
            else:
                cands = list(Method.objects.filter(name=name).values_list('id', 'slug', 'name'))
                if not cands:
                    problems.append('%s：库里找不到 name=%r 的方法（可用 --map 指定）' % (path, name))
                    continue
                if len(cands) > 1:
                    problems.append('%s：name=%r 匹配到 %d 个方法，拒绝猜测：%s'
                                    % (path, name, len(cands), cands[:6]))
                    continue
                m = Method.objects.get(pk=cands[0][0])

            prepared.append((path, data, token, quoted, ex_obj, m))

        if problems:
            self.stderr.write(self.style.ERROR('★ 校验未通过，一份都不写：'))
            for p in problems:
                self.stderr.write('  - %s' % p)
            raise CommandError('中止（未写入任何行）')

        self.stdout.write('校验通过 %d 份；模式=%s' % (len(prepared), 'APPLY' if apply_ else 'DRY-RUN'))
        self.stdout.write('')

        written = 0
        with transaction.atomic():
            for path, data, token, quoted, ex_obj, m in prepared:
                kw = dict(
                    essence=data['essence'],
                    must=data['must'],
                    on_topic_requires=data['on_topic_requires'],
                    common_but_not_required=data['common_but_not_required'],
                    exclude=ex_obj,
                    category_definition=data['category_definition'],
                    pos_examples=data['pos_examples'],
                    neg_examples=data['neg_examples'],
                    edge_examples=data['edge_examples'],
                    scope_note=data.get('scope_note') or '',
                    status=opts['status'],
                    verification=opts['verification'],
                    layer_status=None,          # 未知就写 NULL，不用 normal 冒充
                    author=data['author'],
                    reviewed_by=data['reviewed_by'],
                )
                existed = MethodDefinition.objects.filter(method=m, version=token).exists()
                self.stdout.write(
                    '%-52s → method_id=%-6s slug=%-14s version=%r%s  %s'
                    % (os.path.basename(path), m.id, m.slug, token,
                       '' if quoted else '（未加引号）', '更新' if existed else '新增'))
                if apply_:
                    MethodDefinition.objects.update_or_create(
                        method=m, version=token, defaults=kw)
                    written += 1
                # 每次循环都复核废弃列没被碰
                m.refresh_from_db(fields=['definition'])
                if (m.definition or '') != '':
                    raise CommandError('★ Method.definition 被写入了！立刻回滚。')

        if not apply_:
            self.stdout.write('')
            self.stdout.write('DRY-RUN 结束：未写库。加 --apply 才真正写入。')
        else:
            self.stdout.write('')
            self.stdout.write('已写入/更新 %d 行。' % written)
        self.stdout.write('当前 method_definition 行数：%d' % MethodDefinition.objects.count())
