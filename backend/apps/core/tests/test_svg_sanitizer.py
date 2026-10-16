"""
svg_sanitizer 回归测试。

这个模块此前**零测试**，正是「零覆盖」让`_filter_attribute` 只把属性名
传给要求「属性名 + 等号 + 值」的正则这一笔误长期存活，最终形成可利用的
存储型 XSS：任意 is_staff 账号可 PUT commerce_product.structure_svg，
该字段在序列化输出时经sanitize_svg，而前端 ProductDetail.vue 用
v-html 渲染在**公开未登录**的产品详情页 ⇒ 低权限内部账号可对所有访客
植入持久 XSS。

因此补测试本身就是这次漏洞的根因修复的一部分，而非可选的附属工作。

⚠️ 断言方式：每条用例都断言**恶意内容确实不在输出里**（assertNotIn /
assertNotRegex），而不是只断言「输出有变化」——后者在白名单把整块标签
删掉时也会通过，等于没测。
"""
import re

from django.test import SimpleTestCase

from core.svg_sanitizer import SAFE_SVG_TAGS, sanitize_svg


# 生产库真实样本（RDKit 风格），必须原样保留。
# 它同时覆盖了本次修复最容易误伤的三点：
#   1) linearGradient / stop / rect / text —— 白名单必须放行
#   2) style="stop-color:#f0fdfa"—— style **属性**必须保留（≠ <style> 元素）
#   3) fill="url(#bg)"            —— # 号与冒号不能被属性解析误伤
PRODUCTION_SAMPLE = (
    '<svg><defs><linearGradient id="bg">'
    '<stop offset="0%" style="stop-color:#f0fdfa"/>'
    '</linearGradient></defs>'
    '<rect fill="url(#bg)"/><text>SC8020</text></svg>'
)


class DangerousUrlAttributeTests(SimpleTestCase):
    """href / xlink:href / src 的 javascript:、data: URL 必须被清除。

    这些用例刻意使用 **白名单内** 的标签（use / image）。
    原因：`<a>` 不在 SAFE_SVG_TAGS 里，白名单一开就会被连内容整块删除，
    届时即使属性过滤逻辑整体回退，用例依然会「通过」——那样的测试等于没有。
    用白名单内标签才能真正证明属性过滤这条路径在工作。
    """

    def test_href_javascript(self):
        """#1 基础向量：href="javascript:..."（历史笔误下原样穿透）。"""
        out = sanitize_svg('<svg><use href="javascript:alert(1)"/></svg>')
        self.assertNotIn('javascript:', out)
        self.assertNotIn('alert(1)', out)

    def test_href_javascript_mixed_case(self):
        """#2 大小写混淆不能绕过。"""
        out = sanitize_svg('<svg><use href="JaVaScRiPt:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_href_javascript_leading_whitespace(self):
        """#3 前导空格不能绕过（值两侧的空白同样要吃掉协议前的空隙）。"""
        out = sanitize_svg('<svg><use href="  javascript:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_xlink_href_javascript(self):
        """#4 xlink:href 命名空间形式（第二条失效的正则针对的就是它）。"""
        out = sanitize_svg('<svg><use xlink:href="javascript:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_image_href_data_uri(self):
        """#5 data: URI（可承载 data:text/html 执行脚本）。"""
        out = sanitize_svg(
            '<svg><image href="data:text/html,<script>alert(1)</script>"/></svg>'
        )
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)data:')

    def test_image_src_javascript(self):
        """<image src="javascript:..."> 也必须覆盖到（src 与 href 同等对待）。"""
        out = sanitize_svg('<svg><image src="javascript:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_vbscript_uri(self):
        """vbscript: 属于同一类协议绕过，一并覆盖。"""
        out = sanitize_svg('<svg><use href="vbscript:msgbox(1)"/></svg>')
        self.assertNotRegex(out, r'(?i)vbscript:')

    def test_javascript_with_embedded_tab(self):
        """把协议名拆开（java<TAB>script:）是老式绕过，必须挡住。

        浏览器的 URL 解析器会剥除 href 里的制表/换行，所以这在真实页面上
        是可执行的。注：靠正则里的 \\s* 挡不住——\\s* 只能吃掉冒号附近的空白，
        拆开协议名内部的空白无效，因此必须先归一化整个值再比协议。
        """
        out = sanitize_svg('<svg><use href="java\tscript:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_javascript_with_numeric_char_ref(self):
        """HTML 实体形式 java&#9;script: —— DOM 里解码后同上。"""
        out = sanitize_svg('<svg><use href="java&#9;script:alert(1)"/></svg>')
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')

    def test_data_uri_with_encoded_tab(self):
        """data: 同样要经得起归一化，否则 data&#58; 之类可绕过。"""
        out = sanitize_svg('<svg><use href="da&#9;ta:text/html,x"/></svg>')
        self.assertNotRegex(out, r'(?i)data:')

    def test_single_quoted_and_unquoted_values(self):
        """单引号 / 无引号两种写法都必须被正确解析出值。"""
        single = sanitize_svg("<svg><use href='javascript:alert(1)'/></svg>")
        self.assertNotIn('alert(1)', single)

        unquoted = sanitize_svg('<svg><use href=javascript:alert(1)/></svg>')
        self.assertNotIn('alert(1)', unquoted)


class EventHandlerAttributeTests(SimpleTestCase):
    """事件处理器属性（on*）—— 回归项，本次修复不得破坏既有行为。"""

    def test_onload_removed(self):
        """#6 回归：<svg onload="..."> 一直是被拦住的，别弄坏。"""
        out = sanitize_svg('<svg onload="alert(1)"></svg>')
        self.assertNotIn('onload', out)
        self.assertNotIn('alert(1)', out)

    def test_onclick_onerror_onmouseover(self):
        """#6 扩展：多个事件处理器属性名都要被识别。"""
        for payload in (
            '<svg><circle onclick="alert(1)" r="5"/></svg>',
            '<svg><circle onerror="alert(1)" r="5"/></svg>',
            '<svg><circle onmouseover="alert(1)" r="5"/></svg>',
        ):
            with self.subTest(payload=payload):
                out = sanitize_svg(payload)
                self.assertNotIn('alert(1)', out)
                self.assertNotRegex(out, r'(?i)\son\w+\s*=')

    def test_benign_attributes_are_preserved(self):
        """on* 规则不能误伤正常属性：class / style / fill 等必须原样保留。"""
        out = sanitize_svg(
            '<svg><rect class="bond" style="stop-color:#f0fdfa" fill="#fff"/></svg>'
        )
        self.assertIn('class="bond"', out)
        self.assertIn('style="stop-color:#f0fdfa"', out)
        self.assertIn('fill="#fff"', out)


class DangerousElementTests(SimpleTestCase):
    """危险元素必须连内容一起删除。"""

    def test_script_element(self):
        """#7 回归：<script> 一直被拦住。"""
        out = sanitize_svg('<svg><script>alert(1)</script></svg>')
        self.assertNotIn('script', out)
        self.assertNotIn('alert(1)', out)

    def test_iframe_element(self):
        """#8 回归：<iframe> 一直被拦住。"""
        out = sanitize_svg('<svg><iframe src="//evil"></iframe></svg>')
        self.assertNotIn('iframe', out)
        self.assertNotIn('//evil', out)

    def test_style_element_removed(self):
        """#9 <style> **元素**可注入 @import 外链做数据外泄，必须整块删除。"""
        out = sanitize_svg(
            '<svg><style>@import url(//evil.example/x.css);</style></svg>'
        )
        self.assertNotIn('@import', out)
        self.assertNotIn('evil.example', out)
        self.assertNotIn('<style', out)

    def test_foreign_object_removed_with_content(self):
        """#10 <foreignObject> 能内嵌 HTML，必须连内容一起删。"""
        out = sanitize_svg('<svg><foreignObject><body onload=x></body></foreignObject></svg>')
        self.assertNotIn('foreignObject', out)
        self.assertNotIn('foreignobject', out.lower())
        self.assertNotIn('onload', out)
        self.assertNotIn('<body', out)

    def test_animate_and_set_removed(self):
        """SMIL 动画元素可用于属性注入（animate attributeName=href values=javascript:...）。"""
        for payload in (
            '<svg><animate attributeName="href" values="javascript:alert(1)"/></svg>',
            '<svg><set attributeName="onload" to="alert(1)"/></svg>',
        ):
            with self.subTest(payload=payload):
                out = sanitize_svg(payload)
                self.assertNotIn('alert(1)', out)
                self.assertNotIn('javascript:', out)

    def test_animate_attribute_injection_needs_both_layers(self):
        """即使 <animate> 元素本身被删，其注入的 href 值也不能残留。"""
        out = sanitize_svg(
            '<svg><a><animate attributeName="href" values="javascript:alert(1)"/>'
            '<text>x</text></a></svg>'
        )
        self.assertNotIn('alert(1)', out)
        self.assertNotRegex(out, r'(?i)javascript:')


class WhitelistGuardTests(SimpleTestCase):
    """白名单护栏：非白名单标签连内容一起删除。"""

    def test_production_sample_preserved_verbatim(self):
        """#11 最关键的一条：生产真实样本必须**原样保留**。

        证明白名单没有误伤真实渲染，且 style="..." 属性没被当成 <style> 元素删掉。
        若这条挂了，说明白名单或style 处理有问题，前端所有结构图会挂。
        """
        self.assertEqual(sanitize_svg(PRODUCTION_SAMPLE), PRODUCTION_SAMPLE)

    def test_production_sample_key_elements_present(self):
        """显式断言生产样本的关键元素都在（失败时能立刻看出是哪个环节）。"""
        out = sanitize_svg(PRODUCTION_SAMPLE)
        for fragment in ('<linearGradient', '<stop', 'style="stop-color:#f0fdfa"',
                         '<rect', 'fill="url(#bg)"', '<text', 'SC8020'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, out)

    def test_production_tag_vocabulary_is_whitelisted(self):
        """白名单的依据护栏：生产实际使用的 9 种标签必须全部在白名单内。

        将来若有人给白名单「瘦身」，或RDKit 改了输出，这里会立刻失败，
        从而在部署前暴露"结构图全挂"的风险。
        """
        production_tags = {
            'circle', 'defs', 'g', 'line', 'lineargradient',
            'rect', 'stop', 'svg', 'text',
        }
        self.assertTrue(
            production_tags <= SAFE_SVG_TAGS,
            f'生产标签未被白名单覆盖: {production_tags - SAFE_SVG_TAGS}',
        )

    def test_non_whitelisted_tag_removed_with_content(self):
        """任意非白名单标签都应连内容删除。"""
        for tag in ('marquee', 'blink', 'foo'):
            with self.subTest(tag=tag):
                out = sanitize_svg(f'<svg><{tag}>PAYLOAD</{tag}></svg>')
                self.assertNotIn('PAYLOAD', out)
                self.assertNotIn(f'<{tag}', out)

    def test_a_element_removed(self):
        """<a> 不在白名单（超链接在本平台无意义），应连内容删除。"""
        out = sanitize_svg('<svg><a href="//evil"><text>x</text></a></svg>')
        self.assertNotIn('<a', out)
        self.assertNotIn('//evil', out)

    def test_style_attribute_not_confused_with_style_element(self):
        """核心区分点：style 属性（合法、生产大量使用）≠ <style> 元素（必须删）。"""
        out = sanitize_svg(
            '<svg><stop offset="0%" style="stop-color:#f0fdfa"/>'
            '<style>@import url(//evil.example/x.css);</style></svg>'
        )
        self.assertIn('style="stop-color:#f0fdfa"', out)
        self.assertNotIn('@import', out)
        self.assertNotIn('evil.example', out)


class InputValidationTests(SimpleTestCase):
    """#12 非法/边界输入不抛异常。"""

    def test_empty_svg_tag_preserved(self):
        """最小合法 SVG 原样返回。"""
        self.assertEqual(sanitize_svg('<svg></svg>'), '<svg></svg>')

    def test_empty_string(self):
        self.assertEqual(sanitize_svg(''), '')

    def test_none(self):
        self.assertEqual(sanitize_svg(None), '')

    def test_non_string_types(self):
        """非字符串输入返回 ''，且不抛异常（序列化层可能传入 Decimal/int 等）。"""
        for value in (123, 123.45, [], {}, object(), b'<svg onload="x"></svg>'):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(sanitize_svg(value), '')

    def test_non_svg_string_returns_empty(self):
        """不含 <svg 的输入视为无效，返回 ''。"""
        self.assertEqual(sanitize_svg('hello world'), '')
        self.assertEqual(sanitize_svg('<div>not svg</div>'), '')

    def test_stray_closing_tag_is_cleaned(self):
        """落单的结束标签不应残留（正则去标签时可能留下孤儿 closing tag）。"""
        out = sanitize_svg('<svg></foreignObject></svg>')
        self.assertNotIn('foreignObject', out)


class IdempotencyTests(SimpleTestCase):
    """幂等性：sanitize(sanitize(x)) == sanitize(x)。

    清理逻辑跑第二遍不应改变结果——否则说明某条规则依赖了输入的原始形态，
    重复调用会持续啃掉内容。
    """

    def test_idempotent_on_production_sample(self):
        once = sanitize_svg(PRODUCTION_SAMPLE)
        self.assertEqual(sanitize_svg(once), once)

    def test_idempotent_on_malicious_payloads(self):
        payloads = [
            '<svg><use href="javascript:alert(1)"/></svg>',
            '<svg><use xlink:href="javascript:alert(1)"/></svg>',
            '<svg><image href="data:text/html,<script>alert(1)</script>"/></svg>',
            '<svg onload="alert(1)"></svg>',
            '<svg><script>alert(1)</script></svg>',
            '<svg><iframe src="//evil"></iframe></svg>',
            '<svg><style>@import url(//evil.example/x.css);</style></svg>',
            '<svg><foreignObject><body onload=x></body></foreignObject></svg>',
            '<svg><a href="javascript:alert(1)"><text>x</text></a></svg>',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                once = sanitize_svg(payload)
                self.assertEqual(sanitize_svg(once), once)

    def test_output_never_contains_script_or_event_handlers(self):
        """不变量：对任意输入，输出都不含 <script 与 on*= 事件属性。"""
        payloads = [PRODUCTION_SAMPLE] + [
            '<svg><a href="javascript:alert(1)"><text>x</text></a></svg>',
            '<svg><g onload="alert(1)"><rect onmouseover="alert(2)"/></g></svg>',
            '<svg><foreignObject><body onload=x></body></foreignObject></svg>',
            '<svg><use href="data:text/html,x"/></svg>',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                out = sanitize_svg(payload)
                self.assertNotIn('<script', out.lower())
                self.assertNotRegex(out, r'(?i)\son[a-z]+\s*=')
                self.assertNotRegex(out, r'(?i)javascript:')