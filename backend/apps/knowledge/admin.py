from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import (
    ResearchGoal, Application, Method, Protocol,
    ProtocolStep, Reference, Compatibility,
)


# ── Inlines ──────────────────────────────────────────

class ApplicationInline(admin.StackedInline):
    model = Application
    extra = 0
    fields = ('name', 'slug', 'summary', 'sort_order', 'display_priority', 'status')
    prepopulated_fields = {'slug': ('name',)}
    verbose_name = '应用场景'
    verbose_name_plural = '应用场景'


class MethodInline(admin.StackedInline):
    model = Method
    extra = 0
    fields = ('name', 'slug', 'summary', 'cost_band', 'timeline', 'display_priority', 'status')
    prepopulated_fields = {'slug': ('name',)}
    verbose_name = '科研方法'
    verbose_name_plural = '科研方法'


class ProtocolStepInline(admin.TabularInline):
    model = ProtocolStep
    extra = 0
    fields = ('step_no', 'title', 'body', 'duration_seconds', 'warnings')
    verbose_name = '步骤'
    verbose_name_plural = '实验步骤'


class ProtocolInline(admin.StackedInline):
    model = Protocol
    extra = 0
    fields = ('name', 'slug', 'version', 'objective', 'status')
    show_change_link = True
    verbose_name = '实验协议'
    verbose_name_plural = '实验协议'


# ── ResearchGoal ─────────────────────────────────────

@admin.register(ResearchGoal)
class ResearchGoalAdmin(ModelAdmin):
    list_display = ('name', 'priority', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'summary')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ApplicationInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'summary', 'priority', 'status'),
        }),
    )


# ── Application ──────────────────────────────────────

@admin.register(Application)
class ApplicationAdmin(ModelAdmin):
    list_display = ('name', 'research_goal', 'sort_order', 'display_priority', 'status')
    list_filter = ('status', 'research_goal')
    search_fields = ('name', 'summary')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('research_goal',)
    inlines = [MethodInline]
    fieldsets = (
        (None, {
            'fields': ('research_goal', 'name', 'slug', 'summary'),
        }),
        ('展示', {
            'fields': ('sort_order', 'display_priority', 'status'),
        }),
    )


# ── Method ───────────────────────────────────────────

@admin.register(Method)
class MethodAdmin(ModelAdmin):
    list_display = ('name', 'application', 'cost_band', 'timeline', 'display_priority', 'status')
    list_filter = ('status', 'cost_band', 'timeline', 'application')
    search_fields = ('name', 'purpose', 'advantages')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('application',)
    inlines = [ProtocolInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('application', 'name', 'slug', 'status'),
        }),
        ('内容', {
            'fields': ('summary', 'purpose', 'advantages', 'limitations'),
        }),
        ('参数', {
            'fields': ('cost_band', 'timeline', 'display_priority'),
            'classes': ('collapse',),
        }),
    )


# ── Protocol ─────────────────────────────────────────

@admin.register(Protocol)
class ProtocolAdmin(ModelAdmin):
    list_display = ('name', 'method', 'version', 'status', 'published_at')
    list_filter = ('status', 'method')
    search_fields = ('name', 'objective')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('method',)
    inlines = [ProtocolStepInline]
    fieldsets = (
        ('基本信息', {
            'fields': ('method', 'name', 'slug', 'version', 'status'),
        }),
        ('内容', {
            'fields': ('objective', 'principle', 'materials', 'reagents', 'equipment'),
        }),
        ('详细信息', {
            'fields': ('troubleshooting', 'expected_results', 'references'),
            'classes': ('collapse',),
        }),
        ('时间', {
            'fields': ('published_at', 'superseded_at'),
            'classes': ('collapse',),
        }),
    )


# ── ProtocolStep (独立，可选) ────────────────────────

@admin.register(ProtocolStep)
class ProtocolStepAdmin(ModelAdmin):
    list_display = ('protocol', 'step_no', 'title', 'duration_seconds')
    list_filter = ('protocol',)
    search_fields = ('title', 'body')
    autocomplete_fields = ('protocol',)
    fieldsets = (
        (None, {
            'fields': ('protocol', 'step_no', 'title'),
        }),
        ('内容', {
            'fields': ('body', 'duration_seconds', 'warnings', 'required_materials'),
        }),
    )


# ── Reference ────────────────────────────────────────

@admin.register(Reference)
class ReferenceAdmin(ModelAdmin):
    list_display = ('title', 'journal', 'year', 'doi', 'pmid', 'source_type')
    search_fields = ('title', 'authors', 'doi', 'pmid')
    list_filter = ('source_type', 'year')
    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'authors', 'journal', 'year', 'source_type'),
        }),
        ('标识符', {
            'fields': ('doi', 'pmid', 'url'),
        }),
        ('内容', {
            'fields': ('citation_text',),
            'classes': ('collapse',),
        }),
    )


# ── Compatibility ────────────────────────────────────

@admin.register(Compatibility)
class CompatibilityAdmin(ModelAdmin):
    list_display = ('code', 'scope', 'rule_type', 'severity', 'status')
    list_filter = ('scope', 'rule_type', 'severity', 'status')
    search_fields = ('code', 'summary')
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'scope', 'rule_type', 'severity', 'status'),
        }),
        ('规则定义', {
            'fields': ('summary', 'expression_json'),
        }),
    )
