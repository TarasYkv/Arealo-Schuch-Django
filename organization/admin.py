from django.contrib import admin
from .models import (
    Note,
    Event,
    EventParticipant,
    IdeaBoard,
    BoardElement,
    EventReminder,
    BoardMirrorSession,
)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'updated_at', 'is_public']
    list_filter = ['is_public', 'created_at', 'author']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['mentioned_users']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'organizer', 'start_time', 'end_time', 'location', 'priority']
    list_filter = ['priority', 'is_all_day', 'is_recurring', 'start_time']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_time'


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'response', 'response_time']
    list_filter = ['response', 'response_time']
    search_fields = ['event__title', 'user__username']


@admin.register(IdeaBoard)
class IdeaBoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'creator', 'created_at', 'updated_at', 'is_public']
    list_filter = ['is_public', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collaborators']


@admin.register(BoardElement)
class BoardElementAdmin(admin.ModelAdmin):
    list_display = ['board', 'element_type', 'created_by', 'layer_index', 'created_at']
    list_filter = ['element_type', 'created_at']
    search_fields = ['board__title']


@admin.register(EventReminder)
class EventReminderAdmin(admin.ModelAdmin):
    list_display = ['event', 'user', 'reminder_time', 'is_sent', 'sent_at']
    list_filter = ['is_sent', 'reminder_time']
    search_fields = ['event__title', 'user__username']


@admin.register(BoardMirrorSession)
class BoardMirrorSessionAdmin(admin.ModelAdmin):
    list_display = ['board', 'owner', 'is_active', 'started_at', 'ended_at']
    list_filter = ['is_active', 'started_at']
    search_fields = ['board__title', 'owner__username']
    readonly_fields = ['channel_name', 'started_at', 'ended_at']
