import factory
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility


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


class ProtocolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Protocol
    name = factory.Sequence(lambda n: f'Protocol {n}')
    slug = factory.Sequence(lambda n: f'protocol-{n}')
    version = '1.0'
    method = factory.SubFactory(MethodFactory)


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
