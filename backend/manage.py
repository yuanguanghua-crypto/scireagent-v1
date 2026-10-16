#!/usr/bin/env python
import os
import sys

def main():
    # 拦截误用 `manage.py test`：本项目 pytest 风格测试对它隐形，会造成"假通过"。
    # 必须在 Django 初始化之前 —— 误用要立刻失败，不值得为它先建测试库。
    # 详见 config/guard_manage_py_test.py（含已知局限说明）。
    from config.guard_manage_py_test import guard_manage_py_test
    guard_manage_py_test(sys.argv)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
