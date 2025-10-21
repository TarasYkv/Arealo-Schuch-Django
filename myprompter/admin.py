from django.contrib import admin
from .models import PrompterText


@admin.register(PrompterText)
class PrompterTextAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'word_count', 'is_favorite', 'created_at', 'updated_at']
    list_filter = ['is_favorite', 'created_at', 'updated_at']
    search_fields = ['title', 'content', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'word_count']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Allgemein', {
            'fields': ('user', 'title', 'is_favorite')
        }),
        ('Inhalt', {
            'fields': ('content',)
        }),
        ('Metadaten', {
            'fields': ('word_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
