from django.contrib.auth.models import AbstractUser
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


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
    
    def __str__(self):
        return self.username


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