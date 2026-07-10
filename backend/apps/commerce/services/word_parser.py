"""解析 Word (.docx) 产品说明文档为结构化 JSON。

用于研究员工作台的 Word 导入功能。
"""
import base64
import re
from io import BytesIO

from django.core.exceptions import ValidationError
from docx import Document


class FileUnreadableError(Exception):
    """文件无法读取（损坏或加密）。"""


class FileTooLargeError(Exception):
    """文件超过大小限制。"""


MAX_UPLOAD_SIZE_MB = 10


class WordParserService:
    """按前缀标签正则提取 Word 文档中的产品字段。

    支持 110 个 SciReagent 产品说明文档的标准格式。
    """

    # 匹配 "Label: value" 模式
    LABEL_PATTERN = re.compile(r'^([A-Za-z ]+?):\s*(.+)$')

    # 匹配 "10ul (100 mM)" 或 "1mg" — 拆出数值、单位、(可选)浓度数值、浓度单位
    SIZE_PATTERN = re.compile(
        r'^(\d+(?:\.\d+)?)\s*([a-zA-Zµµ]+)'
        r'(?:\s*\(\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµµ%]+)\s*\))?'
    )

    # 单位标准化（小写输入 → 标准显示形式）
    UNIT_NORMALIZE = {
        'ul': 'µL', 'µl': 'µL',
        'ml': 'mL', 'l': 'L',
        'ug': 'µg', 'µg': 'µg',
        'mg': 'mg', 'g': 'g',
        'mm': 'mM', 'um': 'µM',
    }

    def parse(self, file):
        """解析上传的 .docx 文件，返回结构化字段字典。

        Args:
            file: Django UploadedFile 对象。

        Returns:
            dict: {"fields_found": int, "data": {...}}

        Raises:
            FileUnreadableError: 文件无法读取。
            FileTooLargeError: 文件超过 10MB。
            ValidationError: 非 .docx 文件。
        """
        if not file.name.lower().endswith('.docx'):
            raise ValidationError('仅支持 .docx 格式')

        if file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise FileTooLargeError(f'文件大小超过 {MAX_UPLOAD_SIZE_MB}MB 限制')

        try:
            doc = Document(file)
        except Exception as e:
            raise FileUnreadableError('文件无法读取，可能已损坏或加密') from e

        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

        result = {'skus': [], 'fields_found': 0}
        description_parts = []

        # 首段 = 产品名
        if paragraphs:
            result['product_name'] = paragraphs[0]
            result['fields_found'] += 1

        for p in paragraphs[1:]:
            if p.lower() == 'chemical structure:' or p.lower().startswith('chemical structure'):
                # 跳过 "Chemical structure:" 段落（后面是图片占位符）
                continue
            matched = self._match_label(p)
            if matched:
                result[matched['key']] = matched['value']
                result['fields_found'] += 1
            else:
                description_parts.append(p)

        if description_parts:
            result['description'] = '\n\n'.join(description_parts)

        self._parse_skus(result)
        result['structure_image_base64'] = self._extract_images(doc)

        return result

    def _match_label(self, paragraph):
        """尝试匹配 "Label: value" 模式，提取字段键和值。

        Returns:
            dict {"key": str, "value": str} 或 None。
        """
        m = self.LABEL_PATTERN.match(paragraph)
        if not m:
            return None

        label = m.group(1).strip().lower()
        value = m.group(2).strip()

        # 映射标签到结果键
        label_map = {
            'cas number': 'cas',
            'catalog number': 'catalog_number',
            'formula': 'formula',
            'molecular weight': 'molecular_weight',
            'purity': 'purity',
            'concentration': 'concentration',
            'storage': 'storage',
            'shipping condition': 'shipping',
            'size': 'size',
            'price': 'price',
            'synonyms': 'synonyms',
        }

        key = label_map.get(label)
        if key:
            return {'key': key, 'value': value}
        return None

    def _parse_skus(self, result):
        """从 'size' 和 'price' 字段解析 SKU 列表，拆分出 pack_unit/conc_unit。

        Size: "10ul (100 mM)/ 50ul (100 mM)/ 100ul (100 mM)"
        Price: "$79/$349/$649"
        按 / 分割后按位置配对，再把每个 size 拆成 pack_size+pack_unit
        (+ concentration+conc_unit)。
        """
        if 'size' not in result or 'price' not in result:
            return

        sizes = [s.strip() for s in result['size'].split('/')]
        prices = [s.strip().replace('$', '') for s in result['price'].split('/')]

        for i in range(min(len(sizes), len(prices))):
            sku = {'pack_size': sizes[i], 'price': prices[i]}
            m = self.SIZE_PATTERN.match(sizes[i])
            if m:
                sku['pack_size'] = m.group(1)
                sku['pack_unit'] = self.UNIT_NORMALIZE.get(
                    m.group(2).lower(), m.group(2))
                if m.group(3):
                    sku['concentration'] = m.group(3)
                    sku['conc_unit'] = self.UNIT_NORMALIZE.get(
                        m.group(4).lower(), m.group(4))
            result['skus'].append(sku)

    def _extract_images(self, doc):
        """从文档中提取第一张嵌入式图片的 base64 编码。

        Returns:
            str: "data:image/png;base64,..." 或 None。
        """
        try:
            for rel in doc.part.rels.values():
                if 'image' in rel.reltype:
                    image = rel.target_part
                    image_data = image.blob
                    ext = image.partname.split('.')[-1].lower()
                    if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
                        if ext == 'jpg':
                            ext = 'jpeg'
                        b64 = base64.b64encode(image_data).decode('utf-8')
                        return f'data:image/{ext};base64,{b64}'
                    return None
        except Exception:
            return None

        return None
