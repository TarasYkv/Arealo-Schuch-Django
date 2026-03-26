import uuid
from django.db import models
from django.contrib.auth import get_user_model
from videos.models import Video

User = get_user_model()


# === CHOICES ===

PLATFORM_CHOICES = [
    ('tiktok', 'TikTok'),
    ('youtube_shorts', 'YouTube Shorts'),
    ('instagram_reels', 'Instagram Reels'),
    ('instagram_post', 'Instagram Post (1:1)'),
]

VOICE_CHOICES = [
    ('echo', 'Echo (männlich, natürlich)'),
    ('onyx', 'Onyx (männlich, tief)'),
    ('nova', 'Nova (weiblich, warm)'),
    ('alloy', 'Alloy (neutral)'),
    ('shimmer', 'Shimmer (weiblich, sanft)'),
    ('fable', 'Fable (britisch)'),
]

TEMPLATE_CHOICES = [
    # === KLASSISCH ===
    ('job_intro', '👔 Berufsvorstellung'),
    ('product', '🛍️ Produktvideo'),
    ('tutorial', '📚 Tutorial/HowTo'),
    ('facts', '💡 Fakten-Video'),
    ('comparison', '⚖️ Vergleich A vs B'),
    ('top_list', '🏆 Top 5/10 Liste'),
    ('motivation', '🔥 Motivation'),
    ('tips', '✨ Tipps & Tricks'),
    
    # === SOCIAL MEDIA TRENDS ===
    ('hook_story', '🎣 Hook + Story (Viral-Format)'),
    ('pov', '👀 POV-Video'),
    ('storytime', '📖 Storytime'),
    ('hot_take', '🌶️ Hot Take / Meinung'),
    ('before_after', '↔️ Vorher/Nachher'),
    ('myth_busting', '🔍 Mythen aufdecken'),
    ('secrets', '🤫 Geheimtipps'),
    
    # === SPEZIAL-FORMATE ===
    ('news_style', '📺 News-Format'),
    ('story_vertical', '📱 Story (9:16)'),
    ('discussion', '🎭 Diskussion (2 Sprecher)'),
    ('mistakes', '❌ Häufige Fehler'),
    ('day_in_life', '📅 Ein Tag als...'),
    ('unpopular_opinion', '💬 Unpopular Opinion'),
    ('things_nobody_tells', '🤐 Dinge die keiner sagt'),
    ('this_or_that', '🤔 Dies oder Das'),
    
    # === CUSTOM ===
    ('custom', '✍️ Eigener Text'),
]

STATUS_CHOICES = [
    ('pending', 'Wartend'),
    ('script', 'Skript wird generiert'),
    ('audio', 'Audio wird generiert'),
    ('clips', 'Clips werden gesucht'),
    ('rendering', 'Video wird gerendert'),
    ('compressing', 'Video wird komprimiert'),
    ('done', 'Fertig'),
    ('failed', 'Fehlgeschlagen'),
]

TITLE_POSITION_CHOICES = [
    ('top', 'Oben'),
    ('center', 'Mitte'),
    ('bottom', 'Unten'),
]




class VideoProject(models.Model):
    """Ein Video-Generierungs-Projekt"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vidgen_projects')
    batch = models.ForeignKey('BatchJob', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    
    # Eingabe
    title = models.CharField(max_length=200, verbose_name='Titel/Thema')
    
    # Einstellungen
    template = models.CharField(
        max_length=50,
        choices=TEMPLATE_CHOICES,
        default='job_intro',
        verbose_name='Template'
    )
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        default='tiktok',
        verbose_name='Plattform'
    )
    voice = models.CharField(
        max_length=50,
        choices=VOICE_CHOICES,
        default='echo',
        verbose_name='Stimme'
    )
    # Generiertes Audio-File
    audio_file = models.FileField(
        upload_to="audio/",
        blank=True,
        null=True,
        verbose_name="Audio-Datei"
    )


    # Ziel-Dauer in Sekunden
    target_duration = models.IntegerField(
        default=45,
        verbose_name='Video-Dauer (Sekunden)',
        help_text='Ungefähre Zieldauer des Videos'
    )
    
    # Aufloesung
    resolution = models.CharField(
        max_length=10,
        choices=[
            ('1080p', '1080p (Full HD)'),
            ('720p', '720p (HD - schneller)'),
        ],
        default='1080p',
        verbose_name='Aufloesung'
    )

    # Render Backend Auswahl
    render_backend = models.CharField(
        max_length=20,
        choices=[
            ('local', 'Lokal (Hetzner Server)'),
            ('modal', 'Modal Cloud (GPU - schneller)'),
        ],
        default='local',
        verbose_name='Render Backend',
        help_text='Modal ist schneller aber kostet ~2 Cent/Video'
    )

    title_position = models.CharField(
        max_length=20,
        choices=TITLE_POSITION_CHOICES,
        default='top',
        verbose_name='Titel-Position'
    )

    # === ERWEITERTE VIDEO EFFEKTE ===
    
    # Ken Burns Effekt (Zoom/Pan auf Clips)
    ken_burns_effect = models.BooleanField(
        default=False,
        verbose_name='Ken Burns Effekt',
        help_text='Langsames Zoom/Pan auf Clips'
    )
    
    # Color Grading
    color_grading = models.CharField(
        max_length=20,
        choices=[
            ('none', 'Original'),
            ('warm', 'Warm'),
            ('cold', 'Kalt'),
            ('vintage', 'Vintage'),
            ('neon', 'Neon'),
            ('bw', 'Schwarz-Weiss'),
            ('cinematic', 'Cinematic'),
        ],
        default='none',
        verbose_name='Color Grading'
    )
    
    # Animierte Zitate
    quote_text = models.TextField(
        blank=True,
        verbose_name='Zitat-Text',
        help_text='Wird gross animiert eingeblendet'
    )
    quote_author = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Zitat-Autor'
    )
    quote_time = models.IntegerField(
        default=0,
        verbose_name='Zitat Einblenden (Sek)',
        help_text='0 = kein Zitat'
    )
    quote_duration = models.IntegerField(
        default=5,
        verbose_name='Zitat Dauer (Sek)',
        help_text='Wie lange das Zitat angezeigt wird'
    )
    
    # Fakten-Box
    fact_box_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Fakten-Box Text',
        help_text='z.B. 85% der Deutschen...'
    )
    fact_box_time = models.IntegerField(
        default=0,
        verbose_name='Fakten-Box Einblenden (Sek)',
        help_text='0 = keine Fakten-Box'
    )
    fact_box_duration = models.IntegerField(
        default=5,
        verbose_name='Fakten-Box Dauer (Sek)',
        help_text='Wie lange die Fakten-Box angezeigt wird'
    )
    
    # Hintergrundmusik
    # Ausgewählter Musik-Track aus Bibliothek
    selected_music_track = models.ForeignKey(
        "MusicTrack",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        verbose_name="Ausgewählter Musik-Track"
    )
    background_music = models.CharField(
        max_length=50,
        choices=[
            ('none', 'Keine Musik'),
            ('upbeat', 'Upbeat/Froelich'),
            ('corporate', 'Corporate/Business'),
            ('emotional', 'Emotional/Dramatic'),
            ('chill', 'Chill/Relaxed'),
            ('news', 'News/Serious'),
            ('tech', 'Tech/Modern'),
            ('acoustic', 'Acoustic/Warm'),
        ],
        default='none',
        verbose_name='Hintergrundmusik'
    )
    music_volume = models.IntegerField(
        default=20,
        verbose_name='Musik-Lautstaerke (%)',
        help_text='0-100, empfohlen: 15-25'
    )

    # Custom Musik-Beschreibung (optional)
    custom_music_prompt = models.TextField(
        blank=True,
        verbose_name='Musik-Beschreibung',
        help_text='z.B. Epische Orchestermusik mit Trommeln, dramatisch'
    )
    music_duration = models.IntegerField(
        default=0,
        verbose_name='Musik-Laenge (Sek)',
        help_text='0 = automatisch (Video-Laenge)'
    )
    
    # Kosten-Tracking fuer Musik
    cost_music = models.DecimalField(
        max_digits=10, decimal_places=4, default=0, 
        verbose_name='Musik-Generierung Kosten ($)'
    )
    
    # Kosten-Tracking fuer Modal
    cost_modal = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        verbose_name='Modal Cloud Kosten ($)'
    )
    
    # Sound-Effekte
    sound_effects = models.BooleanField(
        default=False,
        verbose_name='Sound-Effekte',
        help_text='Whoosh bei Uebergaengen, Pling bei Punkten'
    )
    
    # Audio-Ducking
    audio_ducking = models.BooleanField(
        default=True,
        verbose_name='Audio-Ducking',
        help_text='Musik leiser wenn gesprochen wird'
    )
    
    # Diskussions-Format (zwei Sprecher)
    is_discussion = models.BooleanField(
        default=False,
        verbose_name='Diskussions-Format',
        help_text='Zwei Personen debattieren'
    )
    speaker1_name = models.CharField(
        max_length=50,
        blank=True,
        default='Pro',
        verbose_name='Sprecher 1 Name'
    )
    speaker1_voice = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Sprecher 1 Stimme'
    )
    speaker2_name = models.CharField(
        max_length=50,
        blank=True,
        default='Contra',
        verbose_name='Sprecher 2 Name'
    )
    speaker2_voice = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Sprecher 2 Stimme'
    )
    
    # === VIDEO EFFEKTE (optional) ===
    
    # Intro-Style
    intro_style = models.CharField(
        max_length=30,
        choices=[
            ('none', 'Kein Intro'),
            ('fade', 'Fade In'),
            ('zoom', 'Zoom In'),
            ('slide_up', 'Slide von unten'),
            ('glitch', 'Glitch Effekt'),
            ('typewriter', 'Typewriter'),
        ],
        default='none',
        verbose_name='Intro-Style'
    )
    
    # Clip-Uebergaenge
    transition_style = models.CharField(
        max_length=30,
        choices=[
            ('cut', 'Harter Schnitt'),
            ('fade', 'Ueberblenden'),
            ('zoom', 'Zoom'),
            ('slide_left', 'Slide Links'),
            ('slide_right', 'Slide Rechts'),
        ],
        default='cut',
        verbose_name='Clip-Uebergaenge'
    )
    
    # Lower Third (Name/Titel Einblendung)
    lower_third_text = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Lower Third Text',
        help_text='z.B. Name | Titel'
    )
    lower_third_start = models.IntegerField(
        default=0,
        verbose_name='Lower Third Start (Sek)',
        help_text='Wann einblenden (0 = aus)'
    )
    
    # Progress Bar
    show_progress_bar = models.BooleanField(
        default=False,
        verbose_name='Progress Bar anzeigen'
    )
    progress_bar_color = models.CharField(
        max_length=20,
        default='#FFD700',
        verbose_name='Progress Bar Farbe'
    )
    
    # Emoji-Animationen
    emoji_animations = models.BooleanField(
        default=False,
        verbose_name='Emoji-Animationen',
        help_text='Emojis bei bestimmten Woertern einblenden'
    )
    
    # Generierter Content
    script = models.TextField(blank=True, verbose_name='Generiertes Skript')
    
    # Eigener Text (optional - überspringt Skript-Generierung)
    custom_script = models.TextField(
        blank=True, 
        verbose_name='Eigener Text',
        help_text='Optional: Eigenen Sprechtext eingeben (überspringt KI-Generierung)'
    )
    
    # Overlay (optional)
    overlay_file = models.FileField(
        upload_to='vidgen/overlays/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Overlay (Bild/Video)'
    )
    overlay_start = models.IntegerField(default=5, verbose_name='Overlay Start (Sekunden)')
    overlay_position = models.CharField(
        max_length=20,
        choices=[
            ('center', 'Mitte'),
            ('top', 'Oben'),
            ('bottom', 'Unten'),
            ('left', 'Links'),
            ('right', 'Rechts'),
            ('top-left', 'Oben Links'),
            ('top-right', 'Oben Rechts'),
            ('bottom-left', 'Unten Links'),
            ('bottom-right', 'Unten Rechts'),
        ],
        default='center',
        verbose_name='Overlay Position'
    )
    overlay_duration = models.IntegerField(
        default=0,
        verbose_name='Overlay Dauer (Sekunden)',
        help_text='0 = bis zum Ende des Videos'
    )
    overlay_width = models.IntegerField(
        default=60,
        verbose_name='Overlay Breite (%)',
        help_text='Prozent der Videobreite (10-100)'
    )
    
    # Wasserzeichen
    watermark = models.BooleanField(default=False, verbose_name='Wasserzeichen hinzufügen')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    progress = models.IntegerField(default=0, verbose_name='Fortschritt (%)')
    error_message = models.TextField(blank=True, verbose_name='Fehlermeldung')
    
    # Kosten-Tracking
    cost_tts = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='TTS Kosten ($)')
    cost_whisper = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='Whisper Kosten ($)')
    cost_script = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='Skript Kosten ($)')
    cost_total = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='Gesamt Kosten ($)')
    
    # Output
    video = models.OneToOneField(
        Video,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vidgen_project',
        verbose_name='Generiertes Video'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Video Projekt'
        verbose_name_plural = 'Video Projekte'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_platform_resolution(self):
        """Gibt die Auflösung für die Plattform zurück"""
        resolutions = {
            'tiktok': (1080, 1920),
            'youtube_shorts': (1080, 1920),
            'instagram_reels': (1080, 1920),
            'instagram_post': (1080, 1080),
        }
        return resolutions.get(self.platform, (1080, 1920))
    
    def calculate_total_cost(self):
        """Berechnet die Gesamtkosten"""
        self.cost_total = self.cost_tts + self.cost_whisper + self.cost_script + self.cost_music + self.cost_modal
        self.save(update_fields=['cost_total'])


class BatchJob(models.Model):
    """Ein Batch-Job für mehrere Videos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vidgen_batches')
    
    # Eingabe
    keywords = models.TextField(verbose_name='Keywords (eine pro Zeile)')
    
    # Einstellungen (werden auf alle Videos angewendet)
    template = models.CharField(
        max_length=50,
        choices=TEMPLATE_CHOICES,
        default='job_intro',
        verbose_name='Template'
    )
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        default='tiktok',
        verbose_name='Plattform'
    )
    voice = models.CharField(
        max_length=50,
        choices=VOICE_CHOICES,
        default='echo',
        verbose_name='Stimme'
    )
    watermark = models.BooleanField(default=False, verbose_name='Wasserzeichen')
    
    # Status
    total_count = models.IntegerField(default=0, verbose_name='Gesamt')
    completed_count = models.IntegerField(default=0, verbose_name='Fertig')
    failed_count = models.IntegerField(default=0, verbose_name='Fehlgeschlagen')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Wartend'),
            ('processing', 'In Bearbeitung'),
            ('done', 'Fertig'),
            ('failed', 'Fehlgeschlagen'),
        ],
        default='pending',
        verbose_name='Status'
    )
    
    # Kosten
    cost_total = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='Gesamt Kosten ($)')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Batch Job'
        verbose_name_plural = 'Batch Jobs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Batch {self.id} ({self.completed_count}/{self.total_count})"
    
    def get_keywords_list(self):
        """Gibt die Keywords als Liste zurück"""
        return [k.strip() for k in self.keywords.strip().split('\n') if k.strip()]
    
    def update_progress(self):
        """Aktualisiert den Fortschritt"""
        self.completed_count = self.projects.filter(status='done').count()
        self.failed_count = self.projects.filter(status='failed').count()
        self.cost_total = sum(p.cost_total for p in self.projects.all())
        
        if self.completed_count + self.failed_count >= self.total_count:
            self.status = 'done' if self.failed_count == 0 else 'failed'
            from django.utils import timezone
            self.completed_at = timezone.now()
        
        self.save()


class PexelsClip(models.Model):
    """Ein heruntergeladener Pexels-Clip für ein Projekt"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='clips')
    
    pexels_id = models.CharField(max_length=50, verbose_name='Pexels Video ID')
    search_query = models.CharField(max_length=200, verbose_name='Suchbegriff')
    
    video_file = models.FileField(
        upload_to='vidgen/clips/%Y/%m/',
        verbose_name='Video-Datei'
    )
    
    duration = models.FloatField(default=0, verbose_name='Dauer (Sekunden)')
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    
    order = models.IntegerField(default=0, verbose_name='Reihenfolge')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Pexels Clip'
        verbose_name_plural = 'Pexels Clips'
        ordering = ['project', 'order']
    
    def __str__(self):
        return f"Clip {self.order + 1} für {self.project.title}"


class MusicTrack(models.Model):
    """Archivierte AI-generierte Musik-Tracks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Generierungs-Info
    prompt = models.TextField(verbose_name='Prompt/Beschreibung')
    mood = models.CharField(max_length=30, blank=True, verbose_name='Stimmung')
    
    # Audio
    audio_file = models.FileField(upload_to='music_library/', verbose_name='Audio-Datei')
    duration = models.IntegerField(default=30, verbose_name='Dauer (Sek)')
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    usage_count = models.IntegerField(default=0, verbose_name='Nutzungen')
    
    # Tags fuer Suche
    tags = models.CharField(max_length=200, blank=True, help_text='Komma-getrennte Tags')
    
    class Meta:
        ordering = ['-usage_count', '-created_at']
        verbose_name = 'Musik-Track'
        verbose_name_plural = 'Musik-Tracks'
    
    def __str__(self):
        return f"{self.mood or 'Custom'}: {self.prompt[:50]}"
