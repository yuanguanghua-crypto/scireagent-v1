"""
Knowledge Intake API — Accepts knowledge content from the postdoc form.
Creates/updates Research Goals, Applications, Methods, Protocols, and relationships.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException
from django.db import transaction
from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol, ProtocolStep
from apps.knowledge.services.protocol_steps_parser import parse_plain_text_steps
from apps.bridges.models import ProductMethod, MethodProtocol


class AmbiguousKnowledgeName(APIException):
    """同名记录多于一条时拒收（宁 miss 不错配，绝不绑到任意一条）。"""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Ambiguous knowledge name'


def _get_or_create_unique(model, name, defaults):
    """按 name 取或建；同名多行时抛 409，绝不任意绑定。"""
    qs = model.objects.filter(name=name)
    n = qs.count()
    if n > 1:
        raise AmbiguousKnowledgeName(
            detail=f'Ambiguous name "{name}": {n} existing records share it'
        )
    if n == 1:
        return qs.first(), False
    return model.objects.create(name=name, **defaults), True


class KnowledgeIntakeView(EnvelopeMixin, APIView):
    """POST /api/v1/knowledge-intake/ — Submit knowledge content for a product (admin only)."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        with transaction.atomic():
            data = request.data
            product_id = data.get('product_id')

            if not product_id:
                return self.error_response('product_id is required', status_code=400)

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return self.error_response('Product not found', status_code=404)

            # 1. Create/Get Research Goals
            goal_names = data.get('research_goals', [])
            goals = []
            for name in goal_names:
                goal, _ = _get_or_create_unique(
                    ResearchGoal,
                    name,
                    {'summary': '', 'status': 'draft'},
                )
                goals.append(goal)

            # 2. Create/Get Applications
            app_names = data.get('applications', [])
            apps = []
            for name in app_names:
                # Link to first goal if available
                goal = goals[0] if goals else None
                app, _ = _get_or_create_unique(
                    Application,
                    name,
                    {
                        'summary': '',
                        'research_goal': goal,
                        'status': 'draft',
                    },
                )
                apps.append(app)

            # 3. Create/Get Methods
            method_names = data.get('methods', [])
            methods = []
            for name in method_names:
                # Link to first app if available
                app = apps[0] if apps else None
                method, _ = _get_or_create_unique(
                    Method,
                    name,
                    {
                        'summary': '',
                        'purpose': data.get('key_advantages', ''),
                        'advantages': data.get('key_advantages', ''),
                        'limitations': data.get('key_limitations', ''),
                        'application': app,
                        'status': 'draft',
                    },
                )
                methods.append(method)

            # 4. Create ProductMethod bridges
            # ★ 2026-11-26（A-256）：分别计"新建"与"已存在"。
            #   QA 实测（TC-0624）：链接确实加上了（ProductMethod 5456 → 47973），
            #   但保存响应只有 `methods_created`（那是**方法名个数**，不是新建的链接数），
            #   前端 toast 只说 "Saved as draft" ⇒ 用户不知道这次保存到底把什么挂上了。
            method_links_created = 0
            method_links_existing = 0
            for method in methods:
                _, was_created = ProductMethod.objects.get_or_create(
                    product=product, method=method)
                if was_created:
                    method_links_created += 1
                else:
                    method_links_existing += 1

            # 5. Create/Get Protocols
            #
            # ★ A-070（写入路径修正，2026-11-18）三处语义纠正：
            #   ① 步骤不再写进 `objective`。原实现 `objective=data['protocol_steps']`
            #      把「怎么做的」塞进「要达成什么目的」——字段错位，且步骤永远进不了
            #      `protocol_step` 表（生产曾因此积压 443 条被污染的 objective）。
            #      现在步骤只进 ProtocolStep，objective 只由显式字段 `protocol_objective` 承载。
            #   ② 材料落 `materials`（协议级材料清单），不再落 `reagents`
            #      （reagents = 含浓度与用量的试剂，表单没有这个颗粒度，硬塞等于造假）。
            #   ③ `protocols_created` 原为 `len(protocols)`，把**复用**的也算成新建 ⇒
            #      计数虚高。现在如实分开 created / reused，并回报真实 steps 数。
            protocol_names = data.get('protocols', [])

            # 参考来源：表单有两个独立输入框，合成每行一条（与模型 help_text 一致）
            refs = []
            if (data.get('reference_doi') or '').strip():
                refs.append(f"DOI: {data['reference_doi'].strip()}")
            if (data.get('reference_pmid') or '').strip():
                refs.append(f"PMID: {data['reference_pmid'].strip()}")
            references_text = '\n'.join(refs)

            objective_text = (data.get('protocol_objective') or '').strip()
            materials_text = (data.get('protocol_materials') or '').strip()

            protocols = []
            protocols_created = 0
            protocols_reused = 0
            for name in protocol_names:
                if not name:
                    continue
                protocol, created = _get_or_create_unique(
                    Protocol,
                    name,
                    {
                        'objective': objective_text,
                        'materials': materials_text,
                        'reagents': '',
                        'troubleshooting': '',
                        'references': references_text,
                        'version': '1.0',
                        'status': 'draft',
                    },
                )
                protocols.append(protocol)
                if created:
                    protocols_created += 1
                else:
                    protocols_reused += 1

            # 5b. 步骤落 ProtocolStep
            #
            # 表单只有一个 steps 文本框，无法描述「N 个协议各自不同的步骤」。
            # ⇒ 只挂到**第一份**协议，绝不给每个协议复制同一段（那是凭空造出 N-1 份假步骤）。
            #     多协议时在响应 warnings 里明说，让人自己补。
            # 已存在步骤的协议不再追加：重复提交同一表单不该把步骤翻倍。
            step_rows = parse_plain_text_steps(data.get('protocol_steps'))
            steps_created = 0
            warnings = []
            if step_rows:
                if not protocols:
                    warnings.append('protocol_steps 已提供，但 protocols 为空 ⇒ 步骤无处可挂，未写入。')
                else:
                    target = protocols[0]
                    if target.steps.exists():
                        warnings.append(
                            f'协议「{target.name}」已有步骤，本次未覆盖（避免重复追加）。'
                            f'如需更新请先清空该协议步骤后重新提交。'
                        )
                    else:
                        ProtocolStep.objects.bulk_create([
                            ProtocolStep(protocol=target, **row) for row in step_rows
                        ])
                        steps_created = len(step_rows)
                    if len(protocols) > 1:
                        warnings.append(
                            f'共 {len(protocols)} 个协议，但 steps 只有一个来源 ⇒ '
                            f'只写入「{target.name}」，其余协议步骤需逐个补录。'
                        )

            # 6. Create MethodProtocol bridges
            for i, protocol in enumerate(protocols):
                method = methods[i] if i < len(methods) else (methods[0] if methods else None)
                if method:
                    MethodProtocol.objects.get_or_create(method=method, protocol=protocol)

            # 表单收了、但库里没有对应字段的输入 —— 如实回报，不硬塞进别的字段
            unmapped = [f for f in ('protocol_time', 'protocol_difficulty')
                        if (data.get(f) or '').strip()]

            payload = {
                'product_id': product_id,
                'product_name': product.name,
                'goals_created': len(goals),
                'apps_created': len(apps),
                'methods_created': len(methods),
                # ★ 2026-11-26（A-256）：链接层面的增量（前端据此给"链接已添加"的明确提示）
                'method_links_created': method_links_created,
                'method_links_existing': method_links_existing,
                'protocols_created': protocols_created,
                'protocols_reused': protocols_reused,
                'steps_created': steps_created,
                'confidence': data.get('confidence', 'medium'),
            }
            if unmapped:
                payload['unmapped_fields'] = unmapped
                warnings.append(
                    f'{", ".join(unmapped)} 暂无法落库：协议模型没有对应字段（需加字段+迁移）。'
                )
            if warnings:
                payload['warnings'] = warnings
            return self.success_response(payload)
