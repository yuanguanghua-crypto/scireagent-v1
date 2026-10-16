"""
SVG sanitization utilities.

Prevents XSS attacks from malicious SVG content stored in structure_svg fields.
Strips dangerous elements (<script>, event handlers, javascript: URLs) while
preserving safe SVG structure for rendering.

调用方（3 处，修复需同时覆盖）：
  - apps/commerce/api/v1/serializers.py     ProductSerializer.get_structure_svg
  - apps/commerce/api/v1/serializers_v2.py  同上（v2）
  - apps/knowledge/api/v1/site_views.py     站点结构图输出
"""
import re

# Dangerous SVG elements that must be completely removed
#
# ⚠️ 关于 'style'：这里指的是 <style> **元素**（可注入 @import 外链做数据外泄），
#    不是 style="stop-color:#f0fdfa" 这类 **属性**（生产数据大量使用的合法样式）。
#    两者是完全不同的东西，本模块只删元素、不动属性。
DANGEROUS_ELEMENTS = [
    'script', 'iframe', 'embed', 'object', 'applet',
    'form', 'input', 'button', 'textarea', 'select',
    # 以下为存储型 XSS 修复新增
    'style', 'foreignobject',   # <style>@import 外链；<foreignObject> 可内嵌 HTML
    'animate', 'set',           # SMIL 动画可被用来做属性注入
    'handler', 'audio', 'video',
]

# Dangerous attribute patterns (event handlers, javascript URLs)
#
# ⚠️ 历史笔误（存储型 XSS 根因）：下面第 2/3 条要求「属性名 + 等号 + 值」，
#    而 _filter_attribute 过去**只把属性名**传进来匹配，导致这两条恒不命中，
#    `<a href="javascript:...">` 原样穿透。现已改为在 _filter_attribute 内
#    直接解析属性名 + 属性值后判断（见该函数）。
#    此常量仅为兼容外部引用保留，实际判断不再走它。
DANGEROUS_ATTR_PATTERNS = [
    re.compile(r'^on\w+', re.IGNORECASE),          # onclick, onload, onerror, etc.
    re.compile(r'^href\s*=\s*["\']?\s*javascript:', re.IGNORECASE),  # javascript: URLs
    re.compile(r'^xlink:href\s*=\s*["\']?\s*javascript:', re.IGNORECASE),
]

# Allow only known safe SVG element tags
SAFE_SVG_TAGS = {
    'svg', 'g', 'path', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
    'rect', 'text', 'tspan', 'defs', 'clippath', 'lineargradient',
    'radialgradient', 'stop', 'title', 'desc', 'use', 'symbol', 'image',
    'marker', 'pattern', 'mask', 'filter', 'feblend', 'fecolormatrix',
    'fecomponenttransfer', 'fecomposite', 'feconvolvematrix',
    'fediffuselighting', 'fedisplacementmap', 'fedistantlight',
    'feflood', 'fefunca', 'fefuncb', 'fefuncg', 'fefuncr',
    'fegaussianblur', 'feimage', 'femerge', 'femergenode',
    'femorphology', 'feoffset', 'fepointlight', 'fespecularlighting',
    'fespotlight', 'fetile', 'feturbulence',
}


# 数字字符引用（如 &#9; / &#x09;）：浏览器解析 HTML 属性时会先解码，
# 所以 "java&#9;script:" 到 DOM 里就变成 "java<TAB>script:"。
_NUMERIC_CHAR_REF = re.compile(r'&#(?:x([0-9a-fA-F]+)|([0-9]+));?')
# 空白与控制字符：URL 解析器会剥除它们
_CTRL_WS = re.compile(r'[\s\x00-\x1f\x7f]+')
# 危险协议
_DANGEROUS_SCHEME = re.compile(r'^(?:javascript|vbscript|data):', re.IGNORECASE)


def _normalize_url_value(value: str) -> str:
    """把 URL 属性值归一化到"浏览器实际看到的样子"，再判协议。

    只做两件事，都不是过度设计，而是因为浏览器会这么干：
      1. 解码数字字符引用（&#9; → TAB）
      2. 剥除全部空白与控制字符（"java\\tscript:" → "javascript:"）
    少了任一步，协议名就能被拆开绕过。
    """
    def _decode(match):
        code = match.group(1) or match.group(2)
        try:
            point = int(code, 16) if match.group(1) else int(code, 10)
        except ValueError:
            return ''
        return chr(point) if 0 < point < 0x110000 else ''

    return _CTRL_WS.sub('', _NUMERIC_CHAR_REF.sub(_decode, value))


def _strip_non_whitelisted_tags(svg_string: str) -> str:
    """
    白名单护栏：删除所有不在 SAFE_SVG_TAGS 内的标签，**连同其内容一起删除**。

    例：<foreignObject>...</foreignObject>、<style>...</style> 整块消失。
    仅删除**标签**；`style="stop-color:#f0fdfa"` 这类属性不受影响。

    依据：生产库实测 64 个产品的 structure_svg 只用到 9 种标签
    (circle/defs/g/line/lineargradient/rect/stop/svg/text)，全部在白名单内，
    因此开启白名单不会破坏任何现有渲染。
    """
    # 找出文档中出现过的所有标签名
    found = re.findall(r'<\s*/?\s*([a-zA-Z][\w:.-]*)', svg_string)
    for tag in set(found):
        if tag.lower() in SAFE_SVG_TAGS:
            continue
        escaped = re.escape(tag)
        # 带内容的成对标签（含跨行）：<tag ...>...</tag>
        svg_string = re.sub(
            rf'<{escaped}(?=[\s/>])[^>]*>.*?</{escaped}\s*>',
            '',
            svg_string,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # 自闭合：<tag ... />
        svg_string = re.sub(
            rf'<{escaped}(?=[\s/>])[^>]*/\s*>',
            '',
            svg_string,
            flags=re.IGNORECASE,
        )
        # 落单的结束标签 </tag>
        svg_string = re.sub(rf'</{escaped}\s*>', '', svg_string, flags=re.IGNORECASE)
    return svg_string


def sanitize_svg(svg_string: str) -> str:
    """
    Sanitize an SVG string by removing dangerous elements and attributes.

    This is a defense-in-depth measure. The SVG should already be generated
    by trusted code (RDKit), but this protects against manual edits or
    data injection.

    Args:
        svg_string: Raw SVG string, possibly containing malicious content.

    Returns:
        Sanitized SVG string with dangerous content removed.
        Returns empty string if the input is not valid SVG.
    """
    if not svg_string or not isinstance(svg_string, str):
        return ''

    # Quick check: must contain <svg to be valid
    if '<svg' not in svg_string.lower():
        return ''

    # Remove dangerous elements entirely (including content)
    for tag in DANGEROUS_ELEMENTS:
        # Self-closing tags
        svg_string = re.sub(
            rf'<{tag}[^>]*/\s*>',
            '',
            svg_string,
            flags=re.IGNORECASE,
        )
        # Opening + closing tags with content
        svg_string = re.sub(
            rf'<{tag}[^>]*>.*?</{tag}>',
            '',
            svg_string,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # 白名单护栏：非白名单标签连内容一起删除
    # （此前 SAFE_SVG_TAGS 是死代码，黑名单之外的一切标签都被放行）
    svg_string = _strip_non_whitelisted_tags(svg_string)

    # Remove dangerous attributes from remaining tags
    # Match attribute patterns like: attr="value" or attr='value' or attr=value
    def _remove_dangerous_attrs(match):
        tag_content = match.group(0)
        # Reconstruct tag, filtering out dangerous attributes
        result = re.sub(
            r'\s+(\w[\w:-]*)\s*=\s*(?:"[^"]*"|\'[^\']*\'|\S+)',
            _filter_attribute,
            tag_content,
        )
        return result

    def _filter_attribute(attr_match):
        """丢弃危险属性：事件处理器（on*）与 javascript:/data: URL（href/xlink:href/src）。"""
        full_attr = attr_match.group(0)
        # 必须同时解析出属性「名」和「值」——只看名字会让 href 规则恒不命中
        parsed = re.match(
            r'\s+([\w:.-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))',
            full_attr,
        )
        if not parsed:
            return full_attr
        name = parsed.group(1).lower()
        value = parsed.group(2) or parsed.group(3) or parsed.group(4) or ''
        # 1) 事件处理器：onclick / onload / onerror ...（只看属性名即足够）
        if re.match(r'^on\w+', name, re.IGNORECASE):
            return ''
        # 2) href / xlink:href / src 的危险协议（必须看属性值）
        #    先归一化（解实体 + 剥空白控制字符），否则 "java<TAB>script:" 这类
        #    把协议名拆开的绕过能生效——浏览器的 URL 解析器正是这么做的
        if name in ('href', 'xlink:href', 'src'):
            if _DANGEROUS_SCHEME.match(_normalize_url_value(value)):
                return ''
        # 其余属性原样返回，保住原有空白与引号风格
        return full_attr

    # Process each opening tag
    svg_string = re.sub(
        r'<[a-zA-Z][^>]*>',
        _remove_dangerous_attrs,
        svg_string,
    )

    # Remove any remaining CDATA sections that might contain scripts
    svg_string = re.sub(r'<!\[CDATA\[.*?\]\]>', '', svg_string, flags=re.DOTALL)

    # Remove XML processing instructions
    svg_string = re.sub(r'<\?.*?\?>', '', svg_string)

    # Remove HTML comments (can contain conditional execution)
    svg_string = re.sub(r'<!--.*?-->', '', svg_string, flags=re.DOTALL)

    return svg_string.strip()
