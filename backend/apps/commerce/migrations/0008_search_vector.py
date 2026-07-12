from django.db import migrations


def add_search_vector(apps, schema_editor):
    """PostgreSQL-only: add the tsvector FTS column + GIN index.

    The Product.search_vector field is conditional on Postgres
    (_USE_POSTGRES in models.py), so it was never present in the
    SQLite-generated migrations. Add it here so production Postgres
    matches the model. On SQLite this is a no-op (keeps dev/tests green).
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE product ADD COLUMN IF NOT EXISTS search_vector tsvector;"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS product_search_gin "
            "ON product USING gin(search_vector);"
        )


def remove_search_vector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS product_search_gin;")
        cursor.execute("ALTER TABLE product DROP COLUMN IF EXISTS search_vector;")


class Migration(migrations.Migration):
    dependencies = [
        ('commerce', '0007_shrink_category_l1'),
    ]

    operations = [
        migrations.RunPython(add_search_vector, remove_search_vector),
    ]
