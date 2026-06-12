from django.contrib import admin
from .models import ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility


@admin.register(ResearchGoal)
class ResearchGoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'summary')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'research_goal', 'sort_order', 'status')
    list_filter = ('status', 'research_goal')
    search_fields = ('name', 'summary')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Method)
class MethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'application', 'cost_band', 'status')
    list_filter = ('status', 'application')
    search_fields = ('name', 'purpose', 'advantages')
    prepopulated_fields = {'slug': ('name',)}


class ProtocolStepInline(admin.TabularInline):
    model = ProtocolStep
    extra = 0
    ordering = ['step_no']


@admin.register(Protocol)
class ProtocolAdmin(admin.ModelAdmin):
    list_display = ('name', 'method', 'version', 'status')
    list_filter = ('status', 'method')
    search_fields = ('name', 'objective')
    inlines = [ProtocolStepInline]


@admin.register(ProtocolStep)
class ProtocolStepAdmin(admin.ModelAdmin):
    list_display = ('protocol', 'step_no', 'title', 'duration_seconds')
    list_filter = ('protocol',)


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ('title', 'journal', 'year', 'doi', 'source_type')
    search_fields = ('title', 'authors', 'doi', 'pmid')
    list_filter = ('source_type', 'year')


@admin.register(Compatibility)
class CompatibilityAdmin(admin.ModelAdmin):
    list_display = ('code', 'scope', 'rule_type', 'severity', 'status')
    list_filter = ('scope', 'rule_type', 'severity', 'status')
    search_fields = ('code', 'summary')
