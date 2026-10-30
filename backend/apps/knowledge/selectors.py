from django.db.models import QuerySet, Prefetch
from .models import Method, Protocol, ProtocolStep, Application, ResearchGoal


def get_methods_by_application(application_id: int) -> QuerySet:
    """获取指定应用场景下的所有方法（M:N，经 ApplicationMethod 桥）。

    ★ 2026-10-30：原走 `Method.application` FK（1:N）。B 方案改为桥之后，
    同一方法可被多个应用共享，这里按 application_id 筛不会重复
    （`unique_together(application, method)` 保证）。
    """
    return Method.objects.filter(application_methods__application_id=application_id)


def get_protocols_with_steps(method_id: int) -> QuerySet:
    """获取指定方法下的协议（含步骤，经 MethodProtocol 桥）"""
    return Protocol.objects.filter(method_protocols__method_id=method_id).prefetch_related(
        Prefetch('steps', queryset=ProtocolStep.objects.order_by('step_no'))
    )


def get_application_detail(application_id: int):
    """获取应用场景详情（含方法和协议）"""
    return Application.objects.prefetch_related(
        Prefetch('research_goal_collections', queryset=ResearchGoal.objects.order_by('id')),
        Prefetch('methods', queryset=Method.objects.prefetch_related('method_protocols__protocol'))
    ).get(pk=application_id)


def get_research_goals_with_applications() -> QuerySet:
    """获取所有研究目标（含应用场景）"""
    return ResearchGoal.objects.prefetch_related(
        Prefetch('application_collection', queryset=Application.objects.order_by('id'))
    ).order_by('priority')
