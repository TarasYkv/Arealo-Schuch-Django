from django.contrib import admin
from .models import ChatRoom, ChatRoomParticipant, ChatMessage, ChatMessageRead


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'created_by', 'is_group_chat', 'created_at', 'last_message_at', 'participant_count')
    list_filter = ('is_group_chat', 'created_at', 'last_message_at')
    search_fields = ('name', 'created_by__username')
    date_hierarchy = 'created_at'
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Teilnehmer'


@admin.register(ChatRoomParticipant)
class ChatRoomParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat_room', 'joined_at', 'last_read_at', 'is_active')
    list_filter = ('is_active', 'joined_at')
    search_fields = ('user__username', 'chat_room__name')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'chat_room', 'message_type', 'content_preview', 'created_at', 'is_edited')
    list_filter = ('message_type', 'created_at', 'is_edited')
    search_fields = ('sender__username', 'content', 'chat_room__name')
    date_hierarchy = 'created_at'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Inhalt'


@admin.register(ChatMessageRead)
class ChatMessageReadAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('user__username', 'message__content')