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

# Step 2: Generate migrations
echo "[Step 2] Generating migrations..."
python manage.py makemigrations accounts knowledge commerce bridges transactions assets --name initial
echo "  ✓ Migrations generated"
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
