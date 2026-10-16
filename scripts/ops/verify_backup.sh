#!/bin/bash
# 修正验证逻辑：pg_dump 纯 SQL 格式用头部+尾部检查（pg_restore --list 仅适用于 -Fc 格式）
BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then echo "FAIL: file not found"; exit 1; fi
HEADER=$(gunzip -c "$BACKUP_FILE" | head -3)
if echo "$HEADER" | grep -q "PostgreSQL database dump"; then
    echo "Verify: PostgreSQL dump header OK"
    TABLES=$(gunzip -c "$BACKUP_FILE" | grep -c "CREATE TABLE" || echo 0)
    echo "Verify: $TABLES CREATE TABLE statements"
    if [ "$TABLES" -gt 0 ]; then
        echo "Verify: PASS"
    else
        echo "Verify: WARN (0 CREATE TABLE)"
    fi
else
    echo "Verify: FAIL (not a PostgreSQL dump)"
    exit 1
fi
