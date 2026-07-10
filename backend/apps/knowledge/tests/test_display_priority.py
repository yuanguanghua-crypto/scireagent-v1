"""
TDD Tests for display_priority field on Application model.
Phase 1, Week 1.
"""
import pytest
from apps.knowledge.models import Application
from apps.knowledge.tests.factories import ApplicationFactory


@pytest.mark.django_db
class TestApplicationDisplayPriority:
    """T1-05 ~ T1-06: Application display_priority field."""

    def test_t1_05_default_value(self):
        """T1-05: Application has display_priority with default 0."""
        app = ApplicationFactory()
        assert app.display_priority == 0

    def test_t1_06_filter_gt_zero(self):
        """T1-06: Filter applications by display_priority > 0."""
        ApplicationFactory(display_priority=10)
        ApplicationFactory(display_priority=0)
        result = Application.objects.filter(display_priority__gt=0)
        assert result.count() == 1
