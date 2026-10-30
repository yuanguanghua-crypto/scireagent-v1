"""闸门有效性验证：临时把 4 处修复「改坏」，确认对应测试变红，再还原。

A 类闸门判据（docs/e2e/GLOBAL_TEST_DEFINITION.md）：**改坏代码闸门必须红**。
本脚本用 try/finally 保证任何情况下都还原源文件。
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'backend'
VENV = BASE / 'venv' / 'Scripts' / 'python.exe'

# (标签, 文件, 原文, 改坏的版本, 应失败的测试节点)
CASES = [
    (
        '① 分类参数解析不到时回落到全量（旧 bug）',
        BASE / 'apps/commerce/api/v1/views.py',
        "            qs = qs.filter(product_class_id__in=ids) if ids else qs.none()\n"
        "        # Filter by category_l2 name",
        "            if ids:\n"
        "                qs = qs.filter(product_class_id__in=ids)\n"
        "        # Filter by category_l2 name",
        'apps/knowledge/tests/test_homepage_category_pills.py::'
        'HomeCategoryPillsContractTest::test_pill_count_equals_click_through_total',
    ),
    (
        '② site_home 不返回 class_slug',
        BASE / 'apps/knowledge/api/v1/site_views.py',
        "categories_payload.append({**meta, 'class_slug': l1_slug, 'count': count})",
        "categories_payload.append({**meta, 'count': count})",
        'apps/knowledge/tests/test_homepage_category_pills.py::'
        'HomeCategoryPillsContractTest::test_every_pill_has_class_slug',
    ),
    (
        '③ 分类树计数不过滤 status/archived/夹具',
        BASE / 'apps/commerce/api/v1/categories.py',
        "        visible = Product.objects.filter(\n"
        "            status__in=['active', 'published'], archived=False, is_test_fixture=False)",
        "        visible = Product.objects.all()",
        'apps/commerce/tests/test_category_tree_view.py::'
        'TestCategoryTreeView::test_count_excludes_test_fixture',
    ),
    (
        '④ 公开列表不排除测试夹具',
        BASE / 'apps/commerce/api/v1/views.py',
        "            if not is_staff_request(self.request):\n"
        "                qs = qs.filter(is_test_fixture=False)",
        "            if False:\n"
        "                qs = qs.filter(is_test_fixture=False)",
        'apps/commerce/tests/test_product_fixture_visibility.py::'
        'ProductFixtureVisibilityTest::test_anonymous_list_excludes_fixture',
    ),
]


def run(test_node):
    proc = subprocess.run(
        [str(VENV), '-m', 'pytest', test_node, '-q', '--no-header', '-p', 'no:warnings'],
        cwd=str(BASE), capture_output=True, text=True,
    )
    return proc.returncode


def main():
    results = []
    for label, path, good, bad, node in CASES:
        src = path.read_text(encoding='utf-8')
        if good not in src:
            results.append((label, 'SKIP', f'未找到待改坏片段（可能已被改过）：{path.name}'))
            continue
        try:
            path.write_text(src.replace(good, bad, 1), encoding='utf-8')
            rc = run(node)
        finally:
            path.write_text(src, encoding='utf-8')
        results.append((label, 'RED' if rc != 0 else 'GREEN(异常)', node))

    print('\n=== 闸门有效性 ===')
    ok = True
    for label, verdict, detail in results:
        mark = '通过' if verdict == 'RED' else '失败'
        if verdict != 'RED':
            ok = False
        print(f'[{mark}] {label} → {verdict}')
        if verdict != 'RED':
            print(f'        {detail}')
    print('\n结论：', '4/4 闸门均能捕获回归' if ok else '存在无法捕获回归的闸门')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
