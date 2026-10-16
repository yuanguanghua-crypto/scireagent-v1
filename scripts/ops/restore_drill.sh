#!/bin/bash
# 恢复演练 — 验证备份可恢复（DEV-Ops 一键脚本）
# 用法: bash /home/admin/scireagent/scripts/restore_drill.sh
set -e
BACKUP_FILE=$(ls -t /home/admin/scireagent/_backups/scireagent_daily_*.sql.gz 2>/dev/null | head -1)
if [ -z "$BACKUP_FILE" ]; then echo "FAIL: no backup found"; exit 1; fi
echo "[$(date '+%H:%M:%S')] 演练开始 — 备份文件: $BACKUP_FILE ($(stat -c %s "$BACKUP_FILE")B)"

# 基线：当前生产数据行数
BASELINE_PRODUCT=$(docker exec scireagent-db-1 psql -U scireagent -d scireagent -tAc "SELECT count(*) FROM product")
BASELINE_SKU=$(docker exec scireagent-db-1 psql -U scireagent -d scireagent -tAc "SELECT count(*) FROM sku")
echo "[$(date '+%H:%M:%S')] 生产基线: product=$BASELINE_PRODUCT sku=$BASELINE_SKU"

# ① 起临时 PG 容器
docker rm -f restore-test 2>/dev/null || true
docker run --rm -d --name restore-test -e POSTGRES_PASSWORD=drill123 postgres:16-alpine
echo "[$(date '+%H:%M:%S')] 临时 PG 容器已启动"
sleep 3

# ② 等待 PG 就绪
for i in $(seq 1 10); do
    docker exec restore-test pg_isready -U postgres > /dev/null 2>&1 && break
    sleep 1
done

# ③ 恢复备份
gunzip -c "$BACKUP_FILE" | docker exec -i restore-test psql -U postgres -d postgres 2>&1 | tail -3
echo "[$(date '+%H:%M:%S')] SQL 恢复完成"

# ④ 验证关键表行数
R_PRODUCT=$(docker exec restore-test psql -U postgres -d postgres -tAc "SELECT count(*) FROM product" 2>/dev/null || echo "ERR")
R_SKU=$(docker exec restore-test psql -U postgres -d postgres -tAc "SELECT count(*) FROM sku" 2>/dev/null || echo "ERR")
R_ORDER=$(docker exec restore-test psql -U postgres -d postgres -tAc "SELECT count(*) FROM \"order\"" 2>/dev/null || echo "ERR")
echo "[$(date '+%H:%M:%S')] 恢复后: product=$R_PRODUCT sku=$R_SKU order=$R_ORDER"

# ⑤ 比对
PASS=true
if [ "$R_PRODUCT" != "$BASELINE_PRODUCT" ]; then PASS=false; echo "  ⚠ product 不匹配: prod=$BASELINE_PRODUCT vs restore=$R_PRODUCT"; fi
if [ "$R_SKU" != "$BASELINE_SKU" ]; then PASS=false; echo "  ⚠ sku 不匹配: prod=$BASELINE_SKU vs restore=$R_SKU"; fi

if [ "$PASS" = true ]; then
    echo "[$(date '+%H:%M:%S')] ✅ 恢复演练 PASS — 备份可恢复，行数一致"
else
    echo "[$(date '+%H:%M:%S')] ❌ 恢复演练 FAIL — 行数不匹配"
fi

# ⑥ 清理
docker stop restore-test > /dev/null 2>&1
docker rm restore-test > /dev/null 2>&1
echo "[$(date '+%H:%M:%S')] 临时容器已销毁，演练完毕"
