"""
SVG sanitization utilities.

Prevents XSS attacks from malicious SVG content stored in structure_svg fields.
Strips dangerous elements (<script>, event handlers, javascript: URLs) while
preserving safe SVG structure for rendering.
"""
import re

# Dangerous SVG elements that must be completely removed
DANGEROUS_ELEMENTS = [
    'script', 'iframe', 'embed', 'object', 'applet',
    'form', 'input', 'button', 'textarea', 'select',
]

# Dangerous attribute patterns (event handlers, javascript URLs)
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
        full_attr = attr_match.group(0)
        attr_name = re.match(r'\s+(\w[\w:-]*)', full_attr)
        if attr_name:
            name = attr_name.group(1).lower()
            for pattern in DANGEROUS_ATTR_PATTERNS:
                if pattern.match(name):
                    return ''
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
