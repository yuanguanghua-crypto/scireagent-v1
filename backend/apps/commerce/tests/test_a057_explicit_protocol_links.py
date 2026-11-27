"""产品↔协议"显式关联"通道（A-057，2026-11-27）。

## 改前是什么样（实测）
`LinkSource.EXPLICIT` 是**零写入点的死枚举**：`protocol_ids` 只被
`_sync_protocol_bridges` 消费，而它只写 `MethodProtocol`（把协议锚到某个方法），
产品↔协议表一行都不写；随后 `recompute_product` 把该行统一写成 `inherited`
（且 `update_fields` 里还带着 `link_source`，连已有的 explicit 也会被覆盖）。
前端再把"服务端返回了这一行"等同于"派生" ⇒ ✕ 锁死、标签显示"派生关联"。

## 本文件钉住四条
① 手工关联 → 落一条 `explicit` 行；
② 派生协议**不会**被错标成 explicit（用 MethodProtocol 派生集判定，不看有没有行）；
③ `recompute_product` 只改分数/档位，**不再改写 `link_source`**；
④ 解绑 → 只删 explicit 行；派生行不受影响。
"""
import pytest
from django.test import TestCase

from apps.bridges.models import MethodProtocol, ProductMethod, ProductProtocol
from apps.bridges.services.relevance import recompute_product
from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


class ExplicitProtocolLinkTest(TestCase):
    def setUp(self):
        self.product = ProductFactory()
        self.method = MethodFactory()
        self.derived_proto = ProtocolFactory(name='Derived Protocol')
        self.manual_proto = ProtocolFactory(name='Manual Protocol')
        # 方法链：product → method → derived_proto（这条是"派生"）
        ProductMethod.objects.create(product=self.product, method=self.method)
        MethodProtocol.objects.create(method=self.method, protocol=self.derived_proto)

    def _save(self, protocol_ids):
        ser = ProductCreateUpdateSerializer(
            self.product,
            data={'name': self.product.name, 'protocol_ids': protocol_ids},
            partial=True,
        )
        assert ser.is_valid(), ser.errors
        return ser.save()

    # ── ① 手工关联落 explicit ──────────────────────────────
    def test_manual_protocol_becomes_explicit(self):
        self._save([self.derived_proto.id, self.manual_proto.id])
        row = ProductProtocol.objects.get(product=self.product, protocol=self.manual_proto)
        assert row.link_source == ProductProtocol.LinkSource.EXPLICIT, (
            f'手工关联必须是 explicit，实得 {row.link_source}'
        )

    # ── ② 派生协议不被错标 ────────────────────────────────
    def test_derived_protocol_is_not_marked_explicit(self):
        self._save([self.derived_proto.id, self.manual_proto.id])
        derived = ProductProtocol.objects.filter(
            product=self.product, protocol=self.derived_proto).first()
        # 派生协议可能因低分不落库；落库的话来源必须是 inherited
        if derived is not None:
            assert derived.link_source != ProductProtocol.LinkSource.EXPLICIT

    # ── ③ 重算不改写来源 ──────────────────────────────────
    def test_recompute_does_not_overwrite_explicit(self):
        self._save([self.derived_proto.id, self.manual_proto.id])
        # 人为让手工行也落在派生集里（模拟"锚定后又经方法可达"），再重算
        MethodProtocol.objects.get_or_create(method=self.method, protocol=self.manual_proto)
        recompute_product(self.product)
        row = ProductProtocol.objects.get(product=self.product, protocol=self.manual_proto)
        assert row.link_source == ProductProtocol.LinkSource.EXPLICIT, (
            '★ 重算把 explicit 覆写成 inherited —— 这正是运营删不掉自己加的协议的原因'
        )

    # ── ④ 解绑只删 explicit ───────────────────────────────
    def test_unlink_removes_only_explicit_rows(self):
        self._save([self.derived_proto.id, self.manual_proto.id])
        assert ProductProtocol.objects.filter(
            product=self.product, protocol=self.manual_proto).exists()

        self._save([self.derived_proto.id])       # 解绑手工那条
        assert not ProductProtocol.objects.filter(
            product=self.product, protocol=self.manual_proto).exists(), \
            '解绑后 explicit 行必须消失'

    def test_omitting_protocol_ids_deletes_nothing(self):
        """没打算改关联就别动（与 method_ids 的"显式 vs 省略"语义一致）。"""
        self._save([self.derived_proto.id, self.manual_proto.id])
        ser = ProductCreateUpdateSerializer(
            self.product, data={'name': '改名而已'}, partial=True)
        assert ser.is_valid(), ser.errors
        ser.save()
        assert ProductProtocol.objects.filter(
            product=self.product, protocol=self.manual_proto).exists()
