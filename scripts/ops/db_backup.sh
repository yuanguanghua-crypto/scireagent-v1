#!/bin/bash
# DB 自动备份 — DEV-3（QQ SMTP 告警版）
# cron: 0 3 * * * /home/admin/scireagent/scripts/db_backup.sh >> /home/admin/scireagent/_backups/backup.log 2>&1
BACKUP_DIR="/home/admin/scireagent/_backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/scireagent_daily_$TIMESTAMP.sql.gz"
RETENTION_DAYS=30
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# 告警函数（QQ SMTP）
send_alert() {
    python3 -c "
import smtplib
from email.mime.text import MIMEText
from email.header import Header
m = MIMEText('''$2''', 'plain', 'utf-8')
m['From'] = '55248125@qq.com'
m['To'] = '55248125@qq.com'
m['Subject'] = Header('$1', 'utf-8')
s = smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=15)
s.login('55248125@qq.com', 'geftlfggrqqncbbh')
s.sendmail('55248125@qq.com', ['55248125@qq.com'], m.as_string())
s.quit()
" 2>/dev/null
}

# ① pg_dump
docker exec scireagent-db-1 pg_dump -U scireagent -d scireagent --no-owner --no-privileges | gzip > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "$LOG_PREFIX FAIL: backup file is empty"
    send_alert "[SciReAgent] DB Backup FAILED" "Backup file is empty: $BACKUP_FILE"
    exit 1
fi

SIZE=$(stat -c %s "$BACKUP_FILE")
echo "$LOG_PREFIX Backup created: $BACKUP_FILE (${SIZE}B)"

# ② 验证（SQL 头部 + 表数）
HEADER=$(gunzip -c "$BACKUP_FILE" | head -3)
TABLES=$(gunzip -c "$BACKUP_FILE" | grep -c "CREATE TABLE" 2>/dev/null || echo 0)
if echo "$HEADER" | grep -q "PostgreSQL database dump" && [ "$TABLES" -gt 0 ]; then
    echo "$LOG_PREFIX Verify: PASS ($TABLES CREATE TABLE)"
else
    echo "$LOG_PREFIX FAIL: verification failed"
    send_alert "[SciReAgent] DB Backup Verify FAILED" "Tables: $TABLES, File: $BACKUP_FILE"
    exit 1
fi

# ③ 保留策略
DELETED=$(find "$BACKUP_DIR" -name "scireagent_daily_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "$LOG_PREFIX Retention: deleted $DELETED old (>$RETENTION_DAYS days)"

# ④ 磁盘安全
TOTAL=$(du -s "$BACKUP_DIR" | cut -f1)
if [ "$TOTAL" -gt 5242880 ]; then
    OLDEST=$(ls -t "$BACKUP_DIR"/scireagent_daily_*.sql.gz 2>/dev/null | tail -1)
    [ -n "$OLDEST" ] && rm -f "$OLDEST" && echo "$LOG_PREFIX Disk safety: removed $OLDEST"
fi

echo "$LOG_PREFIX Done"
