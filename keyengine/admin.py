from django.contrib import admin
from .models import KeywordList, SavedKeyword, UserPreference


@admin.register(KeywordList)
class KeywordListAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color', 'is_archived', 'keyword_count', 'created_at')
    list_filter = ('is_archived', 'color', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_archived',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SavedKeyword)
class SavedKeywordAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'keyword_list', 'user', 'intent_type', 'priority', 'is_done', 'created_at')
    list_filter = ('keyword_list', 'priority', 'is_done', 'created_at')
    search_fields = ('keyword', 'description', 'notes')
    list_editable = ('priority', 'is_done')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_used_list')
    search_fields = ('user__username',)
