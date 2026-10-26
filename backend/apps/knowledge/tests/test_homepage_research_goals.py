"""首页 Research Goals 区 —— 测试夹具过滤 + priority 排序方向。

背景（2026-10-26 用户报「首页分类/产品不一致」）：
`site_views.py` 的 research_goals 查询有两个缺陷叠加，
导致首页 6 个位置里有 5 个被 E2E 测试残留（`__e2e_goals_*` / `__curl_test_goal__`）占据：

1. 用的是 `ResearchGoal.objects` 而不是 `.public()` —— 本文件其它所有对外查询
   （Application/Method/Product）都走 `.public()`，唯独这里漏了。
2. `order_by('priority', 'id')` 是**升序**，而 priority 字段 help_text 明确写着
   「数字越大越靠前」。全站 11,037/11,045 个 goal 是默认值 0，升序把精心设过
   优先级的少数几条挤到最后。

这两个断言必须同时存在 —— 只修一个，首页仍然不对。
"""
import pytest
from rest_framework.test import APIClient

from apps.knowledge.tests.factories import ResearchGoalFactory

URL = '/api/v1/site/home'


@pytest.mark.django_db
class TestHomepageResearchGoals:
    def setup_method(self):
        self.client = APIClient()

    def _goals(self):
        return self.client.get(URL).json()['data']['research_goals']

    def test_test_fixture_goal_never_shown(self):
        """is_test_fixture=True 的 goal 不能出现在首页 —— 即使 priority 最高。"""
        fixture = ResearchGoalFactory(
            name='__e2e_goals_9999999999__',
            is_test_fixture=True,
            priority=9999,          # 故意给最高优先级：若过滤缺失，它一定会排在首位
        )
        real = ResearchGoalFactory(name='RNA Labeling & Detection',
                                   is_test_fixture=False, priority=10)

        ids = [g['id'] for g in self._goals()]
        assert fixture.id not in ids, '测试夹具泄漏到首页（.public() 过滤缺失）'
        assert real.id in ids

    def test_priority_descending(self):
        """priority 大的排在前面 —— 与字段 help_text「数字越大越靠前」一致。"""
        low = ResearchGoalFactory(name='Low Priority Goal',
                                  is_test_fixture=False, priority=1)
        high = ResearchGoalFactory(name='High Priority Goal',
                                   is_test_fixture=False, priority=500)

        ids = [g['id'] for g in self._goals()]
        assert high.id in ids and low.id in ids, '两个 goal 都应在前 6 内'
        assert ids.index(high.id) < ids.index(low.id), \
            'priority 500 应排在 priority 1 之前（当前是升序，语义反了）'

    def test_returns_at_most_six(self):
        for i in range(9):
            ResearchGoalFactory(name=f'Goal {i}', is_test_fixture=False, priority=i)
        assert len(self._goals()) <= 6
