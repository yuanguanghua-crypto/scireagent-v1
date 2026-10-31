"""轮询本次推送触发的 GitHub Actions，直到完成或超时。

用法：python scripts/_watch_ci.py <head_sha> [--max-min 50]
只读 GitHub 公开 API（每次间隔 120s，避免匿名 60 次/小时的限额）。
"""
import json
import sys
import time
import urllib.request
import urllib.error

REPO = 'yuanguanghua-crypto/scireagent-v1'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HDR = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ci-watch'}


def api(path):
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}{path}', headers=HDR)
    with OP.open(req, timeout=25) as r:
        return json.load(r)


def main():
    sha = sys.argv[1]
    max_min = 50
    if '--max-min' in sys.argv:
        max_min = int(sys.argv[sys.argv.index('--max-min') + 1])

    run = None
    deadline = time.time() + max_min * 60
    while time.time() < deadline:
        runs = api('/actions/runs?per_page=10').get('workflow_runs', [])
        run = next((w for w in runs if w['head_sha'].startswith(sha[:10])), None)
        if not run:
            print(f'[watch] 尚未找到 sha={sha[:10]} 的 run，等 60s')
            time.sleep(60)
            continue
        if run['status'] == 'completed':
            break
        print(f"[watch] {run['status']}  {run['created_at']}", flush=True)
        time.sleep(120)

    if not run:
        print('[watch] TIMEOUT 没找到对应的 run')
        return 2

    print(f"\n=== RUN {run['id']}  status={run['status']}  conclusion={run['conclusion']} ===")
    print(run['html_url'])
    try:
        jobs = api(f"/actions/runs/{run['id']}/jobs").get('jobs', [])
    except Exception as e:
        print('取 job 明细失败：', e)
        return 1

    bad = []
    for j in jobs:
        mark = {'success': 'OK  ', 'failure': 'FAIL', 'skipped': 'skip',
                'cancelled': 'cncl', None: '...'}.get(j['conclusion'], j['conclusion'])
        print(f"  {mark}  {j['name']}")
        if j['conclusion'] == 'failure':
            bad.append(j)

    if bad:
        print('\n=== 失败 job 的失败步骤 ===')
        for j in bad:
            for s in j.get('steps', []):
                if s.get('conclusion') == 'failure':
                    print(f"  [{j['name']}] step: {s['name']}")
        return 1
    print('\n全部 job 通过' if run['conclusion'] == 'success' else f"\n结论：{run['conclusion']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
