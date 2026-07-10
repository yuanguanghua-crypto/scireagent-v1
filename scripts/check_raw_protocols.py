import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
from huggingface_hub import hf_hub_download

# Download and check Bio-protocol.json from bowenxian/BioProBench
path = hf_hub_download('bowenxian/BioProBench', 'Bio-protocol.json', repo_type='dataset')
size = os.path.getsize(path)
print(f'Downloaded to: {path}')
print(f'File size: {size} bytes ({size/1024/1024:.1f} MB)')

# Read the structure without loading the whole file
with open(path, 'r', encoding='utf-8') as f:
    # Just read first 5000 chars to see structure
    chunk = f.read(5000)
    print(f'\nFirst 5000 chars:')
    print(chunk)
