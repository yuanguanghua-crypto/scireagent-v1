from rest_framework import serializers
from ...models import Batch, Coa, SdsRevision, PubChemCache


class BatchSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    product_name = serializers.CharField(source='sku.product.name', read_only=True)
    has_coa = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = [
            'id', 'sku', 'sku_code', 'product_name', 'lot_number',
            'produced_at', 'retest_at', 'has_coa', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_has_coa(self, obj):
        return hasattr(obj, 'coa') and obj.coa is not None


class CoaSerializer(serializers.ModelSerializer):
    lot_number = serializers.CharField(source='batch.lot_number', read_only=True)
    produced_at = serializers.DateField(source='batch.produced_at', read_only=True)
    sku_code = serializers.CharField(source='batch.sku.sku_code', read_only=True)
    product_id = serializers.IntegerField(source='batch.sku.product_id', read_only=True)

    class Meta:
        model = Coa
        fields = [
            'id', 'doc_id', 'status', 'batch', 'lot_number', 'produced_at', 'sku_code',
            'product_id',
            # 产品快照
            'product_name', 'catalog_number', 'cas_number',
            'molecular_formula', 'molecular_weight', 'storage_condition',
            # QC 结果
            'appearance_spec', 'appearance_result',
            'purity_spec', 'purity_result', 'purity_method',
            'water_content_spec', 'water_content_result',
            'melting_point', 'specific_rotation',
            'residual_solvents', 'heavy_metals',
            'nmr_result', 'lcms_result',
            # 色谱条件
            'hplc_conditions', 'lcms_conditions',
            # 签署
            'qc_analyst', 'qa_approval', 'approved_at',
            # PDF
            'pdf_path',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'doc_id', 'status', 'product_name', 'catalog_number',
            'cas_number', 'molecular_formula', 'molecular_weight', 'storage_condition',
            'approved_at', 'pdf_path', 'created_at', 'updated_at',
        ]


class CoaQcUpdateSerializer(serializers.Serializer):
    """COA QC 实测值更新"""
    appearance_result = serializers.CharField(required=False, allow_blank=True)
    purity_result = serializers.CharField(required=False, allow_blank=True)
    purity_method = serializers.CharField(required=False, allow_blank=True)
    water_content_spec = serializers.CharField(required=False, allow_blank=True)
    water_content_result = serializers.CharField(required=False, allow_blank=True)
    melting_point = serializers.CharField(required=False, allow_blank=True)
    specific_rotation = serializers.CharField(required=False, allow_blank=True)
    residual_solvents = serializers.CharField(required=False, allow_blank=True)
    heavy_metals = serializers.CharField(required=False, allow_blank=True)
    nmr_result = serializers.CharField(required=False, allow_blank=True)
    lcms_result = serializers.CharField(required=False, allow_blank=True)
    hplc_conditions = serializers.CharField(required=False, allow_blank=True)
    lcms_conditions = serializers.CharField(required=False, allow_blank=True)


class CoaApproveSerializer(serializers.Serializer):
    """COA 审批"""
    qc_analyst = serializers.CharField(required=False, allow_blank=True, default='')
    qa_approval = serializers.CharField(required=False, allow_blank=True, default='')


class CoaCreateSerializer(serializers.Serializer):
    """创建 COA（Batch + Coa draft）"""
    sku_id = serializers.IntegerField()
    lot_number = serializers.CharField(max_length=50)
    produced_at = serializers.DateField()
    retest_at = serializers.DateField(required=False, allow_null=True, default=None)


class SdsRevisionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    catalog_no = serializers.CharField(source='product.catalog_no', read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = SdsRevision
        fields = [
            'id', 'product', 'product_name', 'catalog_no',
            'revision_no', 'revised_at', 'change_note',
            'signal_word', 'pictograms', 'hazard_codes', 'precaution_codes',
            'section_data', 'pdf_path', 'is_current', 'created_at',
        ]
        read_only_fields = [
            'id', 'revision_no', 'signal_word', 'pictograms',
            'hazard_codes', 'precaution_codes', 'section_data',
            'pdf_path', 'created_at',
        ]

    def get_is_current(self, obj):
        product = obj.product
        return product.current_sds_id == obj.id if product.current_sds_id else False


class SdsGenerateSerializer(serializers.Serializer):
    """生成 SDS"""
    product_id = serializers.IntegerField()


class SdsApproveSerializer(serializers.Serializer):
    """审批 SDS — 无需额外参数"""
    pass


class PubChemCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = PubChemCache
        fields = ['id', 'cas_number', 'cid', 'fetched_at']
        read_only_fields = fields
