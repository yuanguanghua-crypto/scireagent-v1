"""Debug: run import with sample data and print report + ID map."""
import django
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
django.setup()

from core.json_importer import import_graph_json, _id_map

SAMPLE = {
    'metadata': {'version': '3.0', 'description': 'Test'},
    'ResearchGoal': [
        {'id': 'goal_001', 'name': 'RNA Labeling', 'summary': 'Test', 'priority': 'high'},
    ],
    'Application': [
        {'id': 'app_001', 'name': 'FISH', 'goals': ['goal_001']},
    ],
    'Method': [],
    'Protocol': [],
    'Product': [],
    'SKU': [],
}

report = import_graph_json(SAMPLE)
print(f'Success: {report.success}')
print(f'Errors: {report.errors}')
print(f'Imported: {report.imported}')
print(f'ID Map: {dict(_id_map)}')
for key in _id_map:
    print(f'  {key}: {_id_map[key]}')
