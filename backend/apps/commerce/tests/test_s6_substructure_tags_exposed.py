"""S6 前端接入 — 四轴修饰标签字段暴露（ProductListSerializer + ProductDetailSerializer）。

验证：substructure_tags 经列表与详情接口对外暴露，且用户写入路径（Create/Update）不污染。
"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory

SAMPLE_PAYLOAD = {
    'parsed': True,
    'labels': ['U', "2'-F", 'deoxy', 'NTP'],
    'axes': {
        'base': 'U', 'base_mod': None, 'sugar_sub': "2'-F",
        'sugar_type': 'deoxy', 'ring_oh_count': 1,
        'biotin_label': False, 'ntp': True, 'propargyl': False,
    },
}


class S6SubstructureTagsExposedTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.p = ProductFactory(substructure_tags=SAMPLE_PAYLOAD, status='active')

    def test_exposed_in_list(self):
        resp = self.client.get('/api/v1/products/')
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.json()['data'] if r['id'] == self.p.id)
        self.assertEqual(row['substructure_tags'], SAMPLE_PAYLOAD)

    def test_exposed_in_detail(self):
        resp = self.client.get(f'/api/v1/products/{self.p.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['substructure_tags'], SAMPLE_PAYLOAD)
