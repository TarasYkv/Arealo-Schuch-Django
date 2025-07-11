from django.contrib.auth.models import AbstractUser
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField
from django.db.models import Sum, Q


class CustomUser(AbstractUser):
    """Erweiterte User-Model für benutzerdefinierte Ampel-Kategorien."""
    use_custom_categories = models.BooleanField(default=False, verbose_name="Benutzerdefinierte Kategorien verwenden")
    enable_ai_keyword_expansion = models.BooleanField(default=False, verbose_name="KI-Keyword-Erweiterung aktivieren")
    
    openai_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="OpenAI API Key")
    anthropic_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="Anthropic API Key")
    google_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="Google API Key")
    youtube_api_key = EncryptedCharField(max_length=255, blank=True, null=True, verbose_name="YouTube API Key")
    
    # Firmeninfo-Felder für Naturmacher
    company_info = models.TextField(blank=True, verbose_name="Firmeninformationen", 
                                   help_text="Beschreibung Ihres Unternehmens, Produkte, Zielgruppe, etc.")
    learning_goals = models.TextField(blank=True, verbose_name="Standard-Lernziele",
                                     help_text="Ihre Standard-Lernziele für Schulungen")
    
    # Profilbild
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, 
                                       verbose_name="Profilbild")
    
    # Super User für Bug-Chat
    is_bug_chat_superuser = models.BooleanField(default=False, verbose_name="Bug-Chat Super User",
                                               help_text="Kann Bug-Chat-Nachrichten empfangen und Super User verwalten")
    receive_bug_reports = models.BooleanField(default=False, verbose_name="Bug-Meldungen empfangen",
                                             help_text="Erhält Bug-Meldungen über das Chat-System")
    receive_anonymous_reports = models.BooleanField(default=False, verbose_name="Anonyme Meldungen empfangen",
                                                   help_text="Erhält auch Bug-Meldungen ohne angemeldeten User")
    
    # Online-Status
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Letzte Aktivität")
    is_online = models.BooleanField(default=False, verbose_name="Online")
    
    # Call-Berechtigungen
    can_make_audio_calls = models.BooleanField(default=True, verbose_name="Darf Audioanrufe tätigen")
    can_make_video_calls = models.BooleanField(default=True, verbose_name="Darf Videoanrufe tätigen")
    can_receive_audio_calls = models.BooleanField(default=True, verbose_name="Darf Audioanrufe empfangen")
    can_receive_video_calls = models.BooleanField(default=True, verbose_name="Darf Videoanrufe empfangen")
    
    def __str__(self):
        return self.username
    
    def get_unread_chat_count(self):
        """Gibt die Anzahl ungelesener Chat-Nachrichten zurück"""
        from chat.models import ChatRoom
        
        total_unread = 0
        for room in self.chat_rooms.all():
            total_unread += room.get_unread_count(self)
        return total_unread
    
    def is_currently_online(self):
        """Prüft ob der User als online betrachtet wird (letzte Aktivität < 5 Minuten)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.last_activity:
            return False
        
        # Check if user was active in the last 5 minutes AND is marked as online
        is_recently_active = timezone.now() - self.last_activity < timedelta(minutes=5)
        
        # If user is not recently active, mark them as offline
        if not is_recently_active and self.is_online:
            self.is_online = False
            self.save(update_fields=['is_online'])
            
        return is_recently_active and self.is_online


class AmpelCategory(models.Model):
    """Benutzerdefinierte Ampel-Kategorien."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='ampel_categories')
    name = models.CharField(max_length=100, verbose_name="Kategorie-Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ampel-Kategorie"
        verbose_name_plural = "Ampel-Kategorien"
        unique_together = ['user', 'name']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"


class CategoryKeyword(models.Model):
    """Suchbegriffe für jede Kategorie."""
    category = models.ForeignKey(AmpelCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=200, verbose_name="Suchbegriff")
    weight = models.PositiveIntegerField(default=1, verbose_name="Gewichtung")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Kategorie-Suchbegriff"
        verbose_name_plural = "Kategorie-Suchbegriffe"
        unique_together = ['category', 'keyword']
        ordering = ['-weight', 'keyword']
    
    def __str__(self):
        return f"{self.category.name}: {self.keyword}"


class UserLoginHistory(models.Model):
    """Trackt Login/Logout Zeiten für Benutzer"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True, verbose_name="Login Zeit")
    logout_time = models.DateTimeField(null=True, blank=True, verbose_name="Logout Zeit")
    session_duration = models.DurationField(null=True, blank=True, verbose_name="Session Dauer")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-Adresse")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    is_active_session = models.BooleanField(default=True, verbose_name="Aktive Session")
    
    class Meta:
        verbose_name = "Benutzer Login Historie"
        verbose_name_plural = "Benutzer Login Historien"
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time.strftime('%d.%m.%Y %H:%M')}"
    
    def get_duration_display(self):
        """Gibt die Session-Dauer in lesbarer Form zurück"""
        if self.session_duration:
            total_seconds = int(self.session_duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "Läuft noch"