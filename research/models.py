from django.db import models
from django.conf import settings


MODE_CHOICES = (
    ('rag', 'RAG (aus eigener Bibliothek)'),
    ('council', 'Council (mehrere Modelle)'),
    ('hybrid', 'Hybrid (RAG + Council)'),
)


class ResearchQuery(models.Model):
    """Eine einzelne Anfrage an den Forschungsassistenten."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='research_queries')
    question = models.TextField()
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default='rag')
    models_used = models.JSONField(default=list, blank=True,
                                   help_text='Liste der genutzten Modell-Namen')
    answer = models.TextField(blank=True)
    sources = models.JSONField(default=list, blank=True,
                               help_text='Liste von {title, authors, year, filename, score, text, reference_id?}')
    raw_responses = models.JSONField(default=dict, blank=True,
                                     help_text='Für Council-Mode: Rohantworten pro Modell')
    error = models.TextField(blank=True)
    duration_s = models.FloatField(null=True, blank=True)
    total_cost_usd = models.FloatField(null=True, blank=True,
                                       help_text='Summe der API-Kosten in USD')
    STATUS_CHOICES = (
        ('pending', 'Wartet'),
        ('running', 'Läuft'),
        ('done', 'Fertig'),
        ('failed', 'Fehlgeschlagen'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='done',
                              help_text='Job-Status für asynchrone Verarbeitung')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Form-Parameter, damit der Worker sie verarbeiten kann
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Forschungs-Anfrage'
        verbose_name_plural = 'Forschungs-Anfragen'

    def __str__(self):
        return f'{self.owner.username}: {self.question[:60]}'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('research:query_detail', args=[self.pk])
