"""Reagent Class Step 7 — 阈值落地（Rule Governance，可复现）

RC-10：规则 precision 验证通过（专家抽检 100%）→ threshold_passed → 对应 assignment 转 auto_accepted。
2026-08-24 判定：nucleotide.modified/fluorescent/terminator（v1.1）抽检 17+11+10=38 条 100% 正确。
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.apps import apps
from django.db import transaction

PRC = apps.get_model('bridges', 'ProductReagentClass')

PASSED_RULES = {
    'nucleotide.modified': '1.1',
    'nucleotide.fluorescent': '1.1',
    'nucleotide.terminator': '1.1',
}

def main():
    n = 0
    with transaction.atomic():
        for rule, ver in PASSED_RULES.items():
            qs = PRC.objects.filter(classification_rule=rule, classification_rule_version=ver,
                                    status__in=['pending_review', 'candidate'])
            k = qs.count()
            qs.update(status='auto_accepted')
            n += k
            print(f'  {rule} v{ver}: {k} 条 → auto_accepted')
    left = PRC.objects.filter(status='pending_review').count()
    print(f'合计 {n} 条转 auto_accepted；剩余 pending_review: {left}')
    print('提示：rebuild derived 请运行 rc_rebuild.py --apply')

if __name__ == '__main__':
    main()
