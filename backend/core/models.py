from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        abstract = True


class SluggedModel(TimeStampedModel):
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_slug()
        super().save(*args, **kwargs)

    def _generate_slug(self):
        base_slug = slugify(self.name, allow_unicode=True)
        slug = base_slug
        counter = 1
        while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug


class StatusMixin(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        ACTIVE = 'active', '活跃'
        DEPRECATED = 'deprecated', '已弃用'
        ARCHIVED = 'archived', '已归档'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='状态',
    )

    class Meta:
        abstract = True


def test_fixture_field():
    """「测试夹具」标记字段的单一实现。

    历史：本工厂函数原先只定义在 `apps/knowledge/models.py`（私有 `_test_fixture_field`），
    ResearchGoal / Application / Method / Protocol 四张表用它。**Product 一直缺这个字段**
    ⇒ 公开读路径无法统一排除夹具行，于是 e2e 残留的
    「E2E PO Test Product」「Product 0」直接出现在前台 /products 列表里
    （2026-10-30 首页走查实测：可见 69 个产品里有 2 个是夹具）。

    提到 `core.models` 是为了让 `apps.commerce` 也能复用同一份定义，
    避免两处各写一份 BooleanField 造成语义漂移。
    """
    return models.BooleanField(
        default=False, db_index=True, verbose_name='测试夹具',
        help_text='True 表示此行由自动化测试残留产生，不参与任何对外展示与统计；'
                  '仅作标记，数据不会被删除',
    )
