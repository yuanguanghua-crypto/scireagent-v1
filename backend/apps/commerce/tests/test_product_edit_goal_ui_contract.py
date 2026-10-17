"""★ TDD 契约测试：ProductEditPage.vue 的 goal/app 级联**必须走全量 method_ids**。

为什么需要源码契约测试：
  本仓库前端**没有单测运行器**（`frontend/package.json` 只有 playwright e2e，
  无 vitest/jest —— 见 node_modules/.bin 无对应 bin），无法对 .vue 跑函数级单测。
  而本次改动的核心安全性质**完全位于前端**：
    「只要提交 research_goal_ids / application_ids，就必须同时回传**全量** method_ids」
  这条性质一旦被后人改回 baseline 增量，会静默删除产品既有方法关联 ——
  且**不会有任何后端测试变红**（后端行为没变，变的是前端 payload）。

⇒ 故以源码契约方式钉死：对 ProductEditPage.vue 断言其 payload 组装逻辑含该保护。
   这不是"检查文件存在"，而是断言**具体的安全不变式**；删掉保护代码即变红。
"""
from pathlib import Path

from django.test import SimpleTestCase

# 本文件位于 <repo>/backend/apps/commerce/tests/test_x.py
#   parents[0]=tests, [1]=commerce, [2]=apps, [3]=backend, [4]=<repo>
_REPO_ROOT = Path(__file__).resolve().parents[4]
PRODUCT_EDIT_VUE = (
    _REPO_ROOT / 'frontend' / 'src' / 'views' / 'workspace' / 'ProductEditPage.vue'
)


class ProductEditGoalCascadeContractTest(SimpleTestCase):
    """前端源码级安全契约（对应后端 test_product_goal_cascade_probe 的删除风险）。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not PRODUCT_EDIT_VUE.exists():
            raise AssertionError(f'未找到 {PRODUCT_EDIT_VUE}，契约测试无法定位前端源文件')
        cls.src = PRODUCT_EDIT_VUE.read_text(encoding='utf-8')

    def test_payload_sends_goal_and_app_ids(self):
        """UI 存在且会把选择提交为 research_goal_ids / application_ids。"""
        self.assertIn('payload.research_goal_ids', self.src,
                      '未提交 research_goal_ids —— goal 级联入口未接上')
        self.assertIn('payload.application_ids', self.src,
                      '未提交 application_ids —— app 级联入口未接上')

    def test_goal_app_branch_sends_full_method_ids(self):
        """★核心不变式：goal/app 分支必须回传**全量** method_ids。

        断言 `payload.method_ids = merged`（并集后的全量）出现在 goal/app 分支内，
        而不是仅在 baseline 增量分支 `payload.method_ids = methodIds.value`。
        """
        self.assertIn('if (hasGoalAppSelection.value) {', self.src,
                      '缺少 hasGoalAppSelection 分支 —— goal/app 与 method_ids 未同批次提交')
        self.assertIn('payload.method_ids = merged', self.src,
                      'goal/app 分支未回传全量 method_ids —— '
                      '会导致 desired 退化为纯级联集并删除既有方法关联')
        # 全量赋值必须出现在 baseline 增量赋值【之前】，否则分支顺序反了
        self.assertLess(
            self.src.index('payload.method_ids = merged'),
            self.src.index('payload.method_ids = methodIds.value'),
            '全量赋值须在 baseline 增量赋值之前（if/else 结构被改动）',
        )

    def test_cascade_impact_is_surfaced_to_user(self):
        """必须显示级联影响（"将连带关联 N 个方法"），不能静默改写方法链。"""
        self.assertIn('cascadePreview', self.src, '缺少级联影响预览计算')
        self.assertIn('hasGoalAppSelection', self.src, '级联提示未与选择状态绑定')
        # 提示文案必须出现"连带"字样，明确告知会改写 Methods
        self.assertRegex(
            self.src, r'连带',
            '级联提示文案未说明"连带"影响 —— 用户会误以为这是无害的标签操作',
        )

    def test_clear_selection_omits_keys_rather_than_sending_empty_array(self):
        """★ 清空语义：分支条件用 `.length > 0` ⇒ 清空后 key 不进 payload（而非传 []）。

        历史背景（2026-10-17 已在后端修复）：传 [] 曾会让后端
        `_merge_method_ids` 的 cascaded 为空、direct 也为空 ⇒ desired 退化为空集
        ⇒ 整条方法链被清空（当时已由 probe 测试实测坐实）。

        后端现已修复为"级联项只增不删"，故传 [] **不再**清空方法链；但本契约
        **仍然保留**：前端少发两个无意义的 key 更干净，且它同时把"清空"与
        "显式清空方法链（method_ids=[]）"这两种语义区分开，避免将来后端口径变化时
        再次出现误删。前端护栏是第二道防线，不可移除。
        """
        self.assertIn('goalIds.value.length > 0 || appIds.value.length > 0', self.src,
                      'hasGoalAppSelection 未按"长度>0"判定 —— 清空时会误传空数组')
        # 两个 key 必须都挂在 goal/app 分支内（而不是无条件写入 payload）
        branch_start = self.src.index('if (hasGoalAppSelection.value) {')
        goal_key = self.src.index('payload.research_goal_ids')
        app_key = self.src.index('payload.application_ids')
        self.assertGreater(goal_key, branch_start, 'research_goal_ids 未挂在 goal/app 分支内')
        self.assertGreater(app_key, branch_start, 'application_ids 未挂在 goal/app 分支内')
        # 全量 method_ids 必须【先于】两个 key 赋值 —— 保证 desired 是超集
        self.assertLess(
            self.src.index('payload.method_ids = merged'),
            goal_key,
            'method_ids 必须在 goal/app key 之前赋值，否则 payload 里 method_ids 缺失 ⇒ 触发删除',
        )