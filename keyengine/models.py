from django.db import models
from django.conf import settings
from django.utils import timezone


class KeywordList(models.Model):
    """
    Merkliste für Keywords - User können mehrere Listen haben
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='keyword_lists'
    )

    name = models.CharField(max_length=100)

    # Farbe für visuelle Unterscheidung
    COLOR_CHOICES = [
        ('#10b981', 'Grün'),
        ('#3b82f6', 'Blau'),
        ('#8b5cf6', 'Lila'),
        ('#f59e0b', 'Orange'),
        ('#ef4444', 'Rot'),
        ('#ec4899', 'Pink'),
        ('#fbbf24', 'Gelb'),
        ('#06b6d4', 'Türkis'),
    ]
    color = models.CharField(
        max_length=7,
        choices=COLOR_CHOICES,
        default='#10b981'
    )

    description = models.TextField(blank=True)

    # Archivierung
    is_archived = models.BooleanField(
        default=False,
        help_text="Archivierte Listen werden ausgeblendet"
    )

    # Sortierung
    position = models.IntegerField(default=0)

    # Metadaten
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', '-created_at']
        unique_together = ['user', 'name']
        indexes = [
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['position']),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def keyword_count(self):
        """Anzahl Keywords in dieser Liste"""
        return self.keywords.count()

    def open_count(self):
        """Anzahl offener (nicht erledigter) Keywords"""
        return self.keywords.filter(is_done=False).count()

    def done_count(self):
        """Anzahl erledigter Keywords"""
        return self.keywords.filter(is_done=True).count()


class UserPreference(models.Model):
    """
    User-Präferenzen für KeyEngine
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='keyengine_preferences'
    )

    # Letzte verwendete Liste
    last_used_list = models.ForeignKey(
        KeywordList,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )

    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"Preferences for {self.user.username}"


class SavedKeyword(models.Model):
    """
    Gespeicherte Keywords auf der Merkliste
    """
    # Listen-Zuordnung
    keyword_list = models.ForeignKey(
        KeywordList,
        on_delete=models.CASCADE,
        related_name='keywords'
    )

    # Benutzer-Zuordnung (für Queries - redundant aber praktisch)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_keywords'
    )

    # Keyword-Daten
    keyword = models.CharField(max_length=200)
    intent_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Search Intent (z.B. informational, commercial)"
    )
    description = models.TextField(
        blank=True,
        help_text="Beschreibung des Keywords"
    )

    # Priorität
    PRIORITY_CHOICES = [
        ('high', 'Hoch'),
        ('medium', 'Mittel'),
        ('low', 'Niedrig'),
    ]
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )

    # Status
    is_done = models.BooleanField(
        default=False,
        help_text="Wurde das Keyword bereits bearbeitet?"
    )

    # Optionale Notizen
    notes = models.TextField(blank=True)

    # Metadaten
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['keyword_list', 'keyword']
        indexes = [
            models.Index(fields=['keyword_list', 'is_done']),
            models.Index(fields=['user', 'is_done']),
            models.Index(fields=['user', 'priority']),
            models.Index(fields=['keyword']),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.keyword_list.name})"
