#!/usr/bin/env python3
"""生产监控探针 — DEV-5（QQ SMTP 告警版）
检查：HTTPS uptime · 证书到期(<30d) · 磁盘(>85%) · Docker 容器 · DB 连通
告警：QQ SMTP 邮件 + alert.log（状态变化时才发，不轰炸）
cron: */5 * * * *
"""
import subprocess, os, json, datetime, ssl, socket, smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import timezone

SITE = 'scireagent.com'
SITE_URL = f'https://{SITE}'
ALERT_DIR = '/home/admin/scireagent/_alerts'
ALERT_LOG = os.path.join(ALERT_DIR, 'alert.log')
STATE_FILE = os.path.join(ALERT_DIR, 'monitor_state.json')
os.makedirs(ALERT_DIR, exist_ok=True)

SMTP_SERVER = 'smtp.qq.com'
SMTP_PORT = 465
SMTP_USER = '55248125@qq.com'
SMTP_AUTH = 'geftlfggrqqncbbh'
ALERT_EMAIL = '55248125@qq.com'

def send_alert_email(subject, body):
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = SMTP_USER
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = Header(subject, 'utf-8')
        s = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        s.login(SMTP_USER, SMTP_AUTH)
        s.sendmail(SMTP_USER, [ALERT_EMAIL], msg.as_string())
        s.quit()
        return True
    except Exception:
        return False

def run(cmd, timeout=30, env=None):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            env=({**os.environ, **env} if env else None),
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return -1, '', str(e)

checks, alerts = {}, []

# ★ 2026-10-18 安全修正：生产 nginx Basic 口令不再硬编码在仓库里（原为真实可用的生产口令）。
#   改为环境变量注入（沿用项目既有命名 E2E_BASIC_USER / E2E_BASIC_PASS）。
#   来源：服务器 deploy/CREDENTIALS.txt（权限 600，不在仓库内）。
#   缺凭据 ⇒ 该项标记"未配置"并告警，**不**用任何默认口令硬探（否则等于把口令又写回仓库）。
_BASIC_USER = os.getenv('E2E_BASIC_USER', '')
_BASIC_PASS = os.getenv('E2E_BASIC_PASS', '')
if _BASIC_USER and _BASIC_PASS:
    # 用 urllib 直连（**不走 shell**）：口令放请求头，**不落命令行/进程列表**；
    # 也不用 shell 变量展开（Windows 下 shell=True 是 cmd.exe，`$VAR` 不展开 ⇒ 实测 401）。
    try:
        import base64
        import urllib.request
        _tok = base64.b64encode(f'{_BASIC_USER}:{_BASIC_PASS}'.encode()).decode()
        _req = urllib.request.Request(
            f'{SITE_URL}/api/v1/products/',
            headers={'Authorization': f'Basic {_tok}'},
        )
        with urllib.request.urlopen(_req, timeout=15, context=ssl._create_unverified_context()) as _resp:
            out = str(_resp.status)
        rc = 0
    except urllib.error.HTTPError as e:
        out, rc = str(e.code), 1
    except Exception as e:
        out, rc = str(e)[:120], 1
    checks['https_uptime'] = {'rc': rc, 'http_code': out}
    if rc != 0 or out != '200':
        alerts.append(f'HTTPS uptime FAIL: rc={rc} http={out}')
else:
    checks['https_uptime'] = {'rc': -1, 'http_code': '未配置凭据'}
    alerts.append(
        'HTTPS uptime SKIPPED: 未设置 E2E_BASIC_USER/E2E_BASIC_PASS（见 deploy/CREDENTIALS.txt）'
    )

try:
    ctx = ssl.create_default_context()
    conn = ctx.wrap_socket(socket.socket(), server_hostname=SITE)
    conn.connect((SITE, 443))
    cert = conn.getpeercert()
    conn.close()
    not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
    days_left = (not_after - datetime.datetime.now(timezone.utc)).days
    checks['cert_days_left'] = days_left
    if days_left < 30:
        alerts.append(f'Certificate expires in {days_left} days')
except Exception as e:
    checks['cert_days_left'] = 'FAIL'
    alerts.append(f'Certificate check FAIL: {e}')

rc, out, _ = run("df / | tail -1 | awk '{print $5}' | tr -d '%'")
if rc == 0 and out.isdigit():
    checks['disk_pct'] = int(out)
    if checks['disk_pct'] > 85:
        alerts.append(f'Disk usage {checks["disk_pct"]}%')

rc, out, _ = run('docker ps --format "{{.Names}} {{.Status}}"')
checks['containers'] = {}
for c in ['scireagent-backend-1', 'scireagent-db-1', 'scireagent-nginx-1']:
    ok = c in out and 'Up' in out
    checks['containers'][c] = ok
    if not ok: alerts.append(f'Container {c} not running')

rc, out, _ = run('docker exec scireagent-db-1 psql -U scireagent -d scireagent -tAc "SELECT 1"')
checks['db_ok'] = (rc == 0 and out == '1')
if not checks['db_ok']: alerts.append('DB check FAIL')

state = {}
if os.path.exists(STATE_FILE):
    try: state = json.load(open(STATE_FILE))
    except: pass
prev_alerting = state.get('alerting', False)
now_alerting = len(alerts) > 0
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

if now_alerting:
    msg = f'[{ts}] ALERT ({len(alerts)} issue(s))\n' + '\n'.join(f'  ⚠ {a}' for a in alerts)
    with open(ALERT_LOG, 'a') as f: f.write(msg + '\n\n')
    if not prev_alerting:
        ok = send_alert_email(f'[SciReAgent] {len(alerts)} issue(s) detected', msg)
        with open(ALERT_LOG, 'a') as f:
            f.write(f'[email] {"sent" if ok else "FAILED"}\n')
    print(msg)
elif prev_alerting:
    rec = f'[{ts}] RECOVERED — all checks passed'
    with open(ALERT_LOG, 'a') as f: f.write(rec + '\n')
    send_alert_email('[SciReAgent] Recovered', rec)
    print(rec)
else:
    print(f'[{ts}] OK — all checks passed')

state.update({'alerting': now_alerting, 'last_check': ts, 'last_alerts': alerts})
with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)

# ★ Healthchecks.io 死人开关：每次监控跑完 ping 一次
# 服务器挂了 → 没收到 ping → Healthchecks.io 自动发邮件
try:
    run('curl -s --max-time 10 https://hc-ping.com/d3ff13a5-2754-4cbd-a219-b9564867191a > /dev/null 2>&1')
except Exception:
    pass
