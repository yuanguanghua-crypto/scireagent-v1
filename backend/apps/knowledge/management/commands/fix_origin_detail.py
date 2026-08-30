"""fix_origin_detail 数据修复命令 — 把旧版超长 origin_detail 改写为 protocols_count。

背景：旧版 import_topchain_extractions._build_origin_detail 把全部协议 id
逗号拼接写入 origin_detail（extractor_v0.1|protocols:<id列表>|max_conf:<conf>），
RG 关联几百上千协议时突破 CharField max_length=500（实测 14 条 >500 字符，
最长 1567）。

本命令把 `extractor_v0.1|protocols:<逗号id列表>|...` 改写为
`extractor_v0.1|protocols_count:<id个数>|...`：
- N = 旧格式里协议 id 列表按逗号切分的个数（不查 DB 验证 id —— 它们是
  提取时的快照 id，与当前 DB 无直接对应）
- 其余 part（如 max_conf:...）原样保留
- 仅匹配前缀 `extractor_v0.1|protocols:`（旧格式）；已是 protocols_count、
  非 extractor 前缀或空串的记录一律不动

幂等：apply 后再跑 dry-run 应为 0 条待改。

用法：
  python manage.py fix_origin_detail            # dry-run（默认），只统计不改数据
  python manage.py fix_origin_detail --dry-run  # 同上，显式声明
  python manage.py fix_origin_detail --apply    # 实际改写
"""
from django.core.management.base import BaseCommand

from apps.knowledge.models import Application, ResearchGoal

_OLD_PREFIX = 'extractor_v0.1|protocols:'
_SAMPLE_LIMIT = 3


def _rewrite_old_detail(origin_detail):
    """旧格式 origin_detail -> 新格式；非旧格式返回 None（调用方跳过）。"""
    if not origin_detail.startswith(_OLD_PREFIX):
        return None
    parts = origin_detail.split('|')
    # parts[0]='extractor_v0.1'，parts[1]='protocols:<逗号id列表>'，其余（如 max_conf）原样保留
    ids_part = parts[1]
    n = len(ids_part[len('protocols:'):].split(','))
    new_parts = [parts[0], f'protocols_count:{n}'] + parts[2:]
    return '|'.join(new_parts)


class Command(BaseCommand):
    help = '把旧格式 origin_detail（protocols:<id列表>）改写为 protocols_count:<个数>（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='实际改写（缺省为 dry-run，只统计不落库）')
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='显式 dry-run（默认行为，--apply 优先）')

    def handle(self, *args, **options):
        apply = options['apply']

        self.stdout.write('=' * 64)
        self.stdout.write('fix_origin_detail：origin_detail 超长修复（protocols:id列表 -> protocols_count）')
        self.stdout.write('警告：操作开发库，建议先备份！(cp db.sqlite3 db.sqlite3.bak_xxx)')
        self.stdout.write('模式：' + ('--apply（实际改写）' if apply else '[DRY-RUN]（默认，不修改数据）'))
        self.stdout.write('=' * 64)

        rg_pending, ap_pending, skipped = [], [], 0
        for obj in ResearchGoal.objects.all():
            new = _rewrite_old_detail(obj.origin_detail)
            if new is None:
                skipped += 1
            else:
                rg_pending.append((obj, new))
        for obj in Application.objects.all():
            new = _rewrite_old_detail(obj.origin_detail)
            if new is None:
                skipped += 1
            else:
                ap_pending.append((obj, new))

        if not apply:
            self.stdout.write(
                f'[DRY-RUN] RG 改写：{len(rg_pending)} 条 / AP 改写：{len(ap_pending)} 条 / 跳过：{skipped} 条')
            for obj, new in (rg_pending + ap_pending)[:_SAMPLE_LIMIT]:
                self.stdout.write(
                    f'  样例：{obj.__class__.__name__}[id={obj.pk}]  {obj.origin_detail} -> {new}')
            self.stdout.write('dry-run 结束：未修改任何数据。加 --apply 实际改写。')
            return

        for obj, new in rg_pending:
            obj.origin_detail = new
            obj.save(update_fields=['origin_detail'])
        for obj, new in ap_pending:
            obj.origin_detail = new
            obj.save(update_fields=['origin_detail'])
        self.stdout.write(
            f'RG 改写：{len(rg_pending)} 条 / AP 改写：{len(ap_pending)} 条 / 跳过：{skipped} 条')
        self.stdout.write(f'完成：共改写 {len(rg_pending) + len(ap_pending)} 条。')
