"""
COA PDF 生成服务 — 使用 ReportLab
"""
import os
import re

from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── 颜色常量 ──
BLUE = HexColor('#0ea5e9')
DARK = HexColor('#1e293b')
GRAY = HexColor('#64748b')
LIGHT_GRAY = HexColor('#f8fafc')
BORDER = HexColor('#e2e8f0')
GREEN = HexColor('#16a34a')
WHITE = HexColor('#ffffff')


# ── QC 判定（A-055 / A-210）──────────────────────────────────────────────
# 三条铁律：
#   ① 没有结果 ⇒ 不给结论（空值，不是 PASS）；
#   ② 有结果但没有规格 ⇒ '—'（Not evaluated）—— 没有尺子就谈不上合格；
#   ③ 有规格 ⇒ 真比较；规格写法解析不了 ⇒ '—'，**绝不**默认 PASS。

_NUM_RE = re.compile(r'[-+]?\d+(?:\.\d+)?')
# 区间专用：不带符号，避免 '98-102' 被读成 98 与 -102
_UNSIGNED_NUM_RE = re.compile(r'\d+(?:\.\d+)?')


def _first_number(text):
    """取字符串里第一个数字（'85.2%' → 85.2；'≤ 0.5%' → 0.5）。解析不出返回 None。"""
    m = _NUM_RE.search(str(text or '').replace(',', ''))
    return float(m.group()) if m else None


def _verdict(spec, result):
    """按规格与实测值给出 PASS / FAIL / '—'（Not evaluated）。

    支持的规格写法：
      · 文本一致性：`Conforms`（结果里出现 conform/pass 判 PASS）
      · 单侧限：`≤ 0.5%`、`<=0.5`、`<5`、`≥ 98%`、`>=98`、`>90`
      · 区间：`98-102%` / `98.0 – 102.0`（连字符或 en dash）
    其余写法（如 `MW: 523.4`、`Visual`、空）一律 '—' —— 判不了就说判不了。
    """
    res = str(result or '').strip()
    spc = str(spec or '').strip()
    if not res:
        return ''
    if not spc:
        return '—'

    low = spc.lower()
    # ① 文本一致性（Conforms / Passes）
    if 'conform' in low or low in ('pass', 'passes'):
        return 'PASS' if ('conform' in res.lower() or 'pass' in res.lower()) else 'FAIL'

    rv = _first_number(res)
    # ② 单侧限
    for token, op in (('≤', 'le'), ('<=', 'le'), ('≥', 'ge'), ('>=', 'ge'),
                      ('<', 'lt'), ('>', 'gt')):
        if low.startswith(token):
            sv = _first_number(spc[len(token):])
            if sv is None or rv is None:
                return '—'
            ok = {'le': rv <= sv, 'ge': rv >= sv, 'lt': rv < sv, 'gt': rv > sv}[op]
            return 'PASS' if ok else 'FAIL'

    # ③ 区间（两端都是数字）
    # ⚠️ 不能用带符号的 `_NUM_RE`：'98-102%' 会被切成 ['98','-102']，
    #    于是任何值都 < 98 的下界判断反了（实测 98-102% / 100 ⇒ FAIL）。
    nums = _UNSIGNED_NUM_RE.findall(spc.replace(',', ''))
    if len(nums) >= 2 and ('-' in spc or '–' in spc):
        lo, hi = float(nums[0]), float(nums[1])
        if rv is None:
            return '—'
        return 'PASS' if lo <= rv <= hi else 'FAIL'

    # ④ 规格是个纯数字（视为下限）？
    if len(nums) == 1 and nums[0] == spc.replace('%', '').strip():
        if rv is None:
            return '—'
        return 'PASS' if rv >= float(nums[0]) else 'FAIL'

    return '—'


def generate_coa_pdf(coa):
    """
    为 COA 实例生成 PDF 文件。

    参数:
        coa: Coa 模型实例

    返回:
        str: 生成的 PDF 相对路径（相对于 MEDIA_ROOT）
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, 'documents', 'coa')
    os.makedirs(output_dir, exist_ok=True)

    filename = f'{coa.doc_id}.pdf'
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── 样式定义 ──
    s_title = ParagraphStyle('COATitle', parent=styles['Title'],
        fontSize=18, textColor=BLUE, spaceAfter=2 * mm, alignment=TA_CENTER,
        fontName='Helvetica-Bold')
    s_company = ParagraphStyle('Company', parent=styles['Normal'],
        fontSize=11, textColor=DARK, fontName='Helvetica-Bold')
    s_info = ParagraphStyle('Info', parent=styles['Normal'],
        fontSize=7, textColor=GRAY, leading=9)
    s_section = ParagraphStyle('Section', parent=styles['Normal'],
        fontSize=8, textColor=BLUE, fontName='Helvetica-Bold',
        spaceBefore=3 * mm, spaceAfter=2 * mm)
    s_normal = ParagraphStyle('Normal8', parent=styles['Normal'],
        fontSize=8, textColor=DARK, leading=10)
    s_small = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=7, textColor=GRAY, leading=9)
    s_footer = ParagraphStyle('Footer', parent=styles['Normal'],
        fontSize=6.5, textColor=GRAY, leading=8, alignment=TA_CENTER)

    # ── Header ──
    header_data = [[
        Paragraph(f'<b>{coa.product_name}</b><br/>'
                  f'<font size="7" color="#64748b">'
                  f'Catalog: {coa.catalog_number} | CAS: {coa.cas_number}<br/>'
                  f'Lot: {coa.batch.lot_number}</font>', s_normal),
        Paragraph('<font size="18" color="#0ea5e9"><b>CERTIFICATE OF ANALYSIS</b></font>', s_title),
    ]]
    header_table = Table(header_data, colWidths=[70 * mm, 100 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width='100%', thickness=2, color=BLUE, spaceAfter=3 * mm))

    # ── Product Info Grid ──
    info_items = [
        ('Product Name', coa.product_name),
        ('Catalog No', coa.catalog_number),
        ('CAS Number', coa.cas_number),
        ('Lot/Batch No', coa.batch.lot_number),
        ('Molecular Formula', coa.molecular_formula),
        ('Molecular Weight', f'{coa.molecular_weight} g/mol' if coa.molecular_weight else ''),
        ('Storage Condition', coa.storage_condition),
        ('Manufacture Date', str(coa.batch.produced_at)),
        ('Retest Date', str(coa.batch.retest_at) if coa.batch.retest_at else ''),
    ]
    info_data = []
    for i in range(0, len(info_items), 2):
        row = []
        for j in range(2):
            if i + j < len(info_items):
                label, val = info_items[i + j]
                row.append(Paragraph(f'<b>{label}:</b> {val}', s_small))
            else:
                row.append('')
        info_data.append(row)

    info_table = Table(info_data, colWidths=[85 * mm, 85 * mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0, WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # ── QC Results Table ──
    elements.append(Paragraph('<font color="#0ea5e9"><b>QUALITY CONTROL RESULTS</b></font>', s_section))

    qc_header = ['Test Item', 'Specification', 'Result', 'Method', 'Verdict']
    qc_rows = [
        ['Appearance', coa.appearance_spec, coa.appearance_result, 'Visual', ''],
        ['Purity (HPLC)', coa.purity_spec, coa.purity_result, coa.purity_method or 'HPLC', ''],
        ['Water Content', coa.water_content_spec, coa.water_content_result, 'Karl Fischer', ''],
        ['Melting Point', '', coa.melting_point, 'USP <741>', ''],
        ['Specific Rotation', '', coa.specific_rotation, 'USP <781>', ''],
        ['Residual Solvents', '', coa.residual_solvents, 'GC', ''],
        ['Heavy Metals', '', coa.heavy_metals, 'USP <231>', ''],
        ['Identity (NMR)', 'Conforms', coa.nmr_result, 'NMR', ''],
        ['Identity (LC-MS)', f'MW: {coa.molecular_weight}', coa.lcms_result, 'LC-MS', ''],
    ]

    # ── Verdict 判定（A-055 / A-210，2026-11-27）──
    # 改前：这个循环**没有任何失败路径** —— 有结果就 PASS（无规格也 PASS），
    #   有规格时也从不比较数值（`spec.startswith('≤')` 直接 PASS，注释自认"简化判定"）。
    #   ⇒ 一张对外发布的合规证书，只要有人填了数就 9 行全 PASS。
    # 现在：只有**能真正判定**的才给 PASS/FAIL，判不了的写 '—'（Not evaluated）。
    for row in qc_rows:
        row[4] = _verdict(row[1], row[2])

    table_data = [qc_header] + qc_rows
    col_widths = [32 * mm, 35 * mm, 35 * mm, 30 * mm, 22 * mm]
    qc_table = Table(table_data, colWidths=col_widths)
    qc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(qc_table)
    elements.append(Spacer(1, 3 * mm))

    # ── Analytical Methods ──
    if coa.hplc_conditions or coa.lcms_conditions:
        elements.append(Paragraph('<font color="#0ea5e9"><b>ANALYTICAL METHODS</b></font>', s_section))
        methods_text = ''
        if coa.hplc_conditions:
            methods_text += f'<b>HPLC:</b> {coa.hplc_conditions}<br/>'
        if coa.lcms_conditions:
            methods_text += f'<b>LC-MS:</b> {coa.lcms_conditions}'
        elements.append(Paragraph(methods_text, s_small))
        elements.append(Spacer(1, 3 * mm))

    # ── Signatures ──
    elements.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceBefore=2 * mm, spaceAfter=2 * mm))

    sig_data = [[
        Paragraph(f'<b>QC Analyst:</b> {coa.qc_analyst or "_________"}<br/>'
                  f'Date: {str(coa.approved_at.date()) if coa.approved_at else "_________"}', s_small),
        Paragraph(f'<b>QA Approval:</b> {coa.qa_approval or "_________"}<br/>'
                  f'Date: {str(coa.approved_at.date()) if coa.approved_at else "_________"}', s_small),
    ]]
    sig_table = Table(sig_data, colWidths=[85 * mm, 85 * mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 3 * mm))

    # ── Footer ──
    elements.append(HRFlowable(width='100%', thickness=1, color=BORDER, spaceAfter=2 * mm))
    elements.append(Paragraph(
        f'{coa.doc_id} | Page 1 of 1 | '
        f'For research use only. Not for diagnostic or therapeutic use.',
        s_footer
    ))

    # ── Build PDF ──
    doc.build(elements)

    # 返回相对路径
    return f'documents/coa/{filename}'
