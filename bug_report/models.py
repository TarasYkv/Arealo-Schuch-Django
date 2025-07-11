from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class BugReport(models.Model):
    """Bug-Meldung mit Chat-Integration"""
    
    # Sender Information
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, 
                              related_name='sent_bug_reports',
                              help_text="Angemeldeter User (null bei anonymen Meldungen)")
    sender_name = models.CharField(max_length=100, blank=True, 
                                  help_text="Name für anonyme Meldungen")
    sender_email = models.EmailField(blank=True, 
                                    help_text="E-Mail für anonyme Meldungen")
    
    # Bug Report Content
    subject = models.CharField(max_length=200, default="Bug-Meldung")
    message = models.TextField(help_text="Beschreibung des Problems")
    
    # System Information
    browser_info = models.TextField(blank=True, help_text="Browser und System-Informationen")
    url = models.URLField(blank=True, help_text="URL wo der Bug aufgetreten ist")
    console_log = models.TextField(blank=True, help_text="Console Log der letzten 100 Zeilen")
    
    # Status
    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('in_progress', 'In Bearbeitung'),
        ('resolved', 'Gelöst'),
        ('closed', 'Geschlossen'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Chat Integration
    chat_room = models.ForeignKey('chat.ChatRoom', on_delete=models.SET_NULL, null=True, blank=True,
                                 help_text="Verknüpfter Chat-Raum für diese Bug-Meldung")
    
    class Meta:
        verbose_name = "Bug-Meldung"
        verbose_name_plural = "Bug-Meldungen"
        ordering = ['-created_at']
    
    def __str__(self):
        sender_name = self.get_sender_name()
        return f"Bug-Meldung von {sender_name}: {self.subject}"
    
    def get_sender_name(self):
        """Gibt den Namen des Senders zurück (User oder anonym)"""
        if self.sender:
            return self.sender.username
        return self.sender_name or "Anonym"
    
    def get_sender_email(self):
        """Gibt die E-Mail des Senders zurück"""
        if self.sender:
            return self.sender.email
        return self.sender_email


class BugReportAttachment(models.Model):
    """Datei-Anhänge für Bug-Meldungen"""
    
    bug_report = models.ForeignKey(BugReport, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='bug_reports/attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255, help_text="Originaler Dateiname")
    file_size = models.PositiveIntegerField(help_text="Dateigröße in Bytes")
    content_type = models.CharField(max_length=100, help_text="MIME-Type der Datei")
    is_screenshot = models.BooleanField(default=False, help_text="Ist ein automatisch erstellter Screenshot")
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Bug-Meldung Anhang"
        verbose_name_plural = "Bug-Meldung Anhänge"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Anhang: {self.filename}"
    
    def get_file_size_display(self):
        """Formatiert die Dateigröße für die Anzeige"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"