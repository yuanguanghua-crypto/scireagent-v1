"""祖父白名单「同源」断言（2026-11-05 按 Muse 意见加的护栏）。

为什么需要这个测试：
  白名单有两处 —— `apps/knowledge/definition_rules.py::LEGACY_MD5`（导入闸用）
  与 `work/validate_definition.py::LEGACY_MD5`（独立校验脚本用）。
  两边各抄一份必然漂移：改了 A 忘了 B，就会一边放行、一边拒绝，且**不会报错**。
  所以用「集合完全相等」把它变成红灯。

★ 这不是形式主义：漂移的后果是"校验通过但导入拒绝"（或反过来），
  而这两种都不会有显式的错，只会表现为"某份文件莫名其妙过不了"。
"""
import importlib.util
import os

from django.conf import settings
from django.test import SimpleTestCase

from apps.knowledge.definition_rules import LEGACY_MD5 as RULES_LEGACY


def _load_validator():
    """按文件路径加载 work/validate_definition.py（它不在包里，不能 import）。"""
    path = os.path.join(settings.BASE_DIR.parent, 'work', 'validate_definition.py')
    spec = importlib.util.spec_from_file_location('_validate_definition', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LegacyWhitelistParityTest(SimpleTestCase):
    def test_whitelist_sets_are_identical(self):
        vd = _load_validator()
        self.assertEqual(
            set(RULES_LEGACY), set(vd.LEGACY_MD5),
            '祖父白名单两处不一致：definition_rules=%r / validate_definition=%r'
            % (sorted(RULES_LEGACY), sorted(vd.LEGACY_MD5)))

    def test_whitelist_is_not_empty(self):
        """空集合等于"没有祖父化能力"，两份密封件会立刻过不了 —— 这条防的是被误清空。"""
        self.assertGreaterEqual(len(RULES_LEGACY), 2)

    def test_every_entry_is_32_hex(self):
        """手打 md5 少一位会让规则静默失效（11-04 踩过），这里钉死格式。"""
        import re
        for m in RULES_LEGACY:
            self.assertRegex(m, r'^[0-9a-f]{32}$', '白名单项格式非法：%r' % m)
