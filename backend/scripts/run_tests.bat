@echo off
REM SciReagent Backend - T05 Verification Script (Windows)
REM Usage: scripts\run_tests.bat

cd /d "%~dp0\.."

echo ========================================
echo   T05: Routing + Endpoint + API Verify
echo ========================================
echo.

set DB_ENGINE=sqlite
set DJANGO_SETTINGS_MODULE=config.settings.development

REM Step 1: Django system check
echo [Step 1] Running Django system check...
python manage.py check
if %errorlevel% neq 0 (
    echo FAIL: Django check failed
    exit /b 1
)
echo   OK: Django check passed
echo.

REM Step 2: Generate migrations
echo [Step 2] Generating migrations...
python manage.py makemigrations accounts knowledge commerce bridges transactions assets --name initial
if %errorlevel% neq 0 (
    echo FAIL: makemigrations failed
    exit /b 1
)
echo   OK: Migrations generated
echo.

REM Step 3: Apply migrations
echo [Step 3] Applying migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo FAIL: migrate failed
    exit /b 1
)
echo   OK: Migrations applied
echo.

REM Step 4: Verify URL endpoints
echo [Step 4] Verifying URL endpoints...
python scripts\verify_urls.py
echo.

REM Step 5: Run tests
echo [Step 5] Running tests...
python -m pytest apps/ -v --tb=short
echo.

echo ========================================
echo   T05 Verification Complete!
echo ========================================
