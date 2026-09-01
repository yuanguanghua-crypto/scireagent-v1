"""knowledge API 自定义 FilterSet。

#P0-1：Application 的 research_goal_id 过滤改按 M2M（research_goal_collections__id），
与 API 读取路径一致（T4 顶部链真实关联存于 M2M，非 FK research_goal）。
注意：M2M 定义在 ResearchGoal.application_collection（正向），
Application 侧反向名为 research_goal_collections，过滤用反向路径。
"""
import django_filters

from apps.knowledge.models import Application


class ApplicationFilter(django_filters.FilterSet):
    # 兼容旧参数名 research_goal_id，但按 M2M 反向关联过滤（research_goal_collections__id）
    research_goal_id = django_filters.NumberFilter(
        field_name='research_goal_collections__id',
        label='研究目标 id（按 M2M research_goal_collections 过滤）',
    )

    class Meta:
        model = Application
        fields = ['research_goal_id', 'status']
