from django.db import models
from django.conf import settings
import uuid
import os


def business_image_path(instance, filename):
    """Pfad für Business-Bilder: loommarket/businesses/<uuid>/<filename>"""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex[:8]}.{ext}"
    return f'loommarket/businesses/{instance.business.id}/{new_filename}'


def mockup_template_path(instance, filename):
    """Pfad für Mockup-Templates: loommarket/templates/<filename>"""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex[:8]}.{ext}"
    return f'loommarket/templates/{new_filename}'


def campaign_image_path(instance, filename):
    """Pfad für Kampagnen-Bilder: loommarket/campaigns/<uuid>/<filename>"""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex[:8]}.{ext}"
    return f'loommarket/campaigns/{instance.id}/{new_filename}'


class Business(models.Model):
    """
    Unternehmen, das über Instagram-Namen hinzugefügt wurde.
    Speichert Profildaten und gefundene Bilder.
    """
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('searching', 'Suche läuft'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loommarket_businesses'
    )

    # Instagram-Daten
    instagram_username = models.CharField(max_length=100, verbose_name="Instagram Username")
    name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Firmenname")
    bio = models.TextField(blank=True, null=True, verbose_name="Bio")
    website = models.URLField(max_length=500, blank=True, null=True, verbose_name="Website")
    follower_count = models.PositiveIntegerField(default=0, verbose_name="Follower")
    profile_picture_url = models.URLField(max_length=1000, blank=True, null=True, verbose_name="Profilbild URL")

    # Impressum-Daten
    impressum_instagram = models.TextField(blank=True, null=True, verbose_name="Impressum (Instagram)")
    impressum_website = models.TextField(blank=True, null=True, verbose_name="Impressum (Website)")
    impressum_website_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Impressum URL")

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unternehmen"
        verbose_name_plural = "Unternehmen"
        ordering = ['-created_at']
        unique_together = ['user', 'instagram_username']

    def __str__(self):
        return f"@{self.instagram_username}" + (f" ({self.name})" if self.name else "")

    @property
    def display_name(self):
        """Zeigt Name oder Instagram-Username"""
        return self.name or f"@{self.instagram_username}"

    @property
    def logo(self):
        """Gibt das als Logo markierte Bild zurück"""
        return self.images.filter(is_logo=True).first()

    @property
    def image_count(self):
        """Anzahl der gespeicherten Bilder"""
        return self.images.count()


class BusinessImage(models.Model):
    """
    Bilder eines Unternehmens (Logos, Produktbilder).
    Gefunden über Bildersuche oder manuell hochgeladen.
    """
    SOURCE_CHOICES = [
        ('search', 'Bildersuche'),
        ('manual', 'Manuell hochgeladen'),
        ('instagram', 'Instagram'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image = models.ImageField(upload_to=business_image_path, verbose_name="Bild")
    source_url = models.URLField(max_length=1000, blank=True, null=True, verbose_name="Quell-URL")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='search')

    is_logo = models.BooleanField(default=False, verbose_name="Ist Logo")
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge")

    # Metadata
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    file_size = models.PositiveIntegerField(default=0, help_text="Dateigröße in Bytes")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Unternehmensbild"
        verbose_name_plural = "Unternehmensbilder"
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"Bild für {self.business.display_name}" + (" (Logo)" if self.is_logo else "")

    def save(self, *args, **kwargs):
        # Wenn als Logo markiert, alle anderen Logos entfernen
        if self.is_logo:
            BusinessImage.objects.filter(
                business=self.business,
                is_logo=True
            ).exclude(pk=self.pk).update(is_logo=False)
        super().save(*args, **kwargs)


class MockupTemplate(models.Model):
    """
    Mockup-Vorlage (z.B. Blumentopf, Tasse, etc.)
    Enthält Blank-Produkt und Beispiel-Gravur.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loommarket_templates'
    )

    name = models.CharField(max_length=100, verbose_name="Vorlagen-Name")
    description = models.TextField(blank=True, null=True, verbose_name="Beschreibung")

    # Bilder
    product_image_blank = models.ImageField(
        upload_to=mockup_template_path,
        verbose_name="Produkt (blank)",
        help_text="Produktbild ohne Gravur"
    )
    product_image_engraved = models.ImageField(
        upload_to=mockup_template_path,
        verbose_name="Produkt (graviert)",
        help_text="Produktbild mit Beispiel-Gravur"
    )

    # Generierungseinstellungen
    default_background_prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name="Standard Hintergrund-Prompt",
        help_text="Beschreibung des Hintergrunds für die KI-Generierung"
    )

    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mockup-Vorlage"
        verbose_name_plural = "Mockup-Vorlagen"
        ordering = ['name']

    def __str__(self):
        return self.name


class MarketingCampaign(models.Model):
    """
    Marketing-Kampagne für ein Unternehmen.
    Enthält generiertes Mockup und verknüpfte Posts.
    """
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('mockup_pending', 'Mockup ausstehend'),
        ('mockup_generating', 'Mockup wird generiert'),
        ('mockup_ready', 'Mockup fertig'),
        ('captions_pending', 'Captions ausstehend'),
        ('ready', 'Bereit zum Posten'),
        ('posted', 'Gepostet'),
        ('failed', 'Fehlgeschlagen'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loommarket_campaigns'
    )

    name = models.CharField(max_length=200, blank=True, null=True, verbose_name="Kampagnenname")

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='campaigns'
    )

    template = models.ForeignKey(
        MockupTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )

    # Design-Bild (Logo oder ausgewähltes Bild)
    design_image = models.ForeignKey(
        BusinessImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns_as_design'
    )

    # Generiertes Mockup
    mockup_image = models.ImageField(
        upload_to=campaign_image_path,
        blank=True,
        null=True,
        verbose_name="Generiertes Mockup"
    )
    mockup_image_story = models.ImageField(
        upload_to=campaign_image_path,
        blank=True,
        null=True,
        verbose_name="Mockup (Story-Format 9:16)"
    )

    # Generierungsoptionen
    background_prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name="Hintergrund-Prompt"
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Marketing-Kampagne"
        verbose_name_plural = "Marketing-Kampagnen"
        ordering = ['-created_at']

    def __str__(self):
        if self.name:
            return self.name
        return f"Kampagne für {self.business.display_name}"

    @property
    def has_mockup(self):
        return bool(self.mockup_image)

    @property
    def has_captions(self):
        return self.captions.exists()


class SocialMediaCaption(models.Model):
    """
    KI-generierte Captions für verschiedene Plattformen.
    """
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('pinterest', 'Pinterest'),
        ('twitter', 'Twitter/X'),
        ('bluesky', 'Bluesky'),
    ]

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='captions'
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)

    title = models.CharField(max_length=200, blank=True, null=True, verbose_name="Titel")
    caption_text = models.TextField(verbose_name="Caption-Text")
    hashtags = models.TextField(blank=True, null=True, verbose_name="Hashtags")

    # Für @-Mentions
    mention_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="@-Mention",
        help_text="Instagram/Twitter Username für Erwähnung"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Social Media Caption"
        verbose_name_plural = "Social Media Captions"
        unique_together = ['campaign', 'platform']

    def __str__(self):
        return f"{self.get_platform_display()} Caption für {self.campaign}"

    @property
    def full_caption(self):
        """Kombiniert Caption-Text mit Hashtags"""
        parts = [self.caption_text]
        if self.hashtags:
            parts.append(self.hashtags)
        return '\n\n'.join(parts)


class SocialMediaPost(models.Model):
    """
    Tatsächliche Social Media Posts.
    Verfolgt Status und externe Post-IDs.
    """
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('scheduled', 'Geplant'),
        ('publishing', 'Wird veröffentlicht'),
        ('published', 'Veröffentlicht'),
        ('failed', 'Fehlgeschlagen'),
    ]

    POST_TYPE_CHOICES = [
        ('feed', 'Feed-Post'),
        ('story', 'Story'),
        ('reel', 'Reel'),
    ]

    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('pinterest', 'Pinterest'),
        ('twitter', 'Twitter/X'),
        ('bluesky', 'Bluesky'),
    ]

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    post_type = models.CharField(max_length=10, choices=POST_TYPE_CHOICES, default='feed')

    # Inhalt
    post_text = models.TextField(verbose_name="Post-Text")
    image_used = models.CharField(
        max_length=10,
        choices=[('feed', 'Feed-Bild'), ('story', 'Story-Bild')],
        default='feed'
    )

    # Veröffentlichung
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    external_post_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Externe Post-ID")
    external_post_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Post-URL")

    # Scheduling
    scheduled_at = models.DateTimeField(blank=True, null=True, verbose_name="Geplant für")
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="Veröffentlicht am")

    # Fehler
    error_message = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Social Media Post"
        verbose_name_plural = "Social Media Posts"
        ordering = ['-created_at']

    def __str__(self):
        post_type_display = self.get_post_type_display()
        return f"{self.get_platform_display()} {post_type_display} - {self.campaign.business.display_name}"
