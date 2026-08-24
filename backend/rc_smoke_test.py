"""Reagent Class Step 1.5 — constraint smoke test v2（dev，savepoint 隔离，整体回滚零残留）"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.apps import apps

RC = apps.get_model('knowledge', 'ReagentClass')
Method = apps.get_model('knowledge', 'Method')
Product = apps.get_model('commerce', 'Product')
MRC = apps.get_model('bridges', 'MethodReagentClass')
PRC = apps.get_model('bridges', 'ProductReagentClass')
PMR = apps.get_model('bridges', 'ProductMethodRelation')

results = []


def expect_error(name, fn):
    """在独立 savepoint 内执行应触发 IntegrityError/ValidationError 的操作。"""
    try:
        with transaction.atomic():
            fn()
        results.append((name, 'FAIL（未触发预期异常）'))
    except (IntegrityError, ValidationError):
        results.append((name, 'PASS'))
    except Exception as e:
        results.append((name, f'FAIL({type(e).__name__}: {e})'))


class _Rollback(Exception):
    pass

try:
    with transaction.atomic():
        # 基础：建临时 RC + 取真实 Method/Product（主事务，最后整体回滚）
        rc = RC.objects.create(id_code='RC-99TEST', name='Smoke Test RC', slug='smoke-test-rc',
                               behavior_type='context_dependent')
        m = Method.objects.filter(is_test_fixture=False).first()
        p = Product.objects.filter(archived=False).first()
        if not m or not p:
            m = Method.objects.first()
            p = Product.objects.first()
        m2 = Method.objects.exclude(pk=m.pk).filter(is_test_fixture=False).first() or m
        print(f'用 Method #{m.pk} / Product #{p.pk} 做约束冒烟测试')

        # 1. uq_mrc_method_rc：重复 (method, rc)
        MRC.objects.create(method=m, reagent_class=rc, dependency_type='essential', scope='canonical')
        expect_error('uq_mrc_method_rc', lambda: MRC.objects.create(
            method=m, reagent_class=rc, dependency_type='enabling', scope='common'))

        # 2. ck_mrc_conditional_not_essential：conditional + essential 禁止
        expect_error('ck_mrc_conditional_not_essential', lambda: MRC.objects.create(
            method=m2, reagent_class=rc, dependency_type='essential', scope='conditional'))

        # 3. uq_prc_product_rc：重复 (product, rc)
        PRC.objects.create(product=p, reagent_class=rc)
        expect_error('uq_prc_product_rc', lambda: PRC.objects.create(product=p, reagent_class=rc))

        # 4. ck_prc_conditional_requires_evidence：conditional + evidence 空 禁止
        expect_error('ck_prc_conditional_requires_evidence', lambda: PRC.objects.create(
            product=p, reagent_class=rc, assignment_type='conditional', evidence=''))

        # 5. validator：非法 JSON ref 拒绝
        expect_error('validate_evidence_reference', lambda: MRC.objects.create(
            method=m, reagent_class=rc, dependency_type='enabling', scope='common',
            evidence_reference=[{'type': 'XXX', 'value': '1'}]))

        # 6. uq_pmr_product_method_relation_type：重复 (product, method, derived)
        PMR.objects.create(product=p, method=m, relation_type='derived_relevance',
                           source_reagent_class=rc)
        expect_error('uq_pmr_product_method_relation_type', lambda: PMR.objects.create(
            product=p, method=m, relation_type='derived_relevance', source_reagent_class=rc))

        # 7. ck_pmr_relation_discriminator：derived 带 evidence 禁止
        expect_error('ck_pmr_derived_with_evidence', lambda: PMR.objects.create(
            product=p, method=m2, relation_type='derived_relevance',
            source_reagent_class=rc, evidence_type='protocol'))

        # 8. ck_pmr_relation_discriminator：verified 无 evidence 禁止
        expect_error('ck_pmr_verified_no_evidence', lambda: PMR.objects.create(
            product=p, method=m2, relation_type='verified_applicability'))

        # 9. ck_pmr_relation_discriminator：verified 带 source_rc 禁止
        expect_error('ck_pmr_verified_with_source_rc', lambda: PMR.objects.create(
            product=p, method=m2, relation_type='verified_applicability',
            source_reagent_class=rc, evidence_type='protocol',
            evidence_reference=[{'type': 'PMID', 'value': '1'}], evidence_strength='high'))

        raise _Rollback()
except _Rollback:
    pass
except Exception as e:
    results.append(('SETUP', f'FAIL({type(e).__name__}: {e})'))

print()
print('=== Constraint Smoke Test 结果 ===')
all_pass = True
for name, status in results:
    print(f'  [{"✅" if status == "PASS" else "❌"}] {name}: {status}')
    if status != 'PASS':
        all_pass = False
print()
print('结论:', 'ALL PASS ✅（约束全部生效，临时数据已回滚）' if all_pass else '有 FAIL ❌')
sys.exit(0 if all_pass else 1)
