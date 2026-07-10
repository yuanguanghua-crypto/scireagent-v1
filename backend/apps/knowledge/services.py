from django.utils import timezone
from django.db import transaction
from .models import Protocol, ProtocolStep


class KnowledgeService:
    """知识层域服务 — 处理跨模型业务逻辑"""

    @staticmethod
    @transaction.atomic
    def publish_protocol(protocol_id: int) -> Protocol:
        """发布协议 — 设置状态和发布时间"""
        protocol = Protocol.objects.select_for_update().get(pk=protocol_id)
        protocol.status = Protocol.PublicationStatus.PUBLISHED
        protocol.published_at = timezone.now()
        protocol.save(update_fields=['status', 'published_at'])
        return protocol

    @staticmethod
    @transaction.atomic
    def supersede_protocol(protocol_id: int) -> Protocol:
        """取代协议 — 标记旧版本为已取代"""
        protocol = Protocol.objects.select_for_update().get(pk=protocol_id)
        protocol.status = Protocol.PublicationStatus.SUPERSEDED
        protocol.superseded_at = timezone.now()
        protocol.save(update_fields=['status', 'superseded_at'])
        return protocol

    @staticmethod
    @transaction.atomic
    def create_protocol_with_steps(validated_data: dict, steps_data: list) -> Protocol:
        """创建协议及其步骤"""
        steps = steps_data if isinstance(steps_data, list) else steps_data.get('steps', [])
        protocol = Protocol.objects.create(**validated_data)
        ProtocolStep.objects.bulk_create([
            ProtocolStep(protocol=protocol, **step) for step in steps
        ])
        return protocol
