import zipfile, sys, glob, os, json, re
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    body = root.find(W + 'body')
    out = []
    def walk(elem):
        for child in elem:
            tag = child.tag
            if tag == W + 'p':
                out.append(''.join(t.text or '' for t in child.iter(W + 't')))
            elif tag == W + 'tbl':
                for row in child.iter(W + 'tr'):
                    cells = [''.join(t.text or '' for t in cell.iter(W + 'tc')) for cell in row.iter(W + 'tc')]
                    out.append(' | '.join(cells))
            else:
                walk(child)
    walk(body)
    return out

def parse_usage(paras):
    cands = []
    for line in paras:
        low = line.lower()
        if ('used' in low or 'is a ' in low or 'application' in low or 'useful' in low) and len(line) > 40:
            cands.append(line.strip())
    cands.sort(key=lambda s: (0 if 'used' in s.lower() else 1, -len(s)))
    return cands[0] if cands else ''

def parse_field(paras, label):
    for line in paras:
        if line.strip().lower().startswith(label.lower()):
            m = re.split(r'[:：]', line, 1)
            if len(m) == 2:
                return m[1].strip()
    return ''

folder = sys.argv[1]
files = sorted(glob.glob(os.path.join(folder, '*.docx')))
records = []
no_usage = []
for p in files:
    try:
        paras = docx_text(p)
    except Exception as e:
        print(f"ERR {os.path.basename(p)}: {e}", file=sys.stderr)
        continue
    catalog = parse_field(paras, 'Catalog Number')
    name = paras[0].strip() if paras else ''
    cas = parse_field(paras, 'CAS Number')
    usage = parse_usage(paras)
    rec = {'file': os.path.basename(p), 'catalog': catalog, 'name': name, 'cas': cas, 'usage': usage}
    records.append(rec)
    if not usage:
        no_usage.append(catalog or os.path.basename(p))

print(f"Total docx: {len(files)}")
print(f"Parsed records: {len(records)}")
print(f"With catalog: {sum(1 for r in records if r['catalog'])}")
print(f"With CAS: {sum(1 for r in records if r['cas'])}")
print(f"With usage statement: {sum(1 for r in records if r['usage'])}")
print(f"Missing usage: {len(no_usage)} -> {no_usage[:20]}")
print("\n=== SAMPLE (first 8) ===")
for r in records[:8]:
    print(f"{r['catalog']} | {r['name']} | CAS={r['cas']}")
    print(f"   usage: {r['usage'][:200]}")

with open('docx_products.json', 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=1)
print(f"\nSaved docx_products.json ({len(records)} records)")
