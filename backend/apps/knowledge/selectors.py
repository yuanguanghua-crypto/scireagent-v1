from django.db.models import QuerySet, Prefetch
from .models import Method, Protocol, ProtocolStep, Application, ResearchGoal


def get_methods_by_application(application_id: int) -> QuerySet:
    """获取指定应用场景下的所有方法"""
    return Method.objects.filter(application_id=application_id).select_related('application')


def get_protocols_with_steps(method_id: int) -> QuerySet:
    """获取指定方法下的协议（含步骤）"""
    return Protocol.objects.filter(method_id=method_id).prefetch_related(
        Prefetch('steps', queryset=ProtocolStep.objects.order_by('step_no'))
    ).select_related('method')


def get_application_detail(application_id: int):
    """获取应用场景详情（含方法和协议）"""
    return Application.objects.select_related('research_goal').prefetch_related(
        Prefetch('methods', queryset=Method.objects.prefetch_related('protocols'))
    ).get(pk=application_id)


def get_research_goals_with_applications() -> QuerySet:
    """获取所有研究目标（含应用场景）"""
    return ResearchGoal.objects.prefetch_related('applications').order_by('priority')
