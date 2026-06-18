"""
Knowledge Chain Quick Creator.

Creates a complete chain in one call:
ResearchGoal → Application → Method → Protocol
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.db import transaction

from apps.knowledge.models import ResearchGoal, Application, Method, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ChainInput:
    """Input for a knowledge chain creation."""
    goal_name: str = ''
    goal_summary: str = ''
    app_name: str = ''
    app_summary: str = ''
    method_name: str = ''
    method_purpose: str = ''
    protocol_name: str = ''
    protocol_objective: str = ''


@dataclass
class ChainReport:
    """Result of a knowledge chain creation."""
    success: bool = False
    created: dict = field(default_factory=lambda: {
        'ResearchGoal': 0, 'Application': 0,
        'Method': 0, 'Protocol': 0,
    })
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = 'SUCCESS' if self.success else 'FAILED'
        counts = ', '.join(f'{k}={v}' for k, v in self.created.items() if v)
        return f'[{status}] Created: {counts} | Errors: {len(self.errors)}'


def _slug(name: str) -> str:
    return name.lower().replace(' ', '-').replace('/', '-')[:200]


@transaction.atomic
def create_knowledge_chain(inp: ChainInput) -> ChainReport:
    """
    Create a complete knowledge chain in a single transaction.
    Rolls back all changes on failure.
    """
    report = ChainReport()

    # Validate
    if not inp.goal_name:
        report.errors.append('ResearchGoal name is required')
    if not inp.app_name:
        report.errors.append('Application name is required')
    if not inp.method_name:
        report.errors.append('Method name is required')
    if not inp.protocol_name:
        report.errors.append('Protocol name is required')

    if report.errors:
        report.success = False
        return report

    try:
        # 1. ResearchGoal
        goal, created = ResearchGoal.objects.update_or_create(
            slug=_slug(inp.goal_name),
            defaults={
                'name': inp.goal_name,
                'summary': inp.goal_summary,
                'status': 'active',
            },
        )
        if created:
            report.created['ResearchGoal'] = 1

        # 2. Application (FK → ResearchGoal)
        app, created = Application.objects.update_or_create(
            slug=_slug(inp.app_name),
            defaults={
                'name': inp.app_name,
                'summary': inp.app_summary,
                'research_goal': goal,
                'status': 'active',
            },
        )
        if created:
            report.created['Application'] = 1

        # 3. Method (FK → Application)
        method, created = Method.objects.update_or_create(
            slug=_slug(inp.method_name),
            defaults={
                'name': inp.method_name,
                'purpose': inp.method_purpose,
                'application': app,
                'status': 'active',
            },
        )
        if created:
            report.created['Method'] = 1

        # 4. Protocol (FK → Method)
        protocol, created = Protocol.objects.update_or_create(
            slug=_slug(inp.protocol_name),
            defaults={
                'name': inp.protocol_name,
                'objective': inp.protocol_objective,
                'method': method,
                'status': 'published',
            },
        )
        if created:
            report.created['Protocol'] = 1

        report.success = True

    except Exception as e:
        logger.exception('Chain creation failed')
        report.errors.append(f'Chain creation failed: {e}')
        report.success = False

    return report
