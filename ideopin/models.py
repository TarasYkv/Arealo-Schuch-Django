from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


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

    # Styling-Preset Optionen
    STYLE_PRESET_CHOICES = [
        ('custom', 'Benutzerdefiniert'),
        # Modern & Clean
        ('modern_bold', 'Modern & Bold'),
        ('minimal_clean', 'Minimalistisch'),
        ('tech_futuristic', 'Tech & Futuristisch'),
        ('geometric', 'Geometrisch & Modern'),
        # Elegant & Classic
        ('elegant_serif', 'Elegant & Klassisch'),
        ('luxury_gold', 'Luxuriös & Gold'),
        ('wedding_romantic', 'Romantisch & Hochzeit'),
        ('art_deco', 'Art Déco'),
        # Colorful & Fun
        ('playful_color', 'Verspielt & Bunt'),
        ('neon_glow', 'Neon & Leuchtend'),
        ('pastel_soft', 'Pastell & Sanft'),
        ('gradient_vibrant', 'Gradient & Leuchtend'),
        ('rainbow', 'Regenbogen'),
        # Dark & Moody
        ('dark_contrast', 'Dunkel & Kontrastreich'),
        ('midnight_blue', 'Mitternachtsblau'),
        ('noir_dramatic', 'Film Noir'),
        # Light & Fresh
        ('bright_fresh', 'Hell & Frisch'),
        ('summer_beach', 'Sommer & Strand'),
        ('spring_floral', 'Frühling & Blumen'),
        # Retro & Vintage
        ('vintage_retro', 'Vintage & Retro'),
        ('retro_70s', '70er Jahre'),
        ('polaroid', 'Polaroid'),
        # Business & Professional
        ('professional', 'Business & Professionell'),
        ('corporate_blue', 'Corporate Blau'),
        ('startup', 'Startup Modern'),
        # Special Themes
        ('food_warm', 'Food & Warm'),
        ('nature_organic', 'Natur & Organisch'),
        ('fitness_energy', 'Fitness & Energie'),
        ('kids_playful', 'Kinder & Verspielt'),
        ('christmas', 'Weihnachten'),
        ('halloween', 'Halloween'),
    ]

    # Schriftarten-Optionen
    FONT_CHOICES = [
        # Sans-Serif (Modern)
        ('Arial', 'Arial'),
        ('Helvetica', 'Helvetica'),
        ('Verdana', 'Verdana'),
        ('Tahoma', 'Tahoma'),
        ('Trebuchet MS', 'Trebuchet MS'),
        ('Roboto', 'Roboto'),
        ('Open Sans', 'Open Sans'),
        ('Montserrat', 'Montserrat'),
        ('Lato', 'Lato'),
        ('Poppins', 'Poppins'),
        # Serif (Klassisch)
        ('Times New Roman', 'Times New Roman'),
        ('Georgia', 'Georgia'),
        ('Palatino', 'Palatino'),
        ('Garamond', 'Garamond'),
        ('Playfair Display', 'Playfair Display'),
        ('Merriweather', 'Merriweather'),
        # Display (Auffällig)
        ('Impact', 'Impact'),
        ('Anton', 'Anton'),
        ('Bebas Neue', 'Bebas Neue'),
        ('Oswald', 'Oswald'),
        ('Raleway', 'Raleway'),
        # Script & Handwriting
        ('Brush Script MT', 'Brush Script'),
        ('Comic Sans MS', 'Comic Sans'),
        ('Pacifico', 'Pacifico'),
        ('Dancing Script', 'Dancing Script'),
        ('Great Vibes', 'Great Vibes'),
        # Monospace
        ('Courier New', 'Courier New'),
        ('Consolas', 'Consolas'),
    ]

    # Text-Effekt Optionen
    TEXT_EFFECT_CHOICES = [
        ('none', 'Kein Effekt'),
        # Schatten-Varianten
        ('shadow', 'Schatten (Standard)'),
        ('shadow_soft', 'Weicher Schatten'),
        ('shadow_hard', 'Harter Schatten'),
        ('shadow_long', 'Langer Schatten'),
        ('shadow_3d', '3D-Schatten'),
        # Outline/Kontur
        ('outline', 'Kontur (Standard)'),
        ('outline_thin', 'Dünne Kontur'),
        ('outline_thick', 'Dicke Kontur'),
        ('outline_double', 'Doppelte Kontur'),
        # Leuchteffekte
        ('glow', 'Leuchteffekt'),
        ('glow_neon', 'Neon-Glow'),
        ('glow_soft', 'Sanftes Leuchten'),
        # Hintergrund-Elemente
        ('highlight', 'Textmarker'),
        ('underline', 'Unterstrichen'),
        ('box', 'Box/Kasten'),
        ('rounded_box', 'Abgerundeter Kasten'),
        ('pill', 'Pill-Form'),
        # Spezielle Effekte
        ('frame', 'Rahmen'),
        ('banner', 'Banner/Ribbon'),
        ('badge', 'Badge/Stempel'),
        ('stamp', 'Vintage Stempel'),
        ('torn_paper', 'Zerrissenes Papier'),
        ('gradient_text', 'Gradient-Text'),
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

    # Text-Hintergrund Optionen
    text_background_enabled = models.BooleanField(
        default=True,
        verbose_name="Text-Hintergrund",
        help_text="Text auf einem formpassenden Hintergrund platzieren"
    )
    text_background_creative = models.BooleanField(
        default=True,
        verbose_name="Kreative Formen",
        help_text="Hintergrund kann kreative Formen haben (Banner, Ribbon, etc.)"
    )

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

    # Schritt 5: SEO Titel und Beschreibung
    pin_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pin-Titel",
        help_text="Pinterest Pin-Titel (max. 100 Zeichen)"
    )
    pin_title_ai_generated = models.BooleanField(default=False)

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

    # Erweiterte Styling-Optionen
    style_preset = models.CharField(
        max_length=30,
        choices=STYLE_PRESET_CHOICES,
        default='custom',
        verbose_name="Style-Preset",
        help_text="Vordefinierte Styling-Kombination"
    )
    text_effect = models.CharField(
        max_length=20,
        choices=TEXT_EFFECT_CHOICES,
        default='none',
        verbose_name="Text-Effekt",
        help_text="Visueller Effekt für bessere Lesbarkeit"
    )
    text_secondary_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name="Sekundärfarbe",
        help_text="Für Outline, Schatten oder Akzente"
    )
    auto_font_size = models.BooleanField(
        default=True,
        verbose_name="Automatische Schriftgröße",
        help_text="Schriftgröße automatisch an Textlänge anpassen"
    )
    text_max_width_percent = models.IntegerField(
        default=80,
        verbose_name="Max. Textbreite (%)",
        help_text="Maximale Breite des Texts in Prozent der Bildbreite"
    )
    text_padding = models.IntegerField(
        default=20,
        verbose_name="Text-Padding",
        help_text="Abstand um den Text herum"
    )
    text_line_height = models.FloatField(
        default=1.3,
        verbose_name="Zeilenhöhe",
        help_text="Multiplikator für Zeilenabstand"
    )
    styling_ai_generated = models.BooleanField(
        default=False,
        verbose_name="KI-generiertes Styling"
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

    # Pinterest-Posting Status
    pinterest_posted = models.BooleanField(
        default=False,
        verbose_name="Auf Pinterest gepostet"
    )
    pinterest_pin_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pinterest Pin ID",
        help_text="ID des geposteten Pins auf Pinterest"
    )
    pinterest_board_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pinterest Board ID",
        help_text="ID des Boards auf das der Pin gepostet wurde"
    )
    pinterest_board_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Pinterest Board Name"
    )
    pinterest_posted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Gepostet am"
    )
    pinterest_post_error = models.TextField(
        blank=True,
        verbose_name="Posting-Fehler",
        help_text="Letzter Fehler beim Posten auf Pinterest"
    )

    # Upload-Post Plattform-Tracking
    upload_post_platforms = models.TextField(
        blank=True,
        verbose_name="Upload-Post Plattformen",
        help_text="Komma-getrennte Liste der Plattformen (instagram,facebook,x,linkedin,threads,bluesky)"
    )
    upload_post_posted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Upload-Post gepostet am"
    )

    # Multi-Pin Felder
    pin_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        verbose_name="Anzahl Pins",
        help_text="Anzahl der zu erstellenden Pins (1-7)"
    )

    DISTRIBUTION_MODE_CHOICES = [
        ('manual', 'Manuell'),
        ('auto', 'Automatisch verteilen'),
    ]
    distribution_mode = models.CharField(
        max_length=20,
        choices=DISTRIBUTION_MODE_CHOICES,
        default='manual',
        verbose_name="Verteilungs-Modus",
        help_text="Wie sollen die Pins zeitlich verteilt werden?"
    )
    distribution_interval_days = models.PositiveIntegerField(
        default=2,
        verbose_name="Verteilungs-Intervall (Tage)",
        help_text="Tage zwischen automatisch geplanten Pins"
    )

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

    def get_pinterest_url(self):
        """Gibt die Pinterest-URL des geposteten Pins zurück"""
        if self.pinterest_pin_id:
            return f"https://www.pinterest.com/pin/{self.pinterest_pin_id}/"
        return None

    def get_final_image_for_upload(self):
        """Gibt das finale Bild für den Pinterest-Upload zurück"""
        if self.final_image:
            return self.final_image
        elif self.generated_image:
            return self.generated_image
        return None


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

    IDEOGRAM_MODEL_CHOICES = [
        ('V_2A_TURBO', 'Ideogram 2a Turbo (Beste Text-Integration)'),
        ('V_2A', 'Ideogram 2a (Höchste Qualität)'),
        ('V_2', 'Ideogram 2.0'),
        ('V_2_TURBO', 'Ideogram 2.0 Turbo (Schnell)'),
        ('V_1', 'Ideogram 1.0'),
        ('V_1_TURBO', 'Ideogram 1.0 Turbo'),
    ]

    IDEOGRAM_STYLE_CHOICES = [
        ('REALISTIC', 'Realistisch'),
        ('DESIGN', 'Design/Grafisch'),
        ('RENDER_3D', '3D Render'),
        ('ANIME', 'Anime'),
        ('GENERAL', 'Automatisch'),
    ]

    AI_PROVIDER_CHOICES = [
        ('ideogram', 'Ideogram'),
        ('gemini', 'Google Gemini (Nano Banana)'),
    ]

    GEMINI_MODEL_CHOICES = [
        # Gemini Image Generation (Nano Banana)
        ('gemini-3-pro-image-preview', 'Gemini 3 Pro Image (Nano Banana Pro - Beste Qualität)'),
        ('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image (Nano Banana - Schnell)'),
        # Imagen 4 (High-End Bildgenerierung)
        ('imagen-4.0-ultra-generate-001', 'Imagen 4 Ultra'),
        ('imagen-4.0-generate-001', 'Imagen 4 Standard'),
        ('imagen-4.0-fast-generate-001', 'Imagen 4 Fast'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pin_settings'
    )

    # AI Provider Auswahl
    ai_provider = models.CharField(
        max_length=20,
        choices=AI_PROVIDER_CHOICES,
        default='gemini',
        verbose_name="KI-Anbieter",
        help_text="Gemini (Imagen 3) ist empfohlen für beste Text- und Bildqualität"
    )

    # Ideogram Modell-Einstellung
    ideogram_model = models.CharField(
        max_length=20,
        choices=IDEOGRAM_MODEL_CHOICES,
        default='V_2A_TURBO',
        verbose_name="Ideogram Modell",
        help_text="V_2A_TURBO ist am besten für Text-Overlays geeignet"
    )

    # Ideogram Style-Einstellung
    ideogram_style = models.CharField(
        max_length=20,
        choices=IDEOGRAM_STYLE_CHOICES,
        default='REALISTIC',
        verbose_name="Bild-Style",
        help_text="Realistisch ist für Produkt-Pins am besten geeignet"
    )

    # Gemini Modell-Einstellung
    gemini_model = models.CharField(
        max_length=50,
        choices=GEMINI_MODEL_CHOICES,
        default='gemini-2.5-flash-image',
        verbose_name="Gemini Modell",
        help_text="Nano Banana: Schnell und zuverlässig. Pro-Version hat oft Kapazitätsprobleme."
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

    # Erweiterte Styling-Defaults
    default_style_preset = models.CharField(
        max_length=30,
        choices=PinProject.STYLE_PRESET_CHOICES,
        default='modern_bold',
        verbose_name="Standard Style-Preset"
    )
    default_text_effect = models.CharField(
        max_length=20,
        choices=PinProject.TEXT_EFFECT_CHOICES,
        default='shadow',
        verbose_name="Standard Text-Effekt"
    )
    default_auto_font_size = models.BooleanField(
        default=True,
        verbose_name="Auto-Schriftgröße aktivieren"
    )
    enable_auto_styling = models.BooleanField(
        default=True,
        verbose_name="Auto-Styling aktivieren",
        help_text="KI schlägt automatisch passendes Styling vor"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pin Einstellung"
        verbose_name_plural = "Pin Einstellungen"

    def __str__(self):
        return f"Pin-Einstellungen: {self.user.username}"


class Pin(models.Model):
    """Einzelner Pin innerhalb eines PinProject (für Multi-Pin Feature)"""

    project = models.ForeignKey(
        PinProject,
        on_delete=models.CASCADE,
        related_name='pins'
    )

    # Position/Reihenfolge
    position = models.PositiveIntegerField(
        default=1,
        verbose_name="Position",
        help_text="Reihenfolge des Pins (1-7)"
    )

    # Content (variiert pro Pin)
    overlay_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Overlay-Text",
        help_text="Catchy Pin-Text für dieses Bild"
    )
    overlay_text_ai_generated = models.BooleanField(default=False)

    background_description = models.TextField(
        blank=True,
        verbose_name="Hintergrund-Beschreibung",
        help_text="Individuelle Hintergrund-Beschreibung für diesen Pin"
    )

    # Bilder
    generated_image = models.ImageField(
        upload_to='ideopin/pins/generated/',
        blank=True,
        null=True,
        verbose_name="Generiertes Bild"
    )
    final_image = models.ImageField(
        upload_to='ideopin/pins/final/',
        blank=True,
        null=True,
        verbose_name="Finales Bild mit Text"
    )

    # SEO
    pin_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pin-Titel",
        help_text="Pinterest Pin-Titel (max. 100 Zeichen)"
    )
    pin_title_ai_generated = models.BooleanField(default=False)

    seo_description = models.TextField(
        blank=True,
        max_length=500,
        verbose_name="SEO Pin-Beschreibung",
        help_text="Pinterest-optimierte Beschreibung (max. 500 Zeichen)"
    )
    seo_description_ai_generated = models.BooleanField(default=False)

    # Scheduling
    scheduled_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Geplant für",
        help_text="Datum und Uhrzeit für automatisches Posten"
    )

    # Publishing Status
    pinterest_posted = models.BooleanField(
        default=False,
        verbose_name="Auf Pinterest gepostet"
    )
    pinterest_pin_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pinterest Pin ID"
    )
    pinterest_board_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Pinterest Board ID"
    )
    pinterest_board_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Pinterest Board Name"
    )
    pinterest_posted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Gepostet am"
    )
    pinterest_post_error = models.TextField(
        blank=True,
        verbose_name="Posting-Fehler"
    )

    # Upload-Post Tracking
    upload_post_platforms = models.TextField(
        blank=True,
        verbose_name="Upload-Post Plattformen"
    )
    upload_post_posted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Upload-Post gepostet am"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']
        unique_together = ['project', 'position']
        verbose_name = "Pin"
        verbose_name_plural = "Pins"

    def __str__(self):
        return f"Pin {self.position} von Projekt {self.project.id}"

    def get_final_image_for_upload(self):
        """Gibt das finale Bild für den Pinterest-Upload zurück"""
        if self.final_image:
            return self.final_image
        elif self.generated_image:
            return self.generated_image
        return None

    def get_pinterest_url(self):
        """Gibt die Pinterest-URL des geposteten Pins zurück"""
        if self.pinterest_pin_id:
            return f"https://www.pinterest.com/pin/{self.pinterest_pin_id}/"
        return None
