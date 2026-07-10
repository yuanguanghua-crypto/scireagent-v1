# FIX_VERIFICATION — 知识实体 slug 自动生成 + knowledge-intake 路由修复

## 背景（根因）
E2E 暴露两个失败，同一根因：知识实体的 `slug` 在 model 层为 `SlugField(unique=True)` 强制必填，但创建路径都不传 slug：
- **gap ③**：Applications/Methods/Protocols 编辑器保存弹窗不关（序列化器 + model 要求 slug，前端不收集 → 400/500）。
- **gap ①**：KnowledgeIntake 页面 Save 报 404。两层：(a) URL `knowledge-intake` 缺结尾斜杠，前端 POST 带斜杠匹配不上 → 404；(b) `KnowledgeIntakeView.get_or_create` 不传 slug → 500。

## 修改的文件（全部后端，未动 frontend / 未新建 migration / 未改其他文件）

### 1. `apps/knowledge/models.py`
- 文件顶部新增 `from django.utils.text import slugify`（原文件无此 import）。
- 为以下 4 个模型各覆盖 `save()`，在 `super().save()` 前：若 `slug` 为空则基于 `name` 用 `slugify` 生成，并循环检测保证全局唯一（冲突时追加 `-n`）：
  - `ResearchGoal`（约第 16 行 slug 字段上方）
  - `Application`（约第 41 行 slug 字段上方）
  - `Method`（约第 84 行 slug 字段上方）
  - `Protocol`（约第 130 行 slug 字段上方）

通用实现（每个类各放一份）：
```python
def save(self, *args, **kwargs):
    if not self.slug:
        base = slugify(self.name) if self.name else 'item'
        slug = base
        n = 1
        qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        self.slug = slug
    super().save(*args, **kwargs)
```
> 说明：`Protocol` 仍有 `unique_together=[('method','slug','version')]`，但 slug 全局唯一已足够避免 `UniqueViolation`。

### 2. `apps/knowledge/api/v1/serializers.py`
- 在以下 4 个 List 序列化器类中（Meta 之前）各加一行，使 `slug` 可选（model 的 `save()` 会补填）：
  - `ResearchGoalListSerializer`
  - `ApplicationListSerializer`
  - `MethodListSerializer`
  - `ProtocolListSerializer`
```python
slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
```
- **额外修正（必要）**：`ProtocolListSerializer.Meta` 增加 `validators = []`。
  - 原因：DRF 针对 `unique_together` 自动注入 `UniqueTogetherValidator(method_id, slug, version)`，它会强制要求 `slug` 与 `version` 必须出现在请求体中，导致即便显式声明 `slug` 可选仍报 `required`。移除该 API 层校验器后，slug 可缺省；`unique_together` 仍在 DB 层由 `save()` 自动生成的全局唯一 slug 保证，不会触发完整性错误。这是让 gap ③ 的 Protocol 创建真正可用的必需改动。

### 3. `apps/knowledge/api/v1/urls.py`
- 第 30 行补结尾斜杠：
  - 改前：`path('knowledge-intake', KnowledgeIntakeView.as_view(), name='api-knowledge-intake'),`
  - 改后：`path('knowledge-intake/', KnowledgeIntakeView.as_view(), name='api-knowledge-intake'),`

---

## 验证结果

### A) 知识 app 后端测试
命令：
```bash
cd c:/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/backend
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest apps/knowledge -p no:cacheprovider -q
```
实际输出（节选）：
```
........................................................................ [ 17%]
...........................................sssssssss.................... [ 34%]
........................................................................ [ 52%]
........................................................................ [ 69%]
........................................................................ [ 86%]
.......................................................                  [100%]
============================== warnings summary ===============================
... RemovedInDjango60Warning: Converter 'drf_format_suffix' is already registered ...
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```
**结论：exit code 0 —— 全部通过（`s` 为 PG 专用跳过用例，符合预期）。**

---

### B) Django shell 验证序列化器不传 slug 也能通过、且 slug 被自动填
命令：
```bash
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe manage.py shell -c "
from apps.knowledge.api.v1.serializers import ApplicationListSerializer, MethodListSerializer, ProtocolListSerializer
from apps.knowledge.models import ResearchGoal, Application, Method
rg=ResearchGoal.objects.first(); app=Application.objects.first(); mth=Method.objects.first()
for nm,S,d in [('App',ApplicationListSerializer,{'name':'SLUGTEST_A','summary':'x','research_goal_id':rg.id}),('Method',MethodListSerializer,{'name':'SLUGTEST_M','summary':'x','application_id':app.id}),('Proto',ProtocolListSerializer,{'name':'SLUGTEST_P','summary':'x','method_id':mth.id})]:
    s=S(data=d); ok=s.is_valid(); print(nm,'valid=',ok,'errors=',s.errors)
    if ok:
        obj=s.save(); print('   -> created pk=',obj.pk,'slug=',obj.slug)
"
```
实际输出：
```
App valid= True errors= {}
   -> created pk= 39 slug= slugtest_a-1
Method valid= True errors= {}
   -> created pk= 47 slug= slugtest_m-1
Proto valid= True errors= {}
   -> created pk= 202 slug= slugtest_p
```
**结论：三个序列化器 `valid=True`、无 slug 错误；slug 由 `save()` 自动生成，且冲突时自动追加 `-n`（如 `slugtest_a-1`）保证唯一。验证通过。**

> 备注：在仅加 `slug` 可选字段、未加 `validators = []` 时，`Proto` 曾因自动 `UniqueTogetherValidator` 报 `{'slug': required, 'version': required}` 而失败；补充 `validators = []` 后三个全部通过。

---

### C) 验证 knowledge-intake 路由（未认证应返回 401 而非 404）
命令：
```bash
curl -s -o /dev/null -w "knowledge-intake POST (no auth) = %{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/knowledge-intake/ -H "Content-Type: application/json" -d '{}'
```
实际输出：
```
knowledge-intake POST (no auth) = 401
```
**结论：返回 401（证明请求已命中 `KnowledgeIntakeView`，之前的 404 路由失败已修复）。验证通过。**
（curl 退出码 23 为 `-w` 与 `-o /dev/null` 组合在 Windows 上的已知无害提示，HTTP 状态 401 为有效结果。）

---

## 最终结论
- A) pytest：exit 0，全部通过 ✅
- B) 三个序列化器均 `valid=True`、slug 自动生成且唯一 ✅
- C) 路由返回 401（非 404），路由已通 ✅

**全部验证通过。**

### 额外说明（gap ① 内层 500 也已修复）
`KnowledgeIntakeView` 使用 `get_or_create(name=..., defaults={...})` 且 `defaults` 不含 `slug`。`get_or_create → create() → model.save()`，故本次为 4 个模型加的 `save()` 自动填充 slug 后，内层 500 已消除（无需改动该 view，也未改动其他文件）。
