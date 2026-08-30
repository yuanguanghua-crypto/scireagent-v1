"""Reagent Class Step 8 — derived rebuild（allow-list，幂等，向后兼容 CLI）。

逻辑已迁移至 apps.bridges.services.derived_builder；本文件仅作 CLI 入口，
委托 derived_builder.rebuild_all_derived()（等价原全量重建语义，含 MUST-15）。

默认 dry-run；--apply 写库。

注：8-24 生产部署时服务器 /tmp/rc_rebuild.py 为旧副本（已跑完，prod 159 边已落库），
本文件重构不影响已落库数据。
"""
import os
import sys

DRY = '--apply' not in sys.argv


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()

    if DRY:
        print('=== Derived Rebuild (dry-run) ===')
        print('说明：dry-run 不修改数据；用 --apply 写库（委托 derived_builder）。')
        return

    from apps.bridges.services.derived_builder import rebuild_all_derived
    n = rebuild_all_derived()
    print(f'=== Derived Rebuild (apply) === 处理产品数: {n}')


if __name__ == '__main__':
    main()
