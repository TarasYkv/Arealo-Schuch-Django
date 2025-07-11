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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_rooms', null=True, blank=True)
    is_bug_report_room = models.BooleanField(default=False, help_text="Ist ein Bug-Meldungs-Chat-Raum")

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
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    sender_name = models.CharField(max_length=100, blank=True, null=True, help_text="Name für anonyme Nachrichten")
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_system_message = models.BooleanField(default=False, help_text="Ist eine Systemnachricht")
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sender_name = self.sender.username if self.sender else (self.sender_name or "Anonym")
        return f"{sender_name}: {self.content[:50]}..."
    
    def get_sender_name(self):
        """Gibt den Namen des Absenders zurück"""
        if self.sender:
            return self.sender.username
        return self.sender_name or "Anonym"

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


class ChatMessageAttachment(models.Model):
    """
    Represents an attachment to a chat message
    """
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    file_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} - {self.message.id}"

    def get_file_size_display(self):
        """Get human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def is_image(self):
        """Check if file is an image"""
        return self.file_type.startswith('image/')

    def is_video(self):
        """Check if file is a video"""
        return self.file_type.startswith('video/')

    def is_audio(self):
        """Check if file is an audio file"""
        return self.file_type.startswith('audio/')


class Call(models.Model):
    """
    Represents a voice/video call in a chat room
    """
    CALL_TYPES = [
        ('audio', 'Audio'),
        ('video', 'Video'),
    ]
    
    CALL_STATUS = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('connected', 'Connected'),
        ('ended', 'Ended'),
        ('missed', 'Missed'),
        ('rejected', 'Rejected'),
    ]
    
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='calls')
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_calls')
    call_type = models.CharField(max_length=10, choices=CALL_TYPES, default='audio')
    status = models.CharField(max_length=20, choices=CALL_STATUS, default='initiated')
    started_at = models.DateTimeField(auto_now_add=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.caller.username} - {self.get_call_type_display()} Call ({self.status})"
    
    def get_duration_display(self):
        """Get formatted duration"""
        if self.duration:
            total_seconds = int(self.duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"


class CallParticipant(models.Model):
    """
    Represents a participant in a call
    """
    PARTICIPANT_STATUS = [
        ('invited', 'Invited'),
        ('joined', 'Joined'),
        ('left', 'Left'),
        ('rejected', 'Rejected'),
    ]
    
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_participations')
    status = models.CharField(max_length=20, choices=PARTICIPANT_STATUS, default='invited')
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('call', 'user')
    
    def __str__(self):
        return f"{self.user.username} in Call {self.call.id} ({self.status})"