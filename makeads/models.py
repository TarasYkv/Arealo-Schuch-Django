from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class Campaign(models.Model):
    """
    Hauptkampagne für Creative-Erstellung
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=200, verbose_name='Kampagnenname')
    description = models.TextField(verbose_name='Beschreibung')
    basic_idea = models.TextField(verbose_name='Grundlegende Creative-Idee')
    detailed_description = models.TextField(
        verbose_name='Detaillierte Beschreibung', 
        blank=True, 
        null=True
    )
    additional_info = models.TextField(
        verbose_name='Zusätzliche Informationen', 
        blank=True, 
        null=True
    )
    web_links = models.TextField(
        verbose_name='Web-Links (ein Link pro Zeile)', 
        blank=True, 
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Kampagne'
        verbose_name_plural = 'Kampagnen'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"


class ReferenceImage(models.Model):
    """
    Referenzbilder für die Campaign
    """
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='reference_images')
    image = models.ImageField(upload_to='makeads/references/', verbose_name='Referenzbild')
    description = models.CharField(
        max_length=500, 
        blank=True, 
        null=True,
        verbose_name='Bildbeschreibung'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Referenzbild'
        verbose_name_plural = 'Referenzbilder'
    
    def __str__(self):
        return f"Referenz für {self.campaign.name}"


class Creative(models.Model):
    """
    KI-generierte Creative-Elemente
    """
    GENERATION_STATUS_CHOICES = [
        ('pending', 'Wird generiert'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
        ('revision', 'Überarbeitung'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='creatives')
    title = models.CharField(max_length=200, verbose_name='Creative-Titel')
    description = models.TextField(verbose_name='Creative-Beschreibung')
    image_url = models.URLField(verbose_name='Bild-URL', blank=True, null=True)
    image_file = models.ImageField(
        upload_to='makeads/creatives/', 
        verbose_name='Creative-Bild',
        blank=True,
        null=True
    )
    text_content = models.TextField(verbose_name='Text-Inhalt')
    ai_prompt_used = models.TextField(
        verbose_name='Verwendeter AI-Prompt',
        blank=True,
        null=True
    )
    generation_status = models.CharField(
        max_length=20,
        choices=GENERATION_STATUS_CHOICES,
        default='pending',
        verbose_name='Generierungsstatus'
    )
    is_favorite = models.BooleanField(default=False, verbose_name='Als Favorit markiert')
    generation_batch = models.PositiveIntegerField(
        default=1,
        verbose_name='Generierungs-Batch'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Creative'
        verbose_name_plural = 'Creatives'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.campaign.name}"
    
    def get_image_url(self):
        """
        Get the best available image URL.
        Prioritizes local file over external URL to avoid 403 errors.
        """
        if self.image_file:
            return self.image_file.url
        elif self.image_url:
            return self.image_url
        return None
    
    def has_valid_image(self):
        """Check if the creative has a valid image available"""
        return bool(self.image_file or self.image_url)


class CreativeRevision(models.Model):
    """
    Überarbeitungen von Creatives
    """
    original_creative = models.ForeignKey(
        Creative, 
        on_delete=models.CASCADE, 
        related_name='revisions'
    )
    revised_creative = models.ForeignKey(
        Creative, 
        on_delete=models.CASCADE, 
        related_name='revision_of'
    )
    revision_prompt = models.TextField(verbose_name='Überarbeitungsanweisung')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Creative-Überarbeitung'
        verbose_name_plural = 'Creative-Überarbeitungen'
    
    def __str__(self):
        return f"Überarbeitung von {self.original_creative.title}"


class AIService(models.Model):
    """
    KI-Service Konfiguration
    """
    SERVICE_TYPES = [
        ('openai', 'OpenAI'),
        ('claude', 'Anthropic Claude'),
        ('google', 'Google AI'),
        ('dalle', 'DALL-E'),
        ('midjourney', 'Midjourney'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Service-Name')
    service_type = models.CharField(
        max_length=20, 
        choices=SERVICE_TYPES,
        verbose_name='Service-Typ'
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    api_endpoint = models.URLField(verbose_name='API-Endpunkt', blank=True, null=True)
    max_tokens = models.PositiveIntegerField(
        default=1000, 
        verbose_name='Maximale Tokens'
    )
    default_model = models.CharField(
        max_length=100, 
        verbose_name='Standard-Modell',
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = 'KI-Service'
        verbose_name_plural = 'KI-Services'
    
    def __str__(self):
        return f"{self.name} ({self.service_type})"


class GenerationJob(models.Model):
    """
    Jobs für asynchrone Creative-Generierung
    """
    JOB_STATUS_CHOICES = [
        ('queued', 'In Warteschlange'),
        ('processing', 'Wird verarbeitet'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='generation_jobs')
    job_type = models.CharField(
        max_length=20,
        choices=[
            ('initial', 'Initiale Generierung'),
            ('more', 'Weitere Generierung'),
            ('revision', 'Überarbeitung'),
        ],
        verbose_name='Job-Typ'
    )
    status = models.CharField(
        max_length=20,
        choices=JOB_STATUS_CHOICES,
        default='queued',
        verbose_name='Status'
    )
    ai_service = models.ForeignKey(
        AIService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='KI-Service'
    )
    target_count = models.PositiveIntegerField(
        default=10,
        verbose_name='Anzahl zu generierender Creatives'
    )
    generated_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Anzahl generierter Creatives'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Fehlermeldung'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Generierungs-Job'
        verbose_name_plural = 'Generierungs-Jobs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.job_type} Job für {self.campaign.name} - {self.status}"