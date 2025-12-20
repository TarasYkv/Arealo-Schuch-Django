import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# === CHOICES ===

SCRIPT_TYPE_CHOICES = [
    ('fun_facts', 'Witzige Fakten'),
    ('interesting_facts', 'Interessante Fakten'),
    ('how_to', 'Schritt-für-Schritt Anleitung'),
    ('tips', 'Tipps & Tricks'),
    ('story', 'Spannende Geschichte'),
    ('true_false', 'Wahr/Falsch Spiel'),
    ('qa', 'Frage & Antwort'),
    ('riddle', 'Rätsel'),
    ('expectation_reality', 'Erwartung vs. Realität'),
    ('myth_busting', 'Mythen aufdecken'),
    ('comparison', 'Vergleich A vs B'),
    ('top_list', 'Top 5/10 Liste'),
    ('behind_scenes', 'Hinter den Kulissen'),
    ('challenge', 'Challenge-Format'),
    ('controversial', 'Kontroverse Meinung'),
]

TONE_CHOICES = [
    ('professional', 'Professionell & seriös'),
    ('casual', 'Locker & entspannt'),
    ('humorous', 'Humorvoll & witzig'),
    ('inspiring', 'Inspirierend & motivierend'),
    ('neutral', 'Sachlich & informativ'),
    ('motivating', 'Motivierend & aufbauend'),
    ('provocative', 'Provokant & herausfordernd'),
    ('emotional', 'Emotional & berührend'),
    ('dramatic', 'Dramatisch & spannungsgeladen'),
]

TARGET_AUDIENCE_CHOICES = [
    ('beginner', 'Anfänger'),
    ('intermediate', 'Fortgeschrittene'),
    ('expert', 'Experten'),
    ('general', 'Allgemein'),
    ('young', 'Kinder/Jugendliche'),
]

PLATFORM_CHOICES = [
    ('youtube', 'YouTube'),
    ('tiktok', 'TikTok'),
    ('instagram', 'Instagram Reels'),
    ('linkedin', 'LinkedIn'),
    ('facebook', 'Facebook'),
]

DURATION_CHOICES = [
    (0.25, '15 Sekunden'),
    (0.5, '30 Sekunden'),
    (1.0, '1 Minute'),
    (2.0, '2 Minuten'),
    (3.0, '3 Minuten'),
    (5.0, '5 Minuten'),
    (7.0, '7 Minuten'),
    (10.0, '10 Minuten'),
]

AI_MODEL_CHOICES = [
    # GPT-4o Serie (Stabil & Bewährt)
    ('gpt-4o', 'GPT-4o (Empfohlen)'),
    ('gpt-4o-mini', 'GPT-4o Mini (Schnell)'),
    # GPT-4.1 Serie (April 2025)
    ('gpt-4.1', 'GPT-4.1'),
    ('gpt-4.1-mini', 'GPT-4.1 Mini'),
    ('gpt-4.1-nano', 'GPT-4.1 Nano'),
    # O-Serie Reasoning (April 2025)
    ('o3', 'O3 (Reasoning)'),
    ('o3-pro', 'O3 Pro (Max Reasoning)'),
    ('o4-mini', 'O4 Mini (Schnelles Reasoning)'),
]

# === IMAGE GENERATION CHOICES ===

IMAGE_INTERVAL_CHOICES = [
    (1, 'Alle 1 Sekunde'),
    (2, 'Alle 2 Sekunden'),
    (3, 'Alle 3 Sekunden'),
    (4, 'Alle 4 Sekunden'),
    (5, 'Alle 5 Sekunden'),
    (6, 'Alle 6 Sekunden'),
    (7, 'Alle 7 Sekunden'),
    (8, 'Alle 8 Sekunden'),
]

IMAGE_STYLE_CHOICES = [
    ('realistic', 'Realistisch'),
    ('cinematic', 'Cinematic / Filmisch'),
    ('anime', 'Anime / Manga'),
    ('cartoon', 'Cartoon / Comic'),
    ('3d_render', '3D Render'),
    ('watercolor', 'Aquarell'),
    ('oil_painting', 'Ölgemälde'),
    ('sketch', 'Skizze / Zeichnung'),
    ('minimalist', 'Minimalistisch'),
    ('vintage', 'Vintage / Retro'),
    ('cyberpunk', 'Cyberpunk'),
    ('fantasy', 'Fantasy'),
]

IMAGE_MODEL_CHOICES = [
    ('dall-e-3', 'DALL-E 3 (OpenAI)'),
    ('dall-e-2', 'DALL-E 2 (OpenAI)'),
    ('gemini', 'Imagen 3 (Google Gemini)'),
]

IMAGE_FORMAT_CHOICES = [
    ('1024x1024', '1024x1024 (Quadrat)'),
    ('1792x1024', '1792x1024 (Landscape)'),
    ('1024x1792', '1024x1792 (Portrait)'),
    ('512x512', '512x512 (Klein)'),
]


class VSkriptProject(models.Model):
    """Videoskript-Projekt"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vskript_projects')

    # Eingabe
    title = models.CharField(max_length=200, verbose_name='Titel')
    keyword = models.CharField(max_length=200, verbose_name='Keyword/Thema')
    description = models.TextField(blank=True, verbose_name='Beschreibung (optional)')

    # Einstellungen
    script_type = models.CharField(
        max_length=50,
        choices=SCRIPT_TYPE_CHOICES,
        default='interesting_facts',
        verbose_name='Skript-Art'
    )
    tone = models.CharField(
        max_length=50,
        choices=TONE_CHOICES,
        default='casual',
        verbose_name='Ton'
    )
    target_audience = models.CharField(
        max_length=50,
        choices=TARGET_AUDIENCE_CHOICES,
        default='general',
        verbose_name='Zielgruppe'
    )
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        default='youtube',
        verbose_name='Plattform'
    )
    duration = models.FloatField(
        default=1.0,
        verbose_name='Dauer (Minuten)'
    )
    ai_model = models.CharField(
        max_length=50,
        choices=AI_MODEL_CHOICES,
        default='gpt-4o',
        verbose_name='KI-Modell'
    )

    # Bild-Einstellungen
    image_interval = models.IntegerField(
        choices=IMAGE_INTERVAL_CHOICES,
        default=3,
        verbose_name='Bild-Intervall (Sekunden)'
    )
    image_style = models.CharField(
        max_length=50,
        choices=IMAGE_STYLE_CHOICES,
        default='cinematic',
        verbose_name='Bild-Stil'
    )
    image_model = models.CharField(
        max_length=50,
        choices=IMAGE_MODEL_CHOICES,
        default='dall-e-3',
        verbose_name='Bild-KI-Modell'
    )
    image_format = models.CharField(
        max_length=20,
        choices=IMAGE_FORMAT_CHOICES,
        default='1024x1024',
        verbose_name='Bild-Format'
    )

    # Generiertes Skript
    script = models.TextField(blank=True, verbose_name='Skript')
    word_count = models.IntegerField(default=0, verbose_name='Wortanzahl')
    estimated_duration = models.FloatField(default=0, verbose_name='Geschätzte Dauer')

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'VSkript Projekt'
        verbose_name_plural = 'VSkript Projekte'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.keyword})"

    def get_script_type_display_full(self):
        """Gibt die vollständige Beschreibung der Skript-Art zurück"""
        return dict(SCRIPT_TYPE_CHOICES).get(self.script_type, self.script_type)

    def get_tone_display_full(self):
        """Gibt die vollständige Beschreibung des Tons zurück"""
        return dict(TONE_CHOICES).get(self.tone, self.tone)

    def get_target_audience_display_full(self):
        """Gibt die vollständige Beschreibung der Zielgruppe zurück"""
        return dict(TARGET_AUDIENCE_CHOICES).get(self.target_audience, self.target_audience)

    def get_platform_display_full(self):
        """Gibt die vollständige Beschreibung der Plattform zurück"""
        return dict(PLATFORM_CHOICES).get(self.platform, self.platform)


class VSkriptGenerationLog(models.Model):
    """Logging für KI-Generierungen"""
    project = models.ForeignKey(
        VSkriptProject,
        on_delete=models.CASCADE,
        related_name='generation_logs'
    )
    provider = models.CharField(max_length=50, verbose_name='KI-Provider')
    model = models.CharField(max_length=100, verbose_name='KI-Modell')
    prompt = models.TextField(verbose_name='Prompt')
    response = models.TextField(verbose_name='Antwort')
    tokens_input = models.IntegerField(default=0, verbose_name='Input Tokens')
    tokens_output = models.IntegerField(default=0, verbose_name='Output Tokens')
    duration = models.FloatField(default=0, verbose_name='Dauer (Sekunden)')
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'VSkript Generierung Log'
        verbose_name_plural = 'VSkript Generierung Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Log für {self.project.title} ({self.created_at})"


class VSkriptImage(models.Model):
    """Generierte Bilder für ein Videoskript"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        VSkriptProject,
        on_delete=models.CASCADE,
        related_name='images'
    )

    # Position im Video
    position_seconds = models.FloatField(verbose_name='Position (Sekunden)')
    order = models.IntegerField(default=0, verbose_name='Reihenfolge')

    # Prompt und Generierung
    prompt = models.TextField(verbose_name='Bild-Prompt')
    prompt_enhanced = models.TextField(blank=True, verbose_name='Erweiterter Prompt')

    # Generiertes Bild
    image_url = models.URLField(max_length=500, blank=True, verbose_name='Bild-URL')
    image_file = models.ImageField(
        upload_to='vskript/images/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Bild-Datei'
    )

    # Generierungs-Details
    model_used = models.CharField(max_length=50, verbose_name='Verwendetes Modell')
    style_used = models.CharField(max_length=50, verbose_name='Verwendeter Stil')
    format_used = models.CharField(max_length=20, verbose_name='Verwendetes Format')

    # Status
    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('generating', 'Wird generiert'),
        ('completed', 'Fertig'),
        ('failed', 'Fehlgeschlagen'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    error_message = models.TextField(blank=True, verbose_name='Fehlermeldung')

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'VSkript Bild'
        verbose_name_plural = 'VSkript Bilder'
        ordering = ['project', 'order']

    def __str__(self):
        return f"Bild {self.order + 1} für {self.project.keyword} ({self.position_seconds}s)"
