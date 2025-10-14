from django.contrib import admin
from .models import (
    ConnectProfile, SkillCategory, Skill, UserSkill, UserNeed,
    ConnectPost, PostComment, PostLike, ConnectRequest, Connection,
    SkillExchange, ProfileView, ConnectStory, StoryView
)


@admin.register(ConnectProfile)
class ConnectProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_public', 'onboarding_completed', 'karma_score', 'successful_connections', 'created_at')
    list_filter = ('is_public', 'onboarding_completed', 'show_online_status')
    search_fields = ('user__username', 'user__email', 'bio')
    readonly_fields = ('created_at', 'updated_at', 'profile_views_count')
    list_per_page = 50


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'order', 'is_active', 'get_skills_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_predefined', 'is_active', 'usage_count', 'created_by')
    list_filter = ('category', 'is_predefined', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('usage_count', 'created_at')
    ordering = ('-usage_count', 'name')


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ('profile', 'skill', 'level', 'is_offering', 'years_experience', 'created_at')
    list_filter = ('level', 'is_offering', 'skill__category')
    search_fields = ('profile__user__username', 'skill__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['profile', 'skill']


@admin.register(UserNeed)
class UserNeedAdmin(admin.ModelAdmin):
    list_display = ('profile', 'skill', 'urgency', 'is_active', 'created_at')
    list_filter = ('urgency', 'is_active', 'skill__category')
    search_fields = ('profile__user__username', 'skill__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['profile', 'skill']


@admin.register(ConnectPost)
class ConnectPostAdmin(admin.ModelAdmin):
    list_display = ('author', 'post_type', 'likes_count', 'comments_count', 'views_count', 'is_active', 'created_at')
    list_filter = ('post_type', 'is_active', 'created_at')
    search_fields = ('author__user__username', 'content')
    readonly_fields = ('likes_count', 'comments_count', 'views_count', 'created_at', 'updated_at')
    filter_horizontal = ('related_skills',)
    date_hierarchy = 'created_at'


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'post', 'content_preview', 'parent_comment', 'is_edited', 'created_at')
    list_filter = ('is_edited', 'created_at')
    search_fields = ('author__user__username', 'content')
    readonly_fields = ('created_at', 'updated_at')

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Kommentar'


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__content')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(ConnectRequest)
class ConnectRequestAdmin(admin.ModelAdmin):
    list_display = ('from_profile', 'to_profile', 'request_type', 'status', 'related_skill', 'created_at', 'responded_at')
    list_filter = ('status', 'request_type', 'created_at')
    search_fields = ('from_profile__user__username', 'to_profile__user__username', 'message')
    readonly_fields = ('created_at', 'responded_at')
    autocomplete_fields = ['from_profile', 'to_profile', 'related_skill', 'chat_room']
    date_hierarchy = 'created_at'


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('profile_1', 'profile_2', 'chat_room', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('profile_1__user__username', 'profile_2__user__username')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['profile_1', 'profile_2', 'chat_room', 'connect_request']
    date_hierarchy = 'created_at'


@admin.register(SkillExchange)
class SkillExchangeAdmin(admin.ModelAdmin):
    list_display = ('connection', 'skill_offered', 'skill_requested', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'started_at')
    search_fields = ('connection__profile_1__user__username', 'connection__profile_2__user__username', 'notes')
    readonly_fields = ('started_at', 'completed_at')
    autocomplete_fields = ['connection', 'skill_offered', 'skill_requested']


@admin.register(ProfileView)
class ProfileViewAdmin(admin.ModelAdmin):
    list_display = ('viewer', 'viewed_profile', 'viewed_at', 'ip_address')
    list_filter = ('viewed_at',)
    search_fields = ('viewer__user__username', 'viewed_profile__user__username', 'ip_address')
    readonly_fields = ('viewed_at',)
    date_hierarchy = 'viewed_at'


@admin.register(ConnectStory)
class ConnectStoryAdmin(admin.ModelAdmin):
    list_display = ('profile', 'story_type', 'views_count', 'created_at', 'expires_at', 'is_active')
    list_filter = ('story_type', 'created_at')
    search_fields = ('profile__user__username', 'content')
    readonly_fields = ('views_count', 'created_at')
    autocomplete_fields = ['profile']
    date_hierarchy = 'created_at'


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ('viewer', 'story', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('viewer__user__username', 'story__profile__user__username')
    readonly_fields = ('viewed_at',)
    date_hierarchy = 'viewed_at'
