"""
application_methods — 「应用实际展示哪些方法」的**唯一实现**。

## 为什么必须抽出来

这段逻辑原本只写在 `ApplicationDetailSerializer.get_methods` 里：

    active 直接输出（不论有无 application）
    非 active（draft / archived）按名字映射到 canonical
    按 name 去重，映射不到的噪音名跳过

迁移要做到「改造前后前台输出完全一致」，就必须拿**同一个函数**算基线。
用两份实现（序列化器一份、迁移脚本一份）必然漂移 —— 本仓库已经吃过这个亏：
`backfill_protocol_provenance` / `import_protocol_materials` / `backfill_protocol_steps`
三个命令因为各写一套标题匹配，导致同一份语料在三处匹配出不同结果。

## 迁移完成后

B 方案（方法↔应用改 M:N）落地后，本函数应改为直接读 `ApplicationMethod` 桥，
不再需要 `canonical_by_name` 实时翻译。
"""
from apps.knowledge.services.canonical_methods import canonical_by_name


def resolve_application_methods(app) -> list:
    """返回某个应用实际展示的方法列表 `[{'id','name','slug'}, ...]`。

    Args:
        app: Application 实例（需能访问 `app.methods` 反向关系）。

    Returns:
        按「首次出现顺序」去重后的方法三元组列表。
        active 方法原样输出；draft / archived 输出其同名 canonical；
        找不到 canonical 的噪音名（如 `__e2e_methods_*`）直接跳过。
    """
    methods = list(app.methods.all())
    if not methods:
        return []
    canonical = canonical_by_name({m.name for m in methods})
    out, seen = [], set()
    for m in methods:
        if m.status == 'active':
            triple = {'id': m.id, 'name': m.name, 'slug': m.slug}
        else:
            # draft / archived：映射到同名 canonical；映射不到就跳过（宁 miss 不错配）
            c = canonical.get(m.name)
            if c is None:
                continue
            triple = c
        if triple['name'] in seen:
            continue
        seen.add(triple['name'])
        out.append(triple)
    return out


def resolve_application_method_names(app) -> list:
    """同上，只返回名字（排序后）。用于迁移基线对照 —— 顺序无关、便于比对。"""
    return sorted({m['name'] for m in resolve_application_methods(app)})


def canonical_pool() -> dict:
    """canonical 方法池：`{name: [method_id, ...]}`（active 且无 application 归属）。

    多个同名时列表长度 > 1，调用方必须自行判断是否有歧义。
    """
    from apps.knowledge.models import Method
    pool = {}
    for row in Method.objects.filter(status='active', application_id__isnull=True) \
            .values('id', 'name'):
        pool.setdefault(row['name'], []).append(row['id'])
    return pool
