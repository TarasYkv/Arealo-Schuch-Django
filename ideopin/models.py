from django.db import models
from django.conf import settings


class PinProject(models.Model):
    """Haupt-Model für einen Pinterest Pin"""

    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('step1', 'Keywords eingegeben'),
        ('step2', 'Text generiert'),
        ('step3', 'Bild erstellt'),
        ('step4', 'Link eingegeben'),
        ('step5', 'SEO erstellt'),
        ('completed', 'Fertig'),
    ]

    FORMAT_CHOICES = [
        ('1000x1500', 'Pinterest Standard (1000x1500)'),
        ('1000x1000', 'Quadratisch (1000x1000)'),
        ('1080x1920', 'Story Format (1080x1920)'),
        ('600x900', 'Kompakt (600x900)'),
    ]

    TEXT_POSITION_CHOICES = [
        ('top', 'Oben'),
        ('center', 'Mitte'),
        ('bottom', 'Unten'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pin_projects'
    )

    # Schritt 1: Keywords
    keywords = models.TextField(
        verbose_name="Keywords",
        help_text="Keywords kommagetrennt oder einzeln"
    )

    # Schritt 2: Text-Overlay
    overlay_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Overlay-Text",
        help_text="Catchy Pin-Text für das Bild"
    )
    overlay_text_ai_generated = models.BooleanField(default=False)

    # Schritt 3: Bild
    product_image = models.ImageField(
        upload_to='ideopin/products/',
        blank=True,
        null=True,
        verbose_name="Produktbild"
    )
    background_description = models.TextField(
        blank=True,
        verbose_name="Hintergrund-Beschreibung",
        help_text="Beschreibung für Hintergrund-Generierung via Ideogram"
    )
    pin_format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='1000x1500',
        verbose_name="Pin-Format"
    )

    # Text-Integration Modus
    text_integration_mode = models.CharField(
        max_length=20,
        choices=[
            ('ideogram', 'Von Ideogram ins Bild integrieren'),
            ('pil', 'Nachträglich mit PIL hinzufügen'),
            ('none', 'Kein Text-Overlay'),
        ],
        default='ideogram',
        verbose_name="Text-Integration",
        help_text="Wie soll der Text ins Bild integriert werden?"
    )

    generated_image = models.ImageField(
        upload_to='ideopin/generated/',
        blank=True,
        null=True,
        verbose_name="Generiertes Bild"
    )
    final_image = models.ImageField(
        upload_to='ideopin/final/',
        blank=True,
        null=True,
        verbose_name="Finales Bild mit Text"
    )

    # Schritt 4: Link
    pin_url = models.URLField(
        blank=True,
        verbose_name="Pin-Link",
        help_text="Zielseite des Pinterest Pins"
    )

    # Schritt 5: SEO Beschreibung
    seo_description = models.TextField(
        blank=True,
        max_length=500,
        verbose_name="SEO Pin-Beschreibung",
        help_text="Pinterest-optimierte Beschreibung (max. 500 Zeichen)"
    )
    seo_description_ai_generated = models.BooleanField(default=False)

    # Text-Overlay Einstellungen
    text_font = models.CharField(
        max_length=100,
        default='Arial',
        blank=True,
        verbose_name="Schriftart"
    )
    text_size = models.IntegerField(
        default=48,
        verbose_name="Schriftgröße"
    )
    text_color = models.CharField(
        max_length=7,
        default='#FFFFFF',
        verbose_name="Textfarbe"
    )
    text_position = models.CharField(
        max_length=20,
        default='center',
        choices=TEXT_POSITION_CHOICES,
        verbose_name="Text-Position"
    )
    text_background_color = models.CharField(
        max_length=7,
        blank=True,
        verbose_name="Hintergrundfarbe",
        help_text="Hex-Color oder leer für transparent"
    )
    text_background_opacity = models.FloatField(
        default=0.7,
        verbose_name="Hintergrund-Transparenz"
    )

    # Metadaten
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Status"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Pin Projekt"
        verbose_name_plural = "Pin Projekte"

    def __str__(self):
        keywords_preview = self.keywords[:30] if self.keywords else "Ohne Keywords"
        return f"Pin: {keywords_preview}... ({self.user.username})"

    def get_format_dimensions(self):
        """Gibt die Dimensionen als Tuple zurück"""
        format_map = {
            '1000x1500': (1000, 1500),
            '1000x1000': (1000, 1000),
            '1080x1920': (1080, 1920),
            '600x900': (600, 900),
        }
        return format_map.get(self.pin_format, (1000, 1500))


class PinSettings(models.Model):
    """User-spezifische Defaults für Text-Styling"""

    TEXT_POSITION_CHOICES = [
        ('top', 'Oben'),
        ('center', 'Mitte'),
        ('bottom', 'Unten'),
    ]

    FORMAT_CHOICES = [
        ('1000x1500', 'Pinterest Standard (1000x1500)'),
        ('1000x1000', 'Quadratisch (1000x1000)'),
        ('1080x1920', 'Story Format (1080x1920)'),
        ('600x900', 'Kompakt (600x900)'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pin_settings'
    )

    default_font = models.CharField(
        max_length=100,
        default='Arial',
        verbose_name="Standard-Schriftart"
    )
    default_text_size = models.IntegerField(
        default=48,
        verbose_name="Standard-Schriftgröße"
    )
    default_text_color = models.CharField(
        max_length=7,
        default='#FFFFFF',
        verbose_name="Standard-Textfarbe"
    )
    default_text_position = models.CharField(
        max_length=20,
        default='center',
        choices=TEXT_POSITION_CHOICES,
        verbose_name="Standard-Position"
    )
    default_text_background_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name="Standard-Hintergrundfarbe"
    )
    default_text_background_opacity = models.FloatField(
        default=0.7,
        verbose_name="Standard-Transparenz"
    )
    default_pin_format = models.CharField(
        max_length=20,
        default='1000x1500',
        choices=FORMAT_CHOICES,
        verbose_name="Standard-Format"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pin Einstellung"
        verbose_name_plural = "Pin Einstellungen"

    def __str__(self):
        return f"Pin-Einstellungen: {self.user.username}"
