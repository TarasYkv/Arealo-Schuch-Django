from django.db import models
from django.conf import settings


# =============================================================================
# CHOICES - Einstellungsmöglichkeiten
# =============================================================================

GENERATION_MODES = [
    ('background', 'Nur Hintergrund'),
    ('product', 'Produkt auf Hintergrund'),
    ('character', 'Charakter in Szene'),
    ('character_product', 'Charakter + Produkt'),
    ('mockup_text', 'Produkt-Mockup mit Text'),
]

# Mockup-Text Feature - Beschriftungsarten
TEXT_APPLICATION_TYPES = [
    ('gravur', 'Gravur (Eingraviert)'),
    ('druck', 'Druck'),
    ('praegung', 'Prägung'),
    ('relief', 'Relief'),
]

TEXT_POSITIONS = [
    ('center', 'Mitte'),
    ('top', 'Oben'),
    ('bottom', 'Unten'),
    ('custom', 'Automatisch'),
]

FONT_STYLES = [
    ('modern', 'Modern'),
    ('classic', 'Klassisch'),
    ('script', 'Schreibschrift'),
    ('bold', 'Fett'),
    ('minimal', 'Minimalistisch'),
]

TEXT_SIZES = [
    ('small', 'Klein'),
    ('medium', 'Mittel'),
    ('large', 'Groß'),
]

# Mockup Content Types - Text oder Motiv
MOCKUP_CONTENT_TYPES = [
    ('text', 'Text/Beschriftung'),
    ('motif', 'Motiv/Bild'),
]

ASPECT_RATIOS = [
    ('1:1', 'Square (1:1)'),
    ('4:3', 'Standard (4:3)'),
    ('16:9', 'Widescreen (16:9)'),
    ('9:16', 'Portrait (9:16)'),
    ('3:4', 'Portrait (3:4)'),
]

LIGHTING_STYLES = [
    ('studio', 'Studio'),
    ('natural', 'Natürlich'),
    ('dramatic', 'Dramatisch'),
    ('soft', 'Soft Light'),
    ('golden_hour', 'Golden Hour'),
    ('high_key', 'High Key'),
]

PERSPECTIVES = [
    ('frontal', 'Frontal'),
    ('angle_45', '45° Winkel'),
    ('flat_lay', 'Flat Lay'),
    ('floating', 'Schwebend'),
    ('hero', 'Hero Shot'),
    ('macro', 'Makro'),
]

STYLE_PRESETS = [
    ('ecommerce', 'E-Commerce'),
    ('lifestyle', 'Lifestyle'),
    ('minimal', 'Minimalistisch'),
    ('luxury', 'Luxus'),
    ('nature', 'Natur'),
    ('tech', 'Tech'),
]

SHADOW_TYPES = [
    ('none', 'Keiner'),
    ('soft', 'Weich'),
    ('hard', 'Hart'),
    ('reflection', 'Reflektion'),
]

COLOR_MOODS = [
    ('warm', 'Warm'),
    ('neutral', 'Neutral'),
    ('cool', 'Kühl'),
    ('vibrant', 'Lebhaft'),
]

AI_MODELS = [
    ('gemini-2.0-flash-preview-image-generation', 'Gemini 2.0 Flash'),
    ('imagen-3.0-generate-002', 'Imagen 3'),
    ('dall-e-3', 'DALL-E 3'),
    ('dall-e-2', 'DALL-E 2'),
]

QUALITY_LEVELS = [
    ('standard', 'Standard'),
    ('hd', 'HD'),
]


# =============================================================================
# MODELS
# =============================================================================

class Character(models.Model):
    """Gespeicherter Charakter mit mehreren Referenzbildern"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='imageforge_characters'
    )
    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.TextField(
        blank=True,
        verbose_name='Beschreibung',
        help_text='Beschreibung des Charakters für bessere KI-Prompts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Charakter'
        verbose_name_plural = 'Charaktere'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def primary_image(self):
        """Gibt das Hauptbild des Charakters zurück"""
        return self.images.filter(is_primary=True).first() or self.images.first()

    @property
    def image_count(self):
        """Anzahl der Referenzbilder"""
        return self.images.count()


class CharacterImage(models.Model):
    """Einzelnes Referenzbild eines Charakters"""
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='imageforge/characters/%Y/%m/',
        verbose_name='Bild'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Hauptbild'
    )
    upload_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Charakter-Bild'
        verbose_name_plural = 'Charakter-Bilder'
        ordering = ['upload_order', 'created_at']

    def __str__(self):
        return f"Bild für {self.character.name}"

    def save(self, *args, **kwargs):
        # Wenn als Hauptbild markiert, andere Hauptbilder entfernen
        if self.is_primary:
            CharacterImage.objects.filter(
                character=self.character,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ImageGeneration(models.Model):
    """Einzelne Bildgenerierung"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='imageforge_generations'
    )

    # =========================================================================
    # INPUT
    # =========================================================================
    generation_mode = models.CharField(
        max_length=20,
        choices=GENERATION_MODES,
        default='background',
        verbose_name='Modus'
    )

    # Optional: Produktbild (für Modi 'product' und 'character_product')
    product_image = models.ImageField(
        upload_to='imageforge/products/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Produktbild'
    )

    # Optional: Charakter (für Modi 'character' und 'character_product')
    character = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generations',
        verbose_name='Charakter'
    )

    # Optional: Mockup (für Modus 'mockup_text')
    mockup = models.ForeignKey(
        'ProductMockup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scene_generations',
        verbose_name='Produkt-Mockup'
    )

    # Hintergrund-/Szenen-Beschreibung
    background_prompt = models.TextField(
        verbose_name='Szenen-Beschreibung',
        help_text='Beschreiben Sie den gewünschten Hintergrund oder die Szene'
    )

    # =========================================================================
    # EINSTELLUNGEN
    # =========================================================================
    aspect_ratio = models.CharField(
        max_length=10,
        choices=ASPECT_RATIOS,
        default='1:1',
        verbose_name='Format'
    )
    lighting_style = models.CharField(
        max_length=20,
        choices=LIGHTING_STYLES,
        default='natural',
        verbose_name='Lichtstil'
    )
    perspective = models.CharField(
        max_length=20,
        choices=PERSPECTIVES,
        default='frontal',
        verbose_name='Perspektive'
    )
    style_preset = models.CharField(
        max_length=20,
        choices=STYLE_PRESETS,
        default='lifestyle',
        verbose_name='Stil-Preset'
    )
    shadow_type = models.CharField(
        max_length=20,
        choices=SHADOW_TYPES,
        default='soft',
        verbose_name='Schatten'
    )
    color_mood = models.CharField(
        max_length=20,
        choices=COLOR_MOODS,
        default='neutral',
        verbose_name='Farbstimmung'
    )
    quality = models.CharField(
        max_length=20,
        choices=QUALITY_LEVELS,
        default='standard',
        verbose_name='Qualität'
    )

    # KI-Modell
    ai_model = models.CharField(
        max_length=50,
        choices=AI_MODELS,
        default='gemini-2.0-flash-preview-image-generation',
        verbose_name='KI-Modell'
    )

    # =========================================================================
    # OUTPUT
    # =========================================================================
    generated_image = models.ImageField(
        upload_to='imageforge/generated/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Generiertes Bild'
    )
    generation_prompt = models.TextField(
        blank=True,
        verbose_name='Finaler Prompt',
        help_text='Der vollständige Prompt der an die KI gesendet wurde'
    )

    # =========================================================================
    # META
    # =========================================================================
    created_at = models.DateTimeField(auto_now_add=True)
    generation_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Generierungszeit (Sekunden)'
    )
    is_favorite = models.BooleanField(
        default=False,
        verbose_name='Favorit'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Fehlermeldung'
    )

    class Meta:
        verbose_name = 'Bildgenerierung'
        verbose_name_plural = 'Bildgenerierungen'
        ordering = ['-created_at']

    def __str__(self):
        mode_display = dict(GENERATION_MODES).get(self.generation_mode, self.generation_mode)
        return f"{mode_display} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"

    @property
    def is_successful(self):
        """Prüft ob die Generierung erfolgreich war"""
        return bool(self.generated_image) and not self.error_message

    @property
    def mode_display(self):
        """Gibt den deutschen Namen des Modus zurück"""
        return dict(GENERATION_MODES).get(self.generation_mode, self.generation_mode)


class ProductMockup(models.Model):
    """
    Gespeichertes Produkt-Mockup mit Text-Beschriftung.
    Kann für mehrere Szenen-Generierungen wiederverwendet werden.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='imageforge_mockups'
    )

    # Name für einfache Identifikation
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Mockup-Name'
    )

    # Original-Produktbild
    product_image = models.ImageField(
        upload_to='imageforge/mockups/products/%Y/%m/',
        verbose_name='Original-Produktbild'
    )

    # Stil-Referenzbild (optional) - zeigt der KI wie die Beschriftung aussehen soll
    style_reference_image = models.ImageField(
        upload_to='imageforge/mockups/style_refs/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Stil-Referenzbild',
        help_text='Beispielbild das zeigt wie die Beschriftung aussehen soll'
    )

    # Content Type: Text oder Motiv
    content_type = models.CharField(
        max_length=10,
        choices=MOCKUP_CONTENT_TYPES,
        default='text',
        verbose_name='Inhalt-Typ',
        help_text='Text/Beschriftung oder Motiv/Bild'
    )

    # Text-Einstellungen (nur bei content_type='text')
    text_content = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Text/Beschriftung'
    )

    # Motiv-Bild (nur bei content_type='motif')
    motif_image = models.ImageField(
        upload_to='imageforge/mockups/motifs/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Motiv-Bild',
        help_text='Das Motiv/Bild das auf das Produkt soll'
    )
    text_application_type = models.CharField(
        max_length=20,
        choices=TEXT_APPLICATION_TYPES,
        default='druck',
        verbose_name='Beschriftungsart'
    )
    text_position = models.CharField(
        max_length=20,
        choices=TEXT_POSITIONS,
        default='center',
        verbose_name='Text-Position'
    )
    font_style = models.CharField(
        max_length=20,
        choices=FONT_STYLES,
        default='modern',
        verbose_name='Schriftstil'
    )

    # Optionale Zusatzinfos für bessere Prompts
    text_color_hint = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Farbhinweis',
        help_text='z.B. gold, silber, schwarz, weiß'
    )
    text_size_hint = models.CharField(
        max_length=20,
        choices=TEXT_SIZES,
        default='medium',
        verbose_name='Textgröße'
    )

    # Generiertes Mockup-Bild
    mockup_image = models.ImageField(
        upload_to='imageforge/mockups/generated/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Generiertes Mockup'
    )

    # KI-Modell das verwendet wurde
    ai_model = models.CharField(
        max_length=50,
        default='gemini-3-pro-image-preview',
        verbose_name='KI-Modell'
    )

    # Generierter Prompt (für Debugging/Reproduzierbarkeit)
    generation_prompt = models.TextField(
        blank=True,
        verbose_name='Generierungs-Prompt'
    )

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_favorite = models.BooleanField(default=False)
    generation_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Generierungszeit (Sekunden)'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Fehlermeldung'
    )

    class Meta:
        verbose_name = 'Produkt-Mockup'
        verbose_name_plural = 'Produkt-Mockups'
        ordering = ['-updated_at']

    def __str__(self):
        if self.name:
            return self.name
        if self.content_type == 'motif':
            return f"Mockup: Motiv ({self.created_at.strftime('%d.%m.%Y') if self.created_at else 'neu'})"
        return f"Mockup: {self.text_content[:30]}..." if self.text_content else "Mockup (leer)"

    @property
    def is_successful(self):
        """Prüft ob die Generierung erfolgreich war"""
        return bool(self.mockup_image) and not self.error_message

    @property
    def application_type_display(self):
        """Gibt den deutschen Namen der Beschriftungsart zurück"""
        return dict(TEXT_APPLICATION_TYPES).get(self.text_application_type, self.text_application_type)


class StylePreset(models.Model):
    """Benutzerdefinierte Presets"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='imageforge_presets'
    )
    name = models.CharField(max_length=100, verbose_name='Preset-Name')
    settings = models.JSONField(
        default=dict,
        verbose_name='Einstellungen',
        help_text='Alle Einstellungen als JSON gespeichert'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Standard-Preset'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stil-Preset'
        verbose_name_plural = 'Stil-Presets'
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        # Wenn als Standard markiert, andere Standard-Presets des Users entfernen
        if self.is_default:
            StylePreset.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
