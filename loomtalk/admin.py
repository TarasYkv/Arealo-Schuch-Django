from django.contrib import admin
from .models import Category, Tag, Topic, Reply, Vote, Mention


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'color', 'order', 'topics_count', 'posts_count', 'is_active']
    list_filter = ['is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'usage_count', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['-usage_count', 'name']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'status', 'replies_count', 'views_count', 'score', 'created_at', 'is_active']
    list_filter = ['status', 'is_active', 'category', 'created_at']
    search_fields = ['title', 'content', 'author__username']
    raw_id_fields = ['author']
    filter_horizontal = ['tags']
    date_hierarchy = 'created_at'
    readonly_fields = ['id', 'slug', 'replies_count', 'views_count', 'score', 'created_at', 'updated_at', 'last_activity_at']
    ordering = ['-created_at']


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ['get_short_content', 'author', 'topic', 'parent', 'score', 'is_active', 'is_solution', 'created_at']
    list_filter = ['is_active', 'is_solution', 'is_edited', 'created_at']
    search_fields = ['content', 'author__username', 'topic__title']
    raw_id_fields = ['author', 'topic', 'parent']
    readonly_fields = ['id', 'score', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    get_short_content.short_description = 'Inhalt'


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'vote_type', 'topic', 'reply', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['user__username']
    raw_id_fields = ['user', 'topic', 'reply']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(Mention)
class MentionAdmin(admin.ModelAdmin):
    list_display = ['mentioned_user', 'mentioning_user', 'topic', 'reply', 'is_read', 'notified_via_chat', 'created_at']
    list_filter = ['is_read', 'notified_via_chat', 'created_at']
    search_fields = ['mentioned_user__username', 'mentioning_user__username']
    raw_id_fields = ['mentioned_user', 'mentioning_user', 'topic', 'reply']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
