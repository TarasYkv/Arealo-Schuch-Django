from django.contrib import admin
from .models import Category, Prompt


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "category", "visibility", "updated_at")
    list_filter = ("visibility", "category")
    search_fields = ("title", "description", "content")
    autocomplete_fields = ("category",)

