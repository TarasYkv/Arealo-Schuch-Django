from django.contrib import admin

from .models import ResearchQuery


@admin.register(ResearchQuery)
class ResearchQueryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'owner', 'mode', 'short_question', 'duration_s')
    list_filter = ('mode', 'created_at')
    search_fields = ('question', 'answer', 'owner__username')
    readonly_fields = ('created_at', 'duration_s')

    def short_question(self, obj):
        return (obj.question or '')[:80]
    short_question.short_description = 'Frage'
