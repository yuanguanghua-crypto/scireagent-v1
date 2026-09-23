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
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
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
            for method in methods:
                ProductMethod.objects.get_or_create(product=product, method=method)

            # 5. Create/Get Protocols
            protocol_names = data.get('protocols', [])
            protocols = []
            for name in protocol_names:
                if not name:
                    continue
                method = methods[0] if methods else None
                protocol, _ = _get_or_create_unique(
                    Protocol,
                    name,
                    {
                        'objective': data.get('protocol_steps', ''),
                        'reagents': data.get('protocol_materials', ''),
                        'troubleshooting': '',
                        'version': '1.0',
                        'status': 'draft',
                    },
                )
                protocols.append(protocol)

            # 6. Create MethodProtocol bridges
            for i, protocol in enumerate(protocols):
                method = methods[i] if i < len(methods) else (methods[0] if methods else None)
                if method:
                    MethodProtocol.objects.get_or_create(method=method, protocol=protocol)

            return self.success_response({
                'product_id': product_id,
                'product_name': product.name,
                'goals_created': len(goals),
                'apps_created': len(apps),
                'methods_created': len(methods),
                'protocols_created': len(protocols),
                'confidence': data.get('confidence', 'medium'),
            })
