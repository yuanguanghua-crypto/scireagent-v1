from django.db import migrations

# Tables that carry a Postgres-only `search_vector` tsvector column.
# (Application, Method, Protocol, Reference — see _USE_POSTGRES in models.py.)
_SEARCH_TABLES = [
    ('application', 'application_search_gin'),
    ('method', 'method_search_gin'),
    ('protocol', 'protocol_search_gin'),
    ('reference', 'reference_search_gin'),
]


def add_search_vectors(apps, schema_editor):
    """PostgreSQL-only: add tsvector FTS columns + GIN indexes.

    These fields are conditional on Postgres (_USE_POSTGRES in models.py),
    so they were never present in the SQLite-generated migrations. Add them
    here so production Postgres matches the model. On SQLite this is a no-op
    (keeps dev/tests green).
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for table, gin in _SEARCH_TABLES:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS search_vector tsvector;"
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {gin} ON {table} USING gin(search_vector);"
            )


def remove_search_vectors(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for table, gin in _SEARCH_TABLES:
            cursor.execute(f"DROP INDEX IF EXISTS {gin};")
            cursor.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector;")


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0007_alter_application_research_goal_and_more'),
    ]

    operations = [
        migrations.RunPython(add_search_vectors, remove_search_vectors),
    ]
