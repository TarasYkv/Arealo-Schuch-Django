from django.contrib import admin
from .models import Reference, Collection, ModuleLink, ZoteroAccount


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "reference_count", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("owner",)


class ModuleLinkInline(admin.TabularInline):
    model = ModuleLink
    extra = 1


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ("bibtex_key", "title", "authors", "year", "status", "owner")
    list_filter = ("status", "entry_type", "year", "collection")
    search_fields = ("bibtex_key", "title", "authors", "doi", "abstract", "notes")
    inlines = [ModuleLinkInline]
    readonly_fields = ("added_at", "updated_at", "last_synced")


@admin.register(ZoteroAccount)
class ZoteroAccountAdmin(admin.ModelAdmin):
    list_display = ("owner", "user_id", "library_type", "last_sync", "auto_sync")
