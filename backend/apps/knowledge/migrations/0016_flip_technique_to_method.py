# 数据迁移：将既有 facet_type='technique' 翻转为 'method'。
# 背景：method facet 由 k=80 聚类（dimension=technique）改名而来，复用已部署数据。
# 仅改 facet_type 值；ProtocolFacet 通过 facet FK 关联，不受影响。

from django.db import migrations


def flip_technique_to_method(apps, schema_editor):
    FacetValue = apps.get_model('knowledge', 'FacetValue')
    updated = FacetValue.objects.filter(facet_type='technique').update(facet_type='method')
    return updated


def flip_method_to_technique(apps, schema_editor):
    FacetValue = apps.get_model('knowledge', 'FacetValue')
    FacetValue.objects.filter(facet_type='method').update(facet_type='technique')


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0015_alter_facetvalue_facet_type_alter_protocol_facets'),
    ]

    operations = [
        migrations.RunPython(flip_technique_to_method, flip_method_to_technique),
    ]
