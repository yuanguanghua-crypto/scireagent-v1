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

## 两条读路径（B 方案阶段 2）

| 开关 | 读什么 | 何时用 |
|---|---|---|
| `APP_METHOD_READ_FROM_BRIDGE=1`（默认） | `ApplicationMethod` 桥 | 阶段 2 起的正式路径 |
| `APP_METHOD_READ_FROM_BRIDGE=0` | `Method.application` FK + canonical 实时翻译 | 出问题时的回滚路径 |

两条路径在生产实测中输出**完全一致**（迁移 verify 22,219/22,219 通过）。
保留 legacy 是为了「改环境变量即可回滚」，不必重新部署代码。
"""
from django.conf import settings

from apps.knowledge.services.canonical_methods import canonical_by_name


def _read_from_bridge() -> bool:
    return getattr(settings, 'APP_METHOD_READ_FROM_BRIDGE', True)


def resolve_application_methods(app) -> list:
    """返回某个应用实际展示的方法列表 `[{'id','name','slug'}, ...]`。

    默认读 `ApplicationMethod` 桥（B 方案）；开关关掉则退回旧 FK + canonical 翻译。
    """
    if _read_from_bridge():
        return resolve_from_bridge(app)
    return resolve_from_legacy_fk(app)


def resolve_from_bridge(app) -> list:
    """读桥：一次查询，无需 canonical 翻译。

    桥里的 method 全部是 canonical（active 且无 application 归属）——
    迁移时 `merge-active` 已把 10 个带 application 的 active 合并进来，
    `migrate-drafts` 只写入 canonical id。
    """
    links = (app.application_methods
             .select_related('method')
             .order_by('display_order', 'id'))
    out, seen = [], set()
    for link in links:
        m = link.method
        if m.name in seen:
            continue
        seen.add(m.name)
        out.append({'id': m.id, 'name': m.name, 'slug': m.slug})
    return out


def resolve_from_legacy_fk(app) -> list:
    """旧路径：读 `Method.application` FK + `canonical_by_name` 实时翻译。

    **仅作回滚用**。B 方案阶段 3 删除 draft 行后此路径会返回空，
    届时必须改用桥。
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


def application_of_method(method):
    """某个方法「属于」哪个应用 —— M:N 下取 display_order 最小的一条。

    协议页的研究路径（RG→AP→Method）与知识图谱的 AP→Method 边需要**单值**上溯，
    多对多必须选一个代表。用 `display_order` 而不是随机取，保证每次结果稳定。

    受 `APP_METHOD_READ_FROM_BRIDGE` 开关控制：关闭时退回 `Method.application` FK，
    以便回滚路径下 researchPath 的行为与改造前一致（draft 方法也能上溯）。
    """
    if method is None:
        return None
    if not _read_from_bridge():
        return method.application
    link = (method.application_methods.select_related('application')
            .order_by('display_order', 'id').first())
    return link.application if link else None


def method_ids_of_application(application_id):
    """某应用涉及的方法 id 子查询（供 `__in` 过滤用）。"""
    from apps.knowledge.models import ApplicationMethod
    return (ApplicationMethod.objects
            .filter(application_id=application_id)
            .values('method_id'))


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
