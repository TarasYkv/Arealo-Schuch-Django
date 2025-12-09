from django.contrib import admin
from .models import QuestionSearch, SavedQuestion


@admin.register(QuestionSearch)
class QuestionSearchAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'user', 'questions_found', 'ai_questions_generated', 'search_date']
    list_filter = ['search_date', 'user']
    search_fields = ['keyword', 'user__username']
    ordering = ['-search_date']
    readonly_fields = ['search_date']


@admin.register(SavedQuestion)
class SavedQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_short', 'keyword', 'intent', 'source', 'is_saved', 'is_used', 'user']
    list_filter = ['intent', 'source', 'is_saved', 'is_used', 'user']
    search_fields = ['question', 'keyword', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    def question_short(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
    question_short.short_description = 'Frage'
