#!/bin/bash
# SciReagent Backend - T05 Verification Script
# Usage: bash scripts/run_tests.sh
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo "  T05: 路由集成 + 端点测试 + API 验证"
echo "========================================"
echo ""

export DB_ENGINE=sqlite
export DJANGO_SETTINGS_MODULE=config.settings.development

# Step 1: Django system check
echo "[Step 1] Running Django system check..."
python manage.py check
echo "  ✓ Django check passed"
echo ""

# Step 2: 校验迁移图（**只读，不生成**）
# ⚠️ 2026-10-28 改：原文是
#      python manage.py makemigrations accounts knowledge commerce ... --name initial
#    这条在 `DB_ENGINE=sqlite`（本脚本第 13 行）下会给每个 app 生成
#    「RemoveField search_vector + RemoveIndex *_search_gin/_trgm」的破坏性迁移
#    —— 因为 sqlite 分支的模型里没有 PG 专属字段。一旦有人跑了本脚本并把
#    生成的文件提交上去，生产的全文检索（5 列 / 5 GIN / 4 trgm / 5 触发器）
#    会被 migrate 真删掉，且搜索只是"返回空"不报错。
#    迁移早已齐备（90 个文件 / 10 个 app），这一步本来就不该再生成任何东西。
#    现在改为只读校验：`migrate --plan` 会构建完整迁移图，跨 app 依赖断层
#    （`NodeNotFoundError`）在这步就会暴露 —— 而这正是 `manage.py check`
#    查不出、当年 documents/0006 踩过的那类坑。
echo "[Step 2] Checking migration graph (read-only)..."
python manage.py migrate --plan > /dev/null
echo "  ✓ Migration graph OK"
echo ""

# Step 3: Apply migrations
echo "[Step 3] Applying migrations..."
python manage.py migrate
echo "  ✓ Migrations applied"
echo ""

# Step 4: Verify URL endpoints
echo "[Step 4] Verifying URL endpoints..."
python scripts/verify_urls.py
echo ""

# Step 5: Run tests
echo "[Step 5] Running tests..."
python -m pytest apps/ -v --tb=short
echo ""

echo "========================================"
echo "  T05 Verification Complete!"
echo "========================================"
