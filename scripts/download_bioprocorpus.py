import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
from huggingface_hub import hf_hub_download

target_dir = r'E:\scireagent-tencent\backend\data\bioprocorpus'
os.makedirs(target_dir, exist_ok=True)

files_to_download = [
    'Bio-protocol.json',
    'Protocol-exchange.json',
    'Protocol-io.json',
]

print('=== 下载 BioProCorpus 原始协议文件 ===')
for f in files_to_download:
    print(f'\nDownloading {f}...')
    path = hf_hub_download('bowenxian/BioProBench', f, repo_type='dataset', local_dir=target_dir, force_download=False)
    size = os.path.getsize(path)
    print(f'  Done: {os.path.basename(path)} ({size/1024/1024:.1f} MB)')

# Also download benchmark files for verification
benchmark_files = ['PQA.json', 'ERR.json', 'ORD.json', 'GEN.json']
for f in benchmark_files:
    print(f'\nDownloading {f}...')
    path = hf_hub_download('bowenxian/BioProBench', f, repo_type='dataset', local_dir=target_dir, force_download=False)
    size = os.path.getsize(path)
    print(f'  Done: {os.path.basename(path)} ({size/1024/1024:.1f} MB)')

print('\n=== 下载完成 ===')
print(f'保存目录: {target_dir}')
for f in os.listdir(target_dir):
    fp = os.path.join(target_dir, f)
    print(f'  {f}: {os.path.getsize(fp)/1024/1024:.1f} MB')
