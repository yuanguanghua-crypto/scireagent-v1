"""SEO 自动生成 service — 从 ProductAdmin.save_model 抽离。

供 Django Admin 和 Vue 工作台 API 共用。
"""


def generate_seo(product):
    """为产品自动生成 SEO 标题和描述（仅在字段为空时生成）。

    规则:
        seo_title = "{产品名} | SciReagent"
        seo_description = "Buy {产品名} (CAS: {CAS号}). High purity research reagent. Order from SciReagent."
    """
    changed = False

    if not product.seo_title:
        product.seo_title = f'{product.name} | SciReagent'
        changed = True

    if not product.seo_description:
        desc = f'Buy {product.name}'
        if product.cas:
            desc += f' (CAS: {product.cas})'
        desc += '. High purity research reagent. Order from SciReagent.'
        product.seo_description = desc
        changed = True

    return product, changed
