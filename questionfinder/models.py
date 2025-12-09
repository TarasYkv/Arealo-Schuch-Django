from django.db import models
from django.conf import settings
from django.utils import timezone


class QuestionSearch(models.Model):
    """
    Speichert Suchanfragen für Analyse und Wiederverwendung
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_searches'
    )
    keyword = models.CharField(max_length=200)
    search_date = models.DateTimeField(default=timezone.now)

    # Statistiken
    questions_found = models.IntegerField(default=0)
    ai_questions_generated = models.IntegerField(default=0)

    class Meta:
        ordering = ['-search_date']
        verbose_name = 'Fragen-Suche'
        verbose_name_plural = 'Fragen-Suchen'
        indexes = [
            models.Index(fields=['user', 'keyword']),
            models.Index(fields=['search_date']),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.user.username})"


class SavedQuestion(models.Model):
    """
    Gespeicherte Fragen mit Kategorisierung
    """
    INTENT_CHOICES = [
        ('informational', 'Informational'),
        ('commercial', 'Commercial'),
        ('transactional', 'Transactional'),
        ('navigational', 'Navigational'),
    ]

    SOURCE_CHOICES = [
        ('google_paa', 'Google People Also Ask'),
        ('google_related', 'Google Related Searches'),
        ('ai_generated', 'KI-Generiert'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_questions'
    )
    search = models.ForeignKey(
        QuestionSearch,
        on_delete=models.CASCADE,
        related_name='questions',
        null=True,
        blank=True
    )

    # Fragen-Daten
    question = models.TextField()
    keyword = models.CharField(max_length=200)

    # Kategorisierung
    intent = models.CharField(
        max_length=20,
        choices=INTENT_CHOICES,
        default='informational'
    )
    category = models.CharField(max_length=100, blank=True)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='google_paa'
    )

    # Status
    is_saved = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    # Metadaten
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['intent', '-created_at']
        verbose_name = 'Gespeicherte Frage'
        verbose_name_plural = 'Gespeicherte Fragen'
        indexes = [
            models.Index(fields=['user', 'keyword']),
            models.Index(fields=['intent']),
            models.Index(fields=['is_saved']),
        ]

    def __str__(self):
        return self.question[:50]
