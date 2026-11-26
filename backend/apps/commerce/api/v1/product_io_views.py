"""产品列表的 CSV 导出 / 导入（A-028）。

## 为什么是 CSV 而不是 xlsx
用户拍板选 CSV：**零新依赖**。`openpyxl` 本地装了但**不在 requirements.txt**，
用它就得改依赖并 rebuild 后端。CSV 用标准库即可，且 Excel 能直接打开
（用 `utf-8-sig` 带 BOM，中文不乱码）。

## CSV 是单表 ⇒ 只导/导产品主表
SKU 是一个产品多行，塞进同一张表会让产品字段重复、导入时无法定位是改哪个 SKU。
本批**不处理 SKU**（导出不含、导入不改），这是明确的范围边界。

## 导出：必须与列表页看到的一致
不自己重写筛选逻辑 —— 直接实例化 `ProductViewSet` 调 `get_queryset()` + `filter_queryset()`。
否则一旦列表侧新增过滤（如 `is_test_fixture`、`archived`），导出就会"多出来一批"。

## 导入：两段式 + 只更新 + 白名单
- `?dry_run=1`（默认）：全量校验，出一份逐行报告，**不写库**
- `?apply=1`：校验通过才写；**任一行不合格就整体不写**（不做部分成功）
- 匹配键 `catalog_no`，**只更新已有产品**（新建走页面，那边有分类/默认SKU/价格等一整套校验）
- **字段白名单**：`status` / `archived` / `slug` **不可通过导入改** —— 这三个是状态机字段
"""
import csv
import io
import logging

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin

from apps.commerce.models import Product

logger = logging.getLogger(__name__)

#: 导出/导入共用的列（顺序即 CSV 列序）。`catalog_no` 是匹配键，导入时不可改。
COLUMNS = [
    ('catalog_no', '目录号'),
    ('name', '产品名称'),
    ('cas', 'CAS号'),
    ('smiles', 'SMILES'),
    ('inchi', 'InChI'),
    ('formula', '分子式'),
    ('molecular_weight', '分子量'),
    ('purity', '纯度'),
    ('concentration', '浓度'),
    ('storage', '储存条件'),
    ('shipping', '运输条件'),
    ('lead_time', '货期'),
    ('shelf_life', '保质期'),
    ('research_use_only', '仅限研究用途'),
]

#: 分类名只读展示，**导入时忽略**（FK 用名字匹配容易错配）
READONLY_COLUMNS = [('product_class_name', '分类（只读）')]

#: 允许导入更新的字段（白名单）。`catalog_no` 是键，不在此列。
IMPORTABLE = {
    'name', 'cas', 'smiles', 'inchi', 'formula', 'molecular_weight',
    'purity', 'concentration', 'storage', 'shipping', 'lead_time',
    'shelf_life', 'research_use_only',
}

#: 明确禁止通过导入修改的字段 —— 刻意给错误提示，而不是静默忽略
FORBIDDEN = {'status', 'archived', 'slug', 'catalog_no'}


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


class ProductExportView(EnvelopeMixin, APIView):
    """GET /api/v1/products/export/ —— 导出**当前筛选结果**为 CSV。

    沿用列表页的全部查询参数（`search` / `product_class_id` / `research_use_only` /
    `ordering` 等），因为内部复用 `ProductViewSet.get_queryset()` + `filter_queryset()`。
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.commerce.api.v1.views import ProductViewSet

        view = ProductViewSet()
        view.request = request
        view.action = 'list'
        view.format_kwarg = None
        qs = view.filter_queryset(view.get_queryset())
        qs = qs.select_related('product_class')

        buf = io.StringIO()
        writer = csv.writer(buf)
        header = [label for _, label in COLUMNS] + [label for _, label in READONLY_COLUMNS]
        writer.writerow(header)

        n = 0
        # get_queryset 带 prefetch_related ⇒ iterator() 必须给 chunk_size
        for p in qs.iterator(chunk_size=200):
            row = [_cell(getattr(p, f)) for f, _ in COLUMNS]
            row.append(p.product_class.name if p.product_class_id else '')
            writer.writerow(row)
            n += 1

        # utf-8-sig：带 BOM，Excel 双击打开中文不乱码
        resp = HttpResponse(
            '\ufeff' + buf.getvalue(),
            content_type='text/csv; charset=utf-8-sig',
        )
        resp['Content-Disposition'] = 'attachment; filename="products.csv"'
        logger.info('[product-io] export user=%s rows=%s', request.user.pk, n)
        return resp


class ProductImportView(EnvelopeMixin, APIView):
    """POST /api/v1/products/import/ —— 上传 CSV，更新已有产品（按 catalog_no 匹配）。

    参数：
      file      —— CSV 文件（multipart）
      dry_run=1 —— 默认：只校验出报告，不写库
      apply=1   —— 校验通过后落库

    返回（两种模式同构）：
      { total, matched, will_update, unchanged, errors: [{line, catalog_no, field, error}],
        forbidden: [{line, field}], applied: bool }

    ⚠️ 任一行有错误 ⇒ **整体不写**（不做部分成功）。理由：批量导入的部分成功
       最难排查 —— 用户无法知道哪些进了、哪些没进，只能全表重导。
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return self.error_response('请上传 CSV 文件（field: file）', code='FILE_REQUIRED',
                                       status_code=400)

        raw = upload.read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = raw.decode('gbk')     # 兼容 Excel 另存的中文 CSV
            except UnicodeDecodeError:
                return self.error_response(
                    'CSV 编码无法识别（要求 UTF-8 或 GBK）', code='BAD_ENCODING',
                    status_code=400)

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return self.error_response('CSV 为空或缺少表头', code='EMPTY_CSV', status_code=400)

        # 表头映射：既接受中文列名，也接受英文 key
        label_to_field = {label: f for f, label in COLUMNS + READONLY_COLUMNS}
        field_names = set()
        forbidden_hits = []
        for name in reader.fieldnames:
            name = (name or '').strip()
            if name in label_to_field:
                field_names.add(label_to_field[name])
            elif name in IMPORTABLE or name in FORBIDDEN:
                field_names.add(name)
            elif name:
                # 未知列 → 不致命，但要如实报出来（避免用户以为导进去了）
                forbidden_hits.append({'line': 1, 'field': name, 'error': '未知列，已忽略'})

        if 'catalog_no' not in field_names:
            return self.error_response(
                'CSV 必须包含「目录号」(catalog_no) 列作为匹配键',
                code='MISSING_KEY', status_code=400)

        want_apply = (request.query_params.get('apply') or '').lower() in ('1', 'true', 'yes')

        total = 0
        matched = 0
        will_update = 0
        unchanged = 0
        errors = []
        rows_to_write = []

        for idx, row in enumerate(reader, start=2):   # 第 1 行是表头
            # 跳过全空行
            if not any((v or '').strip() for v in row.values()):
                continue
            total += 1

            def get(field):
                for key in (field, *[l for f, l in COLUMNS if f == field]):
                    if key in row and row[key] is not None:
                        return (row[key] or '').strip()
                return ''

            catalog_no = get('catalog_no')
            if not catalog_no:
                errors.append({'line': idx, 'catalog_no': '', 'field': 'catalog_no',
                               'error': '目录号为空，无法匹配'})
                continue

            product = Product.objects.filter(catalog_no=catalog_no).first()
            if not product:
                errors.append({'line': idx, 'catalog_no': catalog_no, 'field': 'catalog_no',
                               'error': '目录号不存在（本批只支持更新已有产品，新建请走页面）'})
                continue
            matched += 1

            updates = {}
            # 白名单字段
            for field in IMPORTABLE:
                if field not in field_names:
                    continue
                raw_val = get(field)
                # ★ 2026-11-26（A-028）：**空单元格 = 不修改**，绝不是"清空"。
                #   否则用户只填「目录号 + 新名称」、其余留空，一次导入就会把
                #   CAS / 分子式 / 浓度 / 纯度 等全部**静默清空** —— 这是批量事故。
                #   代价：无法通过导入把字段改回空值（那属于"删除数据"，应走页面）。
                if raw_val == '':
                    continue
                if field == 'research_use_only':
                    val = raw_val.lower() in ('1', 'true', 'yes', 'y', '是')
                elif field == 'molecular_weight':
                    if raw_val == '':
                        val = None
                    else:
                        try:
                            val = float(raw_val)
                        except ValueError:
                            errors.append({'line': idx, 'catalog_no': catalog_no,
                                           'field': field, 'error': f'不是数字：{raw_val!r}'})
                            continue
                else:
                    val = raw_val
                if getattr(product, field) != val:
                    updates[field] = val

            # 禁止字段：给了值就明确报错（不静默忽略）
            for field in FORBIDDEN - {'catalog_no'}:
                if field in field_names and get(field):
                    errors.append({
                        'line': idx, 'catalog_no': catalog_no, 'field': field,
                        'error': f'{field} 是状态机字段，不能通过导入修改（请走产品页）',
                    })

            if updates:
                will_update += 1
                rows_to_write.append((product, updates))
            else:
                unchanged += 1

        applied = False
        if want_apply and not errors and rows_to_write:
            from django.db import transaction
            with transaction.atomic():
                for product, updates in rows_to_write:
                    # update() 而非 save()：不经 save() 就不会触发任何重算/信号，
                    # 也不会把 updated_at 之外的字段带跑（导入只改白名单列）
                    Product.objects.filter(pk=product.pk).update(**updates)
            applied = True
            logger.info('[product-io] import applied user=%s rows=%s',
                        request.user.pk, len(rows_to_write))

        return self.success_response({
            'total': total,
            'matched': matched,
            'will_update': will_update,
            'unchanged': unchanged,
            'errors': errors,
            'ignored_columns': forbidden_hits,
            'applied': applied,
            'dry_run': not applied,
        })
