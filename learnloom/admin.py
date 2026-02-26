from django.contrib import admin
from .models import PDFBook, PDFNote, TranslationHighlight, Vocabulary, ReadingProgress, PDFAudioSummary


@admin.register(PDFBook)
class PDFBookAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'page_count', 'file_size_display', 'created_at', 'last_opened_at']
    list_filter = ['category', 'created_at', 'user']
    search_fields = ['title', 'original_filename', 'tags', 'user__username']
    readonly_fields = ['id', 'file_size', 'page_count', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    def file_size_display(self, obj):
        return f"{obj.get_file_size_mb():.2f} MB"
    file_size_display.short_description = "Dateigröße"


@admin.register(PDFNote)
class PDFNoteAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'content_preview', 'page_reference', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['content', 'book__title', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Inhalt"


@admin.register(TranslationHighlight)
class TranslationHighlightAdmin(admin.ModelAdmin):
    list_display = ['original_text_preview', 'translated_text_preview', 'book', 'page_number', 'translation_provider', 'created_at']
    list_filter = ['translation_provider', 'source_language', 'target_language', 'created_at']
    search_fields = ['original_text', 'translated_text', 'book__title']
    readonly_fields = ['id', 'created_at']

    def original_text_preview(self, obj):
        return obj.original_text[:30] + "..." if len(obj.original_text) > 30 else obj.original_text
    original_text_preview.short_description = "Original"

    def translated_text_preview(self, obj):
        return obj.translated_text[:30] + "..." if len(obj.translated_text) > 30 else obj.translated_text
    translated_text_preview.short_description = "Übersetzung"


@admin.register(Vocabulary)
class VocabularyAdmin(admin.ModelAdmin):
    list_display = ['english_word', 'german_translation', 'book', 'is_learned', 'times_reviewed', 'created_at']
    list_filter = ['is_learned', 'created_at', 'book']
    search_fields = ['english_word', 'german_translation', 'book__title']
    readonly_fields = ['id', 'created_at']
    list_editable = ['is_learned']


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ['book', 'current_page', 'zoom_level', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['book__title']
    readonly_fields = ['updated_at']


@admin.register(PDFAudioSummary)
class PDFAudioSummaryAdmin(admin.ModelAdmin):
    list_display = ['summary', 'audio_type', 'section_index', 'voice', 'text_length', 'created_at']
    list_filter = ['audio_type', 'voice', 'created_at']
    search_fields = ['summary__book__title']
    readonly_fields = ['id', 'created_at']
