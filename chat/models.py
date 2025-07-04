from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

User = get_user_model()


class ChatRoom(models.Model):
    """
    Represents a chat room/conversation between users
    """
    name = models.CharField(max_length=200, blank=True)
    participants = models.ManyToManyField(User, related_name='chat_rooms', through='ChatRoomParticipant')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)
    is_group_chat = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_rooms')

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        if self.name:
            return self.name
        elif self.is_group_chat:
            return f"Gruppenchat ({self.participants.count()} Teilnehmer)"
        else:
            # Private chat - show other participant's name
            participants = self.participants.all()
            if participants.count() == 2:
                return f"Chat mit {participants.exclude(id=self.created_by.id).first()}"
            return f"Chat {self.id}"

    def get_absolute_url(self):
        return reverse('chat:room_detail', kwargs={'room_id': self.pk})

    def get_other_participant(self, user):
        """Get the other participant in a private chat"""
        if not self.is_group_chat:
            return self.participants.exclude(id=user.id).first()
        return None

    def get_last_message(self):
        """Get the last message in this chat room"""
        return self.messages.first()

    def get_unread_count(self, user):
        """Get count of unread messages for a specific user"""
        try:
            participant = self.participants_through.get(user=user)
            return self.messages.filter(created_at__gt=participant.last_read_at).count()
        except ChatRoomParticipant.DoesNotExist:
            return 0


class ChatRoomParticipant(models.Model):
    """
    Through model for ChatRoom participants with additional fields
    """
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='participants_through')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('chat_room', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.chat_room}"


class ChatMessage(models.Model):
    """
    Represents a message in a chat room
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Bild'),
        ('file', 'Datei'),
        ('system', 'System'),
    ]

    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}..."

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Update last_message_at for the chat room
        if is_new:
            self.chat_room.last_message_at = self.created_at
            self.chat_room.save(update_fields=['last_message_at'])

    def get_formatted_time(self):
        """Get formatted time for display"""
        now = timezone.now()
        if self.created_at.date() == now.date():
            return self.created_at.strftime('%H:%M')
        elif self.created_at.date() == (now - timezone.timedelta(days=1)).date():
            return f"Gestern {self.created_at.strftime('%H:%M')}"
        else:
            return self.created_at.strftime('%d.%m.%Y %H:%M')


class ChatMessageRead(models.Model):
    """
    Track which messages have been read by which users
    """
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user.username} read {self.message.id}"