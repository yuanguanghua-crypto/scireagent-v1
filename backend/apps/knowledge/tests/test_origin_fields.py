"""T3: RG/AP/Method origin + origin_detail 字段（顶部链 AI 生成管线前置）。

铁律：AI 生成数据必须诚实标注来源（三层护栏① origin 溯源）。
- origin: human_curated / ai_extracted / imported（存量默认 imported，不猜来源）
- origin_detail: 溯源详情（extractor_v0.1|protocols:12,34,56）
- is_test_fixture 与 origin 正交保留：前者=测试种子标记，后者=来源
"""
import pytest
from django.test import TestCase

from apps.knowledge.models import ResearchGoal, Application, Method
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
)


class OriginFieldPresenceTest(TestCase):
    """三模型都必须有 origin + origin_detail 字段。"""

    def test_research_goal_has_origin_fields(self):
        for f in ('origin', 'origin_detail'):
            self.assertIn(f, [x.name for x in ResearchGoal._meta.get_fields()],
                          f'ResearchGoal 缺 {f} 字段')

    def test_application_has_origin_fields(self):
        for f in ('origin', 'origin_detail'):
            self.assertIn(f, [x.name for x in Application._meta.get_fields()],
                          f'Application 缺 {f} 字段')

    def test_method_has_origin_fields(self):
        for f in ('origin', 'origin_detail'):
            self.assertIn(f, [x.name for x in Method._meta.get_fields()],
                          f'Method 缺 {f} 字段')


class OriginDefaultTest(TestCase):
    """存量/新建数据默认 origin=imported、origin_detail 空（不猜来源）。"""

    def test_rg_default_imported(self):
        goal = ResearchGoalFactory(name='Origin Default RG', slug='origin-default-rg')
        self.assertEqual(goal.origin, 'imported')
        self.assertEqual(goal.origin_detail, '')

    def test_ap_default_imported(self):
        app = ApplicationFactory(name='Origin Default AP', slug='origin-default-ap')
        self.assertEqual(app.origin, 'imported')
        self.assertEqual(app.origin_detail, '')

    def test_method_default_imported(self):
        method = MethodFactory(name='Origin Default Method', slug='origin-default-method')
        self.assertEqual(method.origin, 'imported')
        self.assertEqual(method.origin_detail, '')


class OriginChoicesTest(TestCase):
    """choices 三值合法：human_curated / ai_extracted / imported。"""

    def test_choices_enum(self):
        choices = dict(ResearchGoal._meta.get_field('origin').choices)
        self.assertEqual(
            set(choices),
            {'human_curated', 'ai_extracted', 'imported'},
        )

    def test_ai_extracted_assignable(self):
        goal = ResearchGoalFactory(
            name='AI Extracted RG', slug='ai-extracted-rg',
            origin='ai_extracted', origin_detail='extractor_v0.1|protocols:12,34,56')
        goal.refresh_from_db()
        self.assertEqual(goal.origin, 'ai_extracted')
        self.assertIn('extractor_v0.1', goal.origin_detail)

    def test_human_curated_assignable(self):
        method = MethodFactory(
            name='Human Curated Method', slug='human-curated-method',
            origin='human_curated', origin_detail='reviewed_by:admin')
        method.refresh_from_db()
        self.assertEqual(method.origin, 'human_curated')

    def test_invalid_choice_rejected(self):
        from django.core.exceptions import ValidationError
        app = ApplicationFactory(name='Bad Origin AP', slug='bad-origin-ap')
        app.origin = 'llm_guess'
        with self.assertRaises(ValidationError):
            app.full_clean()
