import factory
from apps.knowledge.models import (
    ResearchGoal, Application, ApplicationMethod, Method, Protocol, ProtocolStep,
    Reference, Compatibility,
)


class ResearchGoalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResearchGoal
    name = factory.Sequence(lambda n: f'Research Goal {n}')
    slug = factory.Sequence(lambda n: f'research-goal-{n}')
    summary = factory.Faker('sentence')
    priority = factory.Sequence(lambda n: n)


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application
    name = factory.Sequence(lambda n: f'Application {n}')
    slug = factory.Sequence(lambda n: f'application-{n}')
    research_goal = factory.SubFactory(ResearchGoalFactory)


class MethodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Method
    name = factory.Sequence(lambda n: f'Method {n}')
    slug = factory.Sequence(lambda n: f'method-{n}')
    application = factory.SubFactory(ApplicationFactory)
    # ★ 默认 active：生产上 canonical 方法全是 active，测试工厂贴近现实。
    #   需要 draft 的用例显式传 status='draft'（那些用例本来就在测「draft 不展示」）。
    status = 'active'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """★ 2026-10-30（B 方案阶段 2）：建 Method 时若带 application，同步建桥。

        `Method.application` 的语义已由 `ApplicationMethod` 桥承载，读路径全部改走桥。
        这里自动补桥，使「MethodFactory(application=app)」这一个既有写法在两条读路径下
        语义一致 —— 否则 19 个既有测试会因为只有 FK 没有桥而失败。
        """
        obj = super()._create(model_class, *args, **kwargs)
        # ★ 只有 active 才建桥 —— 桥里**只能**放 canonical（active 且无 application）。
        #   draft 不该出现在应用页（旧路径靠「映射到 canonical 或丢弃」实现，
        #   桥路径下靠「压根不进桥」实现），两者等价。
        if obj.application_id and obj.status == 'active':
            ApplicationMethod.objects.get_or_create(
                application_id=obj.application_id, method_id=obj.id,
                defaults={'source': 'test_factory'})
        return obj


class ProtocolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Protocol
    name = factory.Sequence(lambda n: f'Protocol {n}')
    slug = factory.Sequence(lambda n: f'protocol-{n}')
    version = '1.0'


class ProtocolStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProtocolStep
    protocol = factory.SubFactory(ProtocolFactory)
    step_no = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f'Step {n}')
    body = factory.Faker('paragraph')


class ReferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reference
    title = factory.Sequence(lambda n: f'Reference Paper {n}')
    authors = factory.Faker('name')
    journal = factory.Faker('company')
    year = factory.Sequence(lambda n: 2020 + (n % 10))
    doi = factory.Sequence(lambda n: f'10.1234/ref-{n:06d}')
    pmid = factory.Sequence(lambda n: f'{30000000 + n}')


class CompatibilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Compatibility
    code = factory.Sequence(lambda n: f'COMPAT-{n:04d}')
    scope = 'product-product'
    rule_type = 'compatible'
    severity = 'info'
