"""
Admin view for Agent JSON Knowledge Graph import.

Flow: Upload JSON → Validate → Preview → Confirm Import
"""
import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import path
from django.conf import settings

from core.json_validator import validate_graph_json
from core.json_importer import import_graph_json

logger = logging.getLogger(__name__)


@staff_member_required
def knowledge_import_view(request):
    """Multi-step import: upload → validate → preview → confirm → import."""
    context = {
        'title': 'Knowledge Import',
        'site_title': getattr(settings, 'UNFOLD', {}).get('SITE_TITLE', 'Admin'),
        'site_header': getattr(settings, 'UNFOLD', {}).get('SITE_HEADER', 'Admin'),
    }

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # Step 2: Upload & Validate
        if action == 'upload':
            uploaded_file = request.FILES.get('json_file')
            if not uploaded_file:
                context['error'] = 'Please select a JSON file to upload.'
                return render(request, 'admin/knowledge_import.html', context)

            try:
                raw_data = json.loads(uploaded_file.read().decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                context['error'] = f'Invalid JSON file: {e}'
                return render(request, 'admin/knowledge_import.html', context)

            # Validate
            validation = validate_graph_json(raw_data)
            context['validation'] = validation
            context['validation_json'] = json.dumps(validation.summary)

            if validation.is_valid:
                context['can_import'] = True
                # Store validated data in session for the import step
                request.session['import_data'] = raw_data
                # Build a flattened preview list
                preview = []
                for entity_type, entities in raw_data.items():
                    if entity_type == 'metadata':
                        continue
                    if not isinstance(entities, list):
                        continue
                    for entity in entities:
                        if not isinstance(entity, dict):
                            continue
                        preview.append({
                            'type': entity_type,
                            'id': entity.get('id', '?'),
                            'name': entity.get('name', entity.get('catalog_no', '?')),
                            'action': 'Create' if entity.get('id') else 'Update',
                        })
                context['preview'] = preview
                context['entity_count'] = len(preview)
                context['metadata'] = raw_data.get('metadata', {})
            else:
                context['can_import'] = False

            return render(request, 'admin/knowledge_import.html', context)

        # Step 3: Confirm Import
        elif action == 'import':
            import_data = request.session.pop('import_data', None)
            if not import_data:
                context['error'] = 'No validated data found. Please upload again.'
                return render(request, 'admin/knowledge_import.html', context)

            report = import_graph_json(import_data)
            context['import_report'] = report

            return render(request, 'admin/knowledge_import.html', context)

    # Step 1: Show upload form (GET)
    return render(request, 'admin/knowledge_import.html', context)


# For admin URL registration
urlpatterns = [
    path('knowledge-import/', knowledge_import_view, name='knowledge-import'),
]
