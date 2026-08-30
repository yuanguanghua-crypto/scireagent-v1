"""TDD: origin_detail 超长修复 —— protocols_count 替代协议 id 列表。

背景：import_topchain_extractions 的 _build_origin_detail 曾把全部协议 id
逗号拼接写入 origin_detail（字段 max_length=500），RG 关联几百上千协议时
必然超长（实测 14 条 >500 字符，最长 1567）。修复方向：改为 protocols_count:N
计数，不再拼协议 id 列表。

本文件覆盖：
- _build_origin_detail 新格式（单/多协议、max_conf None/有值）
- fix_origin_detail 命令 dry-run（默认：不改数据、输出待改数）
- fix_origin_detail 命令 apply（旧格式转换、非目标不动、幂等）
"""
import io

import pytest
from django.core.management import call_command

from apps.knowledge.management.commands.import_topchain_extractions import Command as ImportCommand
from apps.knowledge.models import Application, ResearchGoal


# ---------------------------------------------------------------------- #
# _build_origin_detail 新格式
# ---------------------------------------------------------------------- #

class TestBuildOriginDetail:
    def _build(self, protocols, max_conf):
        cmd = ImportCommand()
        return cmd._build_origin_detail({'protocols': set(protocols), 'max_conf': max_conf})

    def test_single_protocol_with_max_conf(self):
        assert self._build([7], 0.9) == 'extractor_v0.1|protocols_count:1|max_conf:0.9'

    def test_multi_protocol_is_count_not_id_list(self):
        detail = self._build([3, 1, 2], 0.9)
        assert detail == 'extractor_v0.1|protocols_count:3|max_conf:0.9'
        # 不再拼接协议 id 逗号列表
        assert 'protocols:1,2,3' not in detail
        assert 'protocols:' not in detail

    def test_max_conf_none_omits_part(self):
        assert self._build([1, 2], None) == 'extractor_v0.1|protocols_count:2'


# ---------------------------------------------------------------------- #
# fix_origin_detail 命令
# ---------------------------------------------------------------------- #

def _make_goal(origin_detail, slug='rg-x'):
    return ResearchGoal.objects.create(
        name='RG Fix', slug=slug, origin='ai_extracted', origin_detail=origin_detail,
    )


def _make_app(origin_detail, slug='ap-x'):
    return Application.objects.create(
        name='AP Fix', slug=slug, origin='ai_extracted', origin_detail=origin_detail,
    )


def _run_fix(*args):
    out = io.StringIO()
    call_command('fix_origin_detail', *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestFixOriginDetailCommand:
    def test_dry_run_reports_and_does_not_modify(self):
        goal = _make_goal('extractor_v0.1|protocols:1,2,3|max_conf:0.9')
        app = _make_app('extractor_v0.1|protocols:5,6|max_conf:0.8', slug='ap-y')
        output = _run_fix()  # 默认 dry-run
        assert '[DRY-RUN]' in output
        assert 'RG 改写：1 条' in output
        assert 'AP 改写：1 条' in output
        goal.refresh_from_db()
        app.refresh_from_db()
        assert goal.origin_detail == 'extractor_v0.1|protocols:1,2,3|max_conf:0.9'
        assert app.origin_detail == 'extractor_v0.1|protocols:5,6|max_conf:0.8'

    def test_dry_run_skipped_count(self):
        _make_goal('extractor_v0.1|protocols_count:3|max_conf:0.9')
        _make_goal('reviewed_by:admin', slug='rg-y')
        _make_app('', slug='ap-z')
        output = _run_fix()
        assert 'RG 改写：0 条' in output
        assert '跳过：3 条' in output

    def test_apply_converts_old_format(self):
        goal = _make_goal('extractor_v0.1|protocols:1,2,3|max_conf:0.9')
        _run_fix('--apply')
        goal.refresh_from_db()
        assert goal.origin_detail == 'extractor_v0.1|protocols_count:3|max_conf:0.9'

    def test_apply_converts_app_without_max_conf(self):
        app = _make_app('extractor_v0.1|protocols:42')
        _run_fix('--apply')
        app.refresh_from_db()
        assert app.origin_detail == 'extractor_v0.1|protocols_count:1'

    def test_apply_leaves_new_format_and_other_prefixes(self):
        already_new = _make_goal('extractor_v0.1|protocols_count:3|max_conf:0.9')
        reviewed = _make_goal('reviewed_by:admin', slug='rg-y')
        empty = _make_goal('', slug='rg-z')
        plain = _make_app('imported')
        _run_fix('--apply')
        for obj in (already_new, reviewed, empty, plain):
            obj.refresh_from_db()
        assert already_new.origin_detail == 'extractor_v0.1|protocols_count:3|max_conf:0.9'
        assert reviewed.origin_detail == 'reviewed_by:admin'
        assert empty.origin_detail == ''
        assert plain.origin_detail == 'imported'

    def test_apply_idempotent_second_run_zero_changes(self):
        goal = _make_goal('extractor_v0.1|protocols:1,2,3|max_conf:0.9')
        _run_fix('--apply')
        output = _run_fix('--apply')
        assert 'RG 改写：0 条' in output
        assert 'AP 改写：0 条' in output
        goal.refresh_from_db()
        assert goal.origin_detail == 'extractor_v0.1|protocols_count:3|max_conf:0.9'
