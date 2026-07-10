import sys
sys.stdout.reconfigure(encoding='utf-8')

from datasets import load_dataset, get_dataset_split_names

# Check splits
splits = get_dataset_split_names('BioProBench/BioProBench')
print('Splits:', splits)

# Load the full dataset info without streaming to see all data
ds = load_dataset('BioProBench/BioProBench', split='train', streaming=True)
count = 0
for example in ds:
    count += 1
    if count <= 5:
        t = example.get('type', 'unknown')
        print(f'Sample {count}: type={t}, id={example["id"]}')
        ctx = example.get('context', '')
        if ctx:
            print(f'  context: {str(ctx)[:200]}...')
        # Check if there's a full text field
        for k, v in example.items():
            if isinstance(v, str) and len(v) > 500 and k != 'context':
                print(f'  {k}: {v[:200]}...')
        print()
    if count >= 1000:
        break

print(f'Total samples scanned: {count}')

# Now also check the other datasets mentioned
print('\n=== Checking bowenxian/BioProBench ===')
try:
    other_splits = get_dataset_split_names('bowenxian/BioProBench')
    print('Splits:', other_splits)
except Exception as e:
    print(f'Error: {e}')

print('\nDone!')
