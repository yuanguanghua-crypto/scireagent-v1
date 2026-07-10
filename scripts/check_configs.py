import sys
sys.stdout.reconfigure(encoding='utf-8')
from datasets import load_dataset

configs = ['PQA', 'ERR', 'ORD', 'GEN']
for config in configs:
    try:
        ds = load_dataset('bowenxian/BioProBench', config, split='train', streaming=True)
        for i, ex in enumerate(ds):
            if i == 0:
                keys = list(ex.keys())
                print(f'Config {config}: keys={keys}')
                for k, v in ex.items():
                    if isinstance(v, str):
                        print(f'  {k}: {str(v)[:200]}')
                    elif isinstance(v, list):
                        print(f'  {k}: list[{len(v)}]')
                        if len(v) > 0 and isinstance(v[0], str):
                            print(f'    first: {v[0][:200]}')
                    else:
                        print(f'  {k}: {v}')
            break
        print()
    except Exception as e:
        print(f'Config {config}: Error - {e}')
