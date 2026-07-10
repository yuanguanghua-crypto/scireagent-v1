import sys, json
sys.stdout.reconfigure(encoding='utf-8')

base = r'E:\scireagent-tencent\backend\data\bioprocorpus'

for fname in ['Bio-protocol.json', 'Protocol-exchange.json', 'Protocol-io.json']:
    path = f'{base}/{fname}'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    n = len(data) if isinstance(data, list) else 1
    print(f'{fname}: {n} protocols')

print()
for fname in ['PQA.json', 'ERR.json', 'ORD.json', 'GEN.json']:
    path = f'{base}/{fname}'
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    n = len(data) if isinstance(data, list) else 1
    print(f'{fname}: {n} examples')
