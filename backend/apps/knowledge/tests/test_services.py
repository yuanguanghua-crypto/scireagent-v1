from django.test import TestCase
from django.utils import timezone
from apps.knowledge.services import KnowledgeService
from apps.knowledge.models import Protocol, ProtocolStep
from apps.knowledge.tests.factories import ProtocolFactory, ProtocolStepFactory


class KnowledgeServicePublishProtocolTest(TestCase):
    def test_publish_protocol_sets_status(self):
        """Publishing should set status to 'published'"""
        protocol = ProtocolFactory(status='draft')
        result = KnowledgeService.publish_protocol(protocol.id)
        protocol.refresh_from_db()
        self.assertEqual(protocol.status, 'published')

    def test_publish_protocol_sets_published_at(self):
        """Publishing should set published_at timestamp"""
        protocol = ProtocolFactory(status='draft')
        result = KnowledgeService.publish_protocol(protocol.id)
        protocol.refresh_from_db()
        self.assertIsNotNone(protocol.published_at)

    def test_publish_protocol_returns_protocol(self):
        protocol = ProtocolFactory()
        result = KnowledgeService.publish_protocol(protocol.id)
        self.assertIsInstance(result, Protocol)

    def test_publish_protocol_nonexistent_raises(self):
        with self.assertRaises(Protocol.DoesNotExist):
            KnowledgeService.publish_protocol(99999)


class KnowledgeServiceSupersedeProtocolTest(TestCase):
    def test_supersede_protocol_sets_status(self):
        """Superseding should set status to 'superseded'"""
        protocol = ProtocolFactory(status='published')
        result = KnowledgeService.supersede_protocol(protocol.id)
        protocol.refresh_from_db()
        self.assertEqual(protocol.status, 'superseded')

    def test_supersede_protocol_sets_superseded_at(self):
        protocol = ProtocolFactory(status='published')
        result = KnowledgeService.supersede_protocol(protocol.id)
        protocol.refresh_from_db()
        self.assertIsNotNone(protocol.superseded_at)

    def test_supersede_protocol_returns_protocol(self):
        protocol = ProtocolFactory()
        result = KnowledgeService.supersede_protocol(protocol.id)
        self.assertIsInstance(result, Protocol)


class KnowledgeServiceCreateProtocolWithStepsTest(TestCase):
    def test_create_protocol_with_steps(self):
        from apps.knowledge.tests.factories import MethodFactory
        method = MethodFactory()
        validated_data = {
            'method': method,
            'name': 'Test Protocol',
            'slug': 'test-protocol',
            'version': '1.0',
        }
        steps_data = [
            {'step_no': 1, 'title': 'Step 1', 'body': 'Body 1'},
            {'step_no': 2, 'title': 'Step 2', 'body': 'Body 2'},
        ]
        protocol = KnowledgeService.create_protocol_with_steps(validated_data, steps_data)
        self.assertEqual(protocol.name, 'Test Protocol')
        self.assertEqual(protocol.steps.count(), 2)

    def test_create_protocol_steps_ordering(self):
        from apps.knowledge.tests.factories import MethodFactory
        method = MethodFactory()
        validated_data = {
            'method': method,
            'name': 'Test Protocol',
            'slug': 'test-protocol-2',
            'version': '1.0',
        }
        steps_data = [
            {'step_no': 1, 'title': 'First'},
            {'step_no': 2, 'title': 'Second'},
            {'step_no': 3, 'title': 'Third'},
        ]
        protocol = KnowledgeService.create_protocol_with_steps(validated_data, steps_data)
        steps = list(protocol.steps.values_list('title', flat=True).order_by('step_no'))
        self.assertEqual(steps, ['First', 'Second', 'Third'])
