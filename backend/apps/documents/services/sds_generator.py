"""
SDS PDF 生成服务 — 使用 ReportLab
16 节 GHS 标准格式，5-7 页
"""
import os
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

BLUE = HexColor('#0ea5e9')
DARK_BG = HexColor('#0f172a')
DARK = HexColor('#1e293b')
GRAY = HexColor('#64748b')
LIGHT_GRAY = HexColor('#f1f5f9')
BORDER = HexColor('#e2e8f0')
RED = HexColor('#dc2626')
WHITE = HexColor('#ffffff')


def generate_sds_pdf(sds_revision):
    """
    为 SdsRevision 实例生成 SDS PDF。

    参数:
        sds_revision: SdsRevision 模型实例

    返回:
        str: 生成的 PDF 相对路径（相对于 MEDIA_ROOT）
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, 'documents', 'sds')
    os.makedirs(output_dir, exist_ok=True)

    product = sds_revision.product
    catalog = product.catalog_no or product.name
    filename = f'SDS-{catalog}-v{sds_revision.revision_no}.pdf'
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Styles ──
    s_section_header = ParagraphStyle('SectionHeader', parent=styles['Normal'],
        fontSize=9, textColor=white, fontName='Helvetica-Bold',
        spaceBefore=4 * mm, spaceAfter=2 * mm)
    s_sub = ParagraphStyle('SubLabel', parent=styles['Normal'],
        fontSize=8, textColor=DARK, fontName='Helvetica-Bold',
        spaceBefore=2 * mm, spaceAfter=1 * mm)
    s_body = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=8, textColor=HexColor('#334155'), leading=10)
    s_small = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=7, textColor=GRAY, leading=9)
    s_footer = ParagraphStyle('Footer', parent=styles['Normal'],
        fontSize=7, textColor=GRAY, leading=8)

    sd = sds_revision.get_section_data()

    # ── Header (Page 1 only) ──
    header_data = [[
        Paragraph(f'<font color="white" size="14"><b>SAFETY DATA SHEET</b></font><br/>'
                  f'<font color="#94a3b8" size="6">According to OSHA HCS 2012 (29 CFR 1910.1200) &amp; GHS Rev. 9</font>',
                  styles['Normal']),
        Paragraph(f'<font size="10"><b>{product.name}</b></font><br/>'
                  f'<font size="7" color="#94a3b8">CAS: {product.cas or "N/A"} | '
                  f'SD-{catalog}-v{sds_revision.revision_no}</font>',
                  ParagraphStyle('r', parent=styles['Normal'], alignment=TA_RIGHT)),
    ]]
    ht = Table(header_data, colWidths=[100 * mm, 70 * mm])
    ht.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK_BG),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, 0), 10),
        ('RIGHTPADDING', (-1, 0), (-1, 0), 10),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    elements.append(ht)
    elements.append(Spacer(1, 4 * mm))

    # ── Helper: section header ──
    def add_section(num, title):
        elements.append(Paragraph(
            f'<font color="white"><b>SECTION {num}: {title.upper()}</b></font>',
            s_section_header
        ))
        # Blue bar behind the text
        # We use a colored table row as background
        elements[-1] = _colored_section_header(num, title)

    def _colored_section_header(num, title):
        t = Table(
            [[Paragraph(f'<font color="white"><b>SECTION {num}: {title.upper()}</b></font>',
                        s_section_header)]],
            colWidths=[170 * mm]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BLUE),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('ROUNDEDCORNERS', [3, 3, 3, 3]),
        ]))
        return t

    def add_table(rows, col_widths=None):
        if not rows:
            return
        if not col_widths:
            col_widths = [50 * mm, 120 * mm]
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDER),
        ]))
        elements.append(t)

    def add_kv_table(data_dict):
        """key-value 格式的表格"""
        rows = [[Paragraph(f'<b>{k}</b>', s_small), Paragraph(str(v), s_small)]
                for k, v in data_dict.items()]
        if rows:
            add_table(rows)

    def add_text(text):
        elements.append(Paragraph(text, s_body))

    def add_sub(text):
        elements.append(Paragraph(f'<b>{text}</b>', s_sub))

    # ════════════════════════════════════════════════════
    # SECTION 1: Identification
    # ════════════════════════════════════════════════════
    add_section(1, 'Identification')
    s1 = sd.get('section_1', {})
    supplier = s1.get('supplier', {})
    add_kv_table({
        'Product Name': product.name,
        'Catalog Number': product.catalog_no or '',
        'Synonyms': s1.get('synonyms', ''),
        'CAS Number': product.cas or '',
        'Recommended Use': s1.get('recommended_use', 'Laboratory research reagent'),
        'Restrictions on Use': s1.get('restrictions', ''),
    })
    add_sub('Supplier')
    add_kv_table({
        'Company': supplier.get('company', 'SciReagent'),
        'Address': supplier.get('address', ''),
        'Telephone': supplier.get('telephone', ''),
        'Email': supplier.get('email', ''),
        'Emergency Phone (24h)': supplier.get('emergency_phone', ''),
    })
    elements.append(Spacer(1, 2 * mm))

    # ════════════════════════════════════════════════════
    # SECTION 2: Hazards Identification
    # ════════════════════════════════════════════════════
    add_section(2, 'Hazards Identification')
    s2 = sd.get('section_2', {})
    signal_word = s2.get('signal_word', sds_revision.signal_word or 'Warning')
    pictograms = s2.get('pictograms', sds_revision.get_pictograms())
    h_codes = s2.get('hazard_codes', sds_revision.get_hazard_codes())
    p_codes = s2.get('precaution_codes', sds_revision.get_precaution_codes())

    # Signal word box
    sw_data = [[Paragraph(
        f'<font color="#dc2626" size="16"><b>⚠ {signal_word.upper()}</b></font>',
        ParagraphStyle('sw', alignment=TA_CENTER, spaceAfter=2 * mm)
    )]]
    if pictograms:
        pg_text = '   '.join([f'<font color="#dc2626"><b>{p}</b></font>' for p in pictograms])
        sw_data.append([Paragraph(pg_text, ParagraphStyle('pg', alignment=TA_CENTER))])
    sw_table = Table(sw_data, colWidths=[170 * mm])
    sw_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 2, RED),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(sw_table)
    elements.append(Spacer(1, 2 * mm))

    if h_codes:
        add_sub('Hazard Statements (H-Codes)')
        for code in h_codes:
            add_text(f'<font color="#0ea5e9"><b>{code}</b></font>')

    if p_codes:
        add_sub('Precautionary Statements')
        for code in p_codes:
            add_text(f'<font color="#0ea5e9"><b>{code}</b></font>')

    other = s2.get('other_hazards', '')
    if other:
        add_sub('Other Hazards')
        add_text(other)
    elements.append(Spacer(1, 2 * mm))

    # ════════════════════════════════════════════════════
    # SECTION 3: Composition
    # ════════════════════════════════════════════════════
    add_section(3, 'Composition / Information on Ingredients')
    s3 = sd.get('section_3', {})
    comp_rows = [[
        Paragraph('<b>Chemical Name</b>', s_small),
        Paragraph('<b>CAS No.</b>', s_small),
        Paragraph('<b>Concentration</b>', s_small),
        Paragraph('<b>GHS Classification</b>', s_small),
    ]]
    for item in s3.get('composition', []):
        comp_rows.append([
            Paragraph(item.get('name', ''), s_small),
            Paragraph(product.cas or '', s_small),
            Paragraph(item.get('concentration', ''), s_small),
            Paragraph(item.get('classification', ''), s_small),
        ])
    if comp_rows:
        ct = Table(comp_rows, colWidths=[45 * mm, 25 * mm, 30 * mm, 70 * mm])
        ct.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(ct)
    note = s3.get('note', '')
    if note:
        elements.append(Paragraph(f'<i>{note}</i>', s_small))

    # ════════════════════════════════════════════════════
    # Sections 4-8 (text-based)
    # ════════════════════════════════════════════════════
    _section_texts = {
        4: ('First-Aid Measures', [
            ('Inhalation', 'inhalation'), ('Skin Contact', 'skin_contact'),
            ('Eye Contact', 'eye_contact'), ('Ingestion', 'ingestion'),
            ('Most Important Symptoms', 'symptoms'), ('Notes to Physician', 'physician_notes'),
        ]),
        5: ('Fire-Fighting Measures', [
            ('Suitable Extinguishing Media', 'suitable_media'),
            ('Unsuitable Extinguishing Media', 'unsuitable_media'),
            ('Specific Hazards', 'hazards'),
            ('Special Protective Equipment', 'firefighter_equipment'),
        ]),
        6: ('Accidental Release Measures', [
            ('Personal Precautions', 'personal'),
            ('Environmental Precautions', 'environmental'),
            ('Methods for Containment & Cleanup', 'cleanup'),
        ]),
        7: ('Handling and Storage', [
            ('Handling', 'handling'), ('Storage', 'storage'), ('Specific Use', 'specific_use'),
        ]),
    }
    for sec_num, (sec_title, fields) in _section_texts.items():
        add_section(sec_num, sec_title)
        sec_data = sd.get(f'section_{sec_num}', {})
        for label, key in fields:
            val = sec_data.get(key, '')
            if val:
                add_sub(label)
                add_text(val)

    # ════════════════════════════════════════════════════
    # SECTION 8: Exposure Controls
    # ════════════════════════════════════════════════════
    add_section(8, 'Exposure Controls / Personal Protection')
    s8 = sd.get('section_8', {})
    for k in ['exposure_limits', 'engineering_controls', 'hygiene']:
        v = s8.get(k, '')
        if v:
            label = k.replace('_', ' ').title()
            add_sub(label)
            add_text(v)
    ppe = s8.get('ppe', {})
    if ppe:
        add_sub('Personal Protective Equipment (PPE)')
        add_kv_table({k.replace('_', ' ').title(): v for k, v in ppe.items()})

    # ════════════════════════════════════════════════════
    # SECTION 9: Physical Properties
    # ════════════════════════════════════════════════════
    add_section(9, 'Physical and Chemical Properties')
    s9 = sd.get('section_9', {})
    prop_labels = [
        ('appearance', 'Appearance'), ('odor', 'Odor'), ('odor_threshold', 'Odor Threshold'),
        ('ph', 'pH'), ('melting_point', 'Melting Point'), ('boiling_point', 'Boiling Point'),
        ('flash_point', 'Flash Point'), ('evaporation_rate', 'Evaporation Rate'),
        ('flammability', 'Flammability'), ('vapor_pressure', 'Vapor Pressure'),
        ('vapor_density', 'Vapor Density'), ('relative_density', 'Relative Density'),
        ('solubility_water', 'Solubility in Water'), ('solubility_dmso', 'Solubility (DMSO)'),
        ('partition_coefficient', 'Partition Coefficient'),
        ('auto_ignition', 'Auto-ignition Temperature'),
        ('decomposition_temp', 'Decomposition Temperature'),
        ('viscosity', 'Viscosity'), ('explosive', 'Explosive Properties'),
        ('oxidizing', 'Oxidizing Properties'), ('exact_mass', 'Exact Mass'),
    ]
    prop_data = []
    for key, label in prop_labels:
        val = s9.get(key, 'Not available')
        if val:
            prop_data.append([
                Paragraph(f'<b>{label}</b>', s_small),
                Paragraph(str(val), s_small),
            ])
    if prop_data:
        add_table(prop_data)

    # ════════════════════════════════════════════════════
    # SECTION 10: Stability and Reactivity
    # ════════════════════════════════════════════════════
    add_section(10, 'Stability and Reactivity')
    s10 = sd.get('section_10', {})
    add_kv_table({k.replace('_', ' ').title(): v for k, v in s10.items() if v})

    # ════════════════════════════════════════════════════
    # SECTION 11: Toxicological Information
    # ════════════════════════════════════════════════════
    add_section(11, 'Toxicological Information')
    s11 = sd.get('section_11', {})
    at = s11.get('acute_toxicity', {})
    if at:
        add_sub('Acute Toxicity')
        add_kv_table({k.replace('_', ' ').title(): v for k, v in at.items() if v})
    for key in ['skin_irritation', 'eye_irritation', 'sensitization', 'mutagenicity',
                'carcinogenicity', 'reproductive_toxicity', 'stot_single', 'stot_repeated', 'aspiration']:
        val = s11.get(key, '')
        if val:
            label = key.replace('_', ' ').title()
            add_sub(label)
            add_text(val)

    # ════════════════════════════════════════════════════
    # SECTION 12: Ecological Information
    # ════════════════════════════════════════════════════
    add_section(12, 'Ecological Information')
    s12 = sd.get('section_12', {})
    add_kv_table({k.replace('_', ' ').title(): v for k, v in s12.items() if v})

    # ════════════════════════════════════════════════════
    # SECTION 13: Disposal Considerations
    # ════════════════════════════════════════════════════
    add_section(13, 'Disposal Considerations')
    s13 = sd.get('section_13', {})
    for k in ['waste', 'packaging', 'rcra']:
        v = s13.get(k, '')
        if v:
            add_sub(k.replace('_', ' ').title())
            add_text(v)

    # ════════════════════════════════════════════════════
    # SECTION 14: Transport Information
    # ════════════════════════════════════════════════════
    add_section(14, 'Transport Information')
    s14 = sd.get('section_14', {})
    add_kv_table({
        'DOT (USA)': s14.get('dot', 'Not regulated'),
        'IMDG (Sea)': s14.get('imdg', 'Not regulated'),
        'IATA (Air)': s14.get('iata', 'Not regulated'),
        'UN Number': s14.get('un_number', 'None'),
        'UN Proper Shipping Name': s14.get('shipping_name', 'Not applicable'),
        'Transport Hazard Class': s14.get('hazard_class', 'None'),
        'Packing Group': s14.get('packing_group', 'None'),
        'Special Precautions': s14.get('special_precautions', ''),
    })

    # ════════════════════════════════════════════════════
    # SECTION 15: Regulatory Information
    # ════════════════════════════════════════════════════
    add_section(15, 'Regulatory Information')
    s15 = sd.get('section_15', {})
    add_kv_table({k.upper(): v for k, v in s15.items() if v})

    # ════════════════════════════════════════════════════
    # SECTION 16: Other Information
    # ════════════════════════════════════════════════════
    add_section(16, 'Other Information')
    s16 = sd.get('section_16', {})
    add_kv_table({
        'Revision Date': sds_revision.revised_at or '',
        'Revision Number': f'{sds_revision.revision_no}.0',
        'Supersedes': s16.get('supersedes', 'New document'),
        'Prepared By': s16.get('prepared_by', ''),
    })
    refs = s16.get('references', [])
    if refs:
        add_sub('References')
        for r in refs:
            add_text(f'• {r}')

    abbr = s16.get('abbreviations', {})
    if abbr:
        add_sub('Abbreviations')
        add_kv_table({k: v for k, v in abbr.items()})

    disc = s16.get('disclaimer', '')
    if disc:
        elements.append(Spacer(1, 3 * mm))
        add_text(f'<i>{disc}</i>')

    # ── Footer ──
    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=2 * mm))
    elements.append(Paragraph(
        f'END OF SAFETY DATA SHEET | SD-{catalog}-v{sds_revision.revision_no} | '
        f'SciReagent — Safety Data Sheet',
        s_footer
    ))

    # ── Build ──
    doc.build(elements)
    return f'documents/sds/{filename}'
