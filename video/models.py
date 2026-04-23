import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class VideoProject(models.Model):
    """Hauptprojekt – Container für Charaktere, Bilder und Szenen"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_projects')
    name = models.CharField(max_length=255, verbose_name='Projektname')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Projekt-weite Hintergrundmusik (ein Track für alle Szenen)
    music_prompt = models.TextField(blank=True, default='', verbose_name='Musik-Prompt')
    MUSIC_GENRE_CHOICES = [
        ('', 'Kein Genre'),
        ('cinematic', 'Cinematic / Filmmusik'),
        ('lofi', 'Lo-Fi / Chill'),
        ('corporate', 'Corporate / Business'),
        ('epic', 'Epic / Trailer'),
        ('ambient', 'Ambient / Atmosphärisch'),
        ('happy', 'Happy / Fröhlich'),
        ('sad', 'Sad / Melancholisch'),
        ('dramatic', 'Dramatisch / Spannend'),
        ('romantic', 'Romantisch'),
        ('electronic', 'Electronic / Synth'),
        ('acoustic', 'Akustisch / Gitarre'),
        ('piano', 'Piano / Klavier'),
    ]
    music_genre = models.CharField(max_length=20, blank=True, default='', choices=MUSIC_GENRE_CHOICES, verbose_name='Musik-Genre')
    music_file = models.FileField(upload_to="video/project_music/", blank=True, null=True, verbose_name='Projekt-Musikdatei')
    music_volume = models.FloatField(default=0.3, verbose_name='Musik-Lautstärke (0-1)')

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Video Projekt'
        verbose_name_plural = 'Video Projekte'

    def __str__(self):
        return self.name

    def total_duration(self):
        return sum(s.duration for s in self.scenes.all())


class Character(models.Model):
    """Charakter mit einem Hauptbild plus optional weiteren Referenzbildern."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='characters')
    name = models.CharField(max_length=255, verbose_name='Charaktername')
    image = models.ImageField(upload_to='video/characters/', verbose_name='Hauptbild')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Charakter'
        verbose_name_plural = 'Charaktere'

    def all_image_paths(self):
        """Gibt alle Referenz-Bilder des Charakters zurück (Hauptbild zuerst, dann extra)."""
        paths = []
        if self.image:
            paths.append(self.image.path)
        for img in self.extra_images.all().order_by('order'):
            if img.image:
                paths.append(img.image.path)
        return paths

    def __str__(self):
        return self.name


class CharacterImage(models.Model):
    """Zusätzliche Referenzbilder eines Charakters (verschiedene Winkel, Ausdrücke)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to='video/characters/', verbose_name='Referenzbild')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Charakter-Referenzbild'
        verbose_name_plural = 'Charakter-Referenzbilder'



class Product(models.Model):
    """Optionales Produkt-Bild"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(VideoProject, on_delete=models.CASCADE, related_name='product')
    name = models.CharField(max_length=255, verbose_name='Produktname')
    image = models.ImageField(upload_to='video/products/', verbose_name='Bild')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Produkt'
        verbose_name_plural = 'Produkte'

    def __str__(self):
        return self.name


class StillImage(models.Model):
    """Optionales Stillbild / Referenzbild"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(VideoProject, on_delete=models.CASCADE, related_name='still_image')
    name = models.CharField(max_length=255, verbose_name='Name')
    image = models.ImageField(upload_to='video/stills/', verbose_name='Bild')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stillbild'
        verbose_name_plural = 'Stillbilder'

    def __str__(self):
        return self.name


class GeneratedFrame(models.Model):
    """KI-generiertes Bild (Start- oder Endframe)"""
    FRAME_TYPES = [
        ('start', 'Start-Frame'),
        ('end', 'End-Frame'),
        ('unassigned', 'Nicht zugewiesen'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Wartend'),
        ('generating', 'Wird generiert'),
        ('done', 'Fertig'),
        ('error', 'Fehler'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='frames')
    frame_type = models.CharField(max_length=20, choices=FRAME_TYPES, default='unassigned')
    prompt = models.TextField(verbose_name='Prompt')
    image = models.ImageField(upload_to='video/frames/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Generierter Frame'
        verbose_name_plural = 'Generierte Frames'

    def __str__(self):
        return f"Frame ({self.frame_type}): {self.prompt[:50]}"


class Scene(models.Model):
    """Videoszene: Start-Frame + End-Frame + Prompt → LTX-Video"""
    STATUS_CHOICES = [
        ('pending', 'Wartend'),
        ('generating', 'Wird generiert'),
        ('done', 'Fertig'),
        ('error', 'Fehler'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='scenes')
    order = models.PositiveIntegerField(default=0)

    start_frame = models.ForeignKey(
        GeneratedFrame, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='as_start_in_scenes'
    )
    end_frame = models.ForeignKey(
        GeneratedFrame, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='as_end_in_scenes'
    )
    start_frame_prompt = models.TextField(blank=True, default='', verbose_name='Start-Frame Prompt')
    end_frame_prompt = models.TextField(blank=True, default='', verbose_name='End-Frame Prompt')
    frame_model = models.CharField(max_length=20, default='flux-pulid', blank=True,
        choices=[('nano-banana', 'Nano Banana 2'), ('flux-pulid', 'FLUX + PuLID')],
        verbose_name='Frame-Modell')

    FRAME_STYLE_CHOICES = [
        ('photorealistic', 'Fotorealistisch'),
        ('cinematic', 'Cinematic / Film'),
        ('editorial', 'Editorial / Magazin'),
        ('documentary', 'Dokumentarisch'),
        ('warm-portrait', 'Warmes Portrait'),
        ('anime', 'Anime / Manga'),
        ('illustration', 'Illustration'),
        ('watercolor', 'Aquarell'),
        ('3d-render', '3D Render'),
        ('none', 'Kein Stil (nur Prompt)'),
    ]
    frame_style = models.CharField(max_length=20, choices=FRAME_STYLE_CHOICES, default='photorealistic', verbose_name='Frame-Stil')


    GPU_CHOICES = [
        ('auto', 'Automatisch (API)'),
    ]
    MODEL_CHOICES = [
        ('wan-2.2', 'Wan 2.2'),
        ('wan-2.1', 'Wan 2.1'),
        ('wan-flf2v', 'Wan FLF2V'),
        ('hunyuanvideo', 'HunyuanVideo 1.5'),
        ('hunyuan', 'HunyuanVideo'),
        ('ltx-video', 'LTX-Video 2B'),
        ('ltx-2-distilled', 'LTX-2 Distilled'),
        ('cogvideox', 'CogVideoX 5B'),
        ('hunyuanvideo-rp', 'HunyuanVideo 1.5 I2V (RunPod)'),
    ]
    with_audio = models.BooleanField(default=False, verbose_name="Ambient Audio")
    gpu_choice = models.CharField(max_length=10, choices=GPU_CHOICES, default='L40S', verbose_name='GPU Server')
    model_choice = models.CharField(max_length=30, choices=MODEL_CHOICES, default='hunyuanvideo-rp')
    prompt = models.TextField(blank=True, verbose_name='Szene-Prompt')
    duration = models.PositiveIntegerField(default=5, verbose_name='Dauer (Sek)')

    # Erweiterte Einstellungen
    aspect_ratio = models.CharField(max_length=10, default='auto', verbose_name='Bildformat',
        choices=[('auto', 'Auto'), ('16:9', '16:9 (Querformat)'), ('9:16', '9:16 (Hochformat)'), ('1:1', '1:1 (Quadrat)')])
    guidance_scale = models.FloatField(default=5.0, verbose_name='Guidance Scale')
    num_steps = models.PositiveIntegerField(default=30, verbose_name='Inference Steps')
    seed = models.BigIntegerField(default=42, verbose_name='Seed')
    fps = models.PositiveIntegerField(default=24, verbose_name='FPS',
        choices=[(16, '16 fps'), (24, '24 fps'), (30, '30 fps')])
    negative_prompt = models.TextField(blank=True, default='', verbose_name='Negativer Prompt')

    # Render Stats
    render_duration_sec = models.FloatField(default=0, verbose_name='Render-Dauer (Sek)')
    render_cost = models.FloatField(default=0, verbose_name='Render-Kosten ($)')
    render_progress = models.IntegerField(default=0, verbose_name='Render-Fortschritt (%)')

    # Output
    video_file = models.FileField(upload_to='video/scenes/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    # Quality / Fine-tuning (FLUX + HunyuanVideo)
    QUALITY_PRESET_CHOICES = [
        ('draft', 'Draft (schnell)'),
        ('balanced', 'Balanced (empfohlen)'),
        ('ultra', 'Ultra (beste Qualität)'),
        ('custom', 'Custom'),
    ]
    quality_preset = models.CharField(max_length=20, choices=QUALITY_PRESET_CHOICES, default='balanced', verbose_name='Qualitäts-Preset')

    FLUX_RES_CHOICES = [
        ('1024', '1024×1024 (quadratisch, schnell)'),
        ('1080_h', '1920×1080 (FullHD horizontal)'),
        ('1080_v', '1080×1920 (FullHD vertikal/Shorts)'),
        ('2048', '2048×2048 (2K, langsam)'),
    ]
    flux_resolution = models.CharField(max_length=10, choices=FLUX_RES_CHOICES, default='1024', verbose_name='FLUX-Auflösung')
    flux_steps = models.PositiveIntegerField(default=24, verbose_name='FLUX Inference Steps')
    flux_guidance = models.FloatField(default=3.5, verbose_name='FLUX Guidance (CFG)')
    pulid_cfg = models.FloatField(default=1.0, verbose_name='PuLID Gesichts-Gewicht')

    HUNYUAN_RES_CHOICES = [
        ('480p', '480p (832×480, schnell)'),
        ('720p', '720p (1280×720, hohe Qualität)'),
    ]
    hunyuan_resolution = models.CharField(max_length=10, choices=HUNYUAN_RES_CHOICES, default='480p', verbose_name='Hunyuan-Auflösung')
    hunyuan_steps = models.PositiveIntegerField(default=20, verbose_name='Hunyuan Inference Steps')
    hunyuan_cfg = models.FloatField(default=6.0, verbose_name='Hunyuan CFG')
    hunyuan_flow_shift = models.FloatField(default=7.0, verbose_name='Hunyuan Flow Shift')

    # Text Overlay (ffmpeg post-process, no GPU re-render)
    OVERLAY_POS_V_CHOICES = [('top', 'Oben'), ('middle', 'Mitte'), ('bottom', 'Unten')]
    OVERLAY_POS_H_CHOICES = [('left', 'Links'), ('center', 'Zentriert'), ('right', 'Rechts')]
    OVERLAY_STYLE_CHOICES = [
        ('classic', 'Classic (weiß + schwarze Box)'),
        ('modern', 'Modern (große Outline, keine Box)'),
        ('subtitle', 'Subtitle (klein, unten)'),
        ('title', 'Title (groß, oben)'),
    ]
    text_overlay = models.TextField(blank=True, default='', verbose_name='Text-Overlay')
    overlay_pos_v = models.CharField(max_length=10, choices=OVERLAY_POS_V_CHOICES, default='middle')
    overlay_pos_h = models.CharField(max_length=10, choices=OVERLAY_POS_H_CHOICES, default='center')
    overlay_style = models.CharField(max_length=10, choices=OVERLAY_STYLE_CHOICES, default='modern')

    # Voiceover
    voiceover_text = models.TextField(blank=True, default="", verbose_name="Gesprochener Text")
    audio_model = models.CharField(max_length=60, default="piper-thorsten-medium", blank=True, verbose_name="Audio-Modell")
    voice_reference_audio = models.FileField(upload_to="video/voice_refs/", blank=True, null=True, verbose_name="Voice-Clone Referenz")
    voice_clone = models.ForeignKey('VoiceClone', on_delete=models.SET_NULL, null=True, blank=True, related_name='scenes', verbose_name='Aktive Voice-Clone')
    audio_file = models.FileField(upload_to="video/audio/", blank=True, null=True)

    music_prompt = models.TextField(blank=True, default='', verbose_name='Musik-Prompt')
    MUSIC_GENRE_CHOICES = [
        ('', 'Kein Genre'),
        ('cinematic', 'Cinematic / Filmmusik'),
        ('lofi', 'Lo-Fi / Chill'),
        ('corporate', 'Corporate / Business'),
        ('epic', 'Epic / Trailer'),
        ('ambient', 'Ambient / Atmosphärisch'),
        ('happy', 'Happy / Fröhlich'),
        ('sad', 'Sad / Melancholisch'),
        ('dramatic', 'Dramatisch / Spannend'),
        ('romantic', 'Romantisch'),
        ('electronic', 'Electronic / Synth'),
        ('acoustic', 'Akustisch / Gitarre'),
        ('piano', 'Piano / Klavier'),
    ]
    music_genre = models.CharField(max_length=20, blank=True, default='', choices=MUSIC_GENRE_CHOICES, verbose_name='Musik-Genre')
    music_file = models.FileField(upload_to="video/music/", blank=True, null=True, verbose_name='Musik-Datei')
    music_volume = models.FloatField(default=0.3, verbose_name='Musik-Lautstärke (0-1)')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Szene'
        verbose_name_plural = 'Szenen'

    def __str__(self):
        return f"Szene {self.order + 1}"


class VideoAPIKey(models.Model):
    """API-Key pro User für Video-Generierung"""
    PROVIDER_CHOICES = [
        ('renderful', 'Renderful (Wan, Kling, Seedance)'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_api_keys')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='renderful')
    api_key = models.CharField(max_length=255, verbose_name='API Key')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'provider']
        verbose_name = 'Video API Key'
        verbose_name_plural = 'Video API Keys'

    def __str__(self):
        return f'{self.user.username} - {self.provider}'
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()




class VoiceClone(models.Model):
    """Gespeicherte Voice-Clone Referenzaudios pro User für XTTS-Clone."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voice_clones')
    name = models.CharField(max_length=100, verbose_name='Name der Stimme')
    audio_file = models.FileField(upload_to='video/voice_clones/', verbose_name='Audio-Referenz')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Voice Clone'
        verbose_name_plural = 'Voice Clones'

    def __str__(self):
        return f'{self.name} ({self.user.username})'


class SceneVideo(models.Model):
    """Gerendertes Video für eine Szene — mehrere Versionen möglich."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scene = models.ForeignKey('Scene', on_delete=models.CASCADE, related_name='rendered_videos')
    video_file = models.FileField(upload_to='video/renders/', verbose_name='Video-Datei')
    
    # Render info
    render_duration_sec = models.FloatField(default=0, verbose_name='Render-Dauer (Sek)')
    render_cost = models.FloatField(default=0, verbose_name='Render-Kosten ($)')
    model_used = models.CharField(max_length=30, verbose_name='Verwendetes Modell')
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('rendering', 'Wird gerendert'),
        ('done', 'Fertig'),
        ('error', 'Fehler'),
    ], default='rendering')
    error_message = models.TextField(blank=True)
    
    # Selection
    is_selected = models.BooleanField(default=False, verbose_name='Ausgewählt')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Gerendertes Video'
        verbose_name_plural = 'Gerenderte Videos'

    def __str__(self):
        return f"Render {self.id[:8]} ({self.model_used})"


class GPUServerState(models.Model):
    """Singleton — trackt GPU-Server-Status und Auto-Shutdown."""
    id = models.IntegerField(primary_key=True, default=1)
    is_manually_started = models.BooleanField(default=False, verbose_name='Manuell gestartet')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Letzte Aktivität')
    auto_shutdown_scheduled = models.BooleanField(default=False, verbose_name='Auto-Shutdown geplant')
    auto_shutdown_minutes = models.IntegerField(default=10, verbose_name="Auto-Shutdown Minuten")
    
    class Meta:
        verbose_name = 'GPU Server Status'
        verbose_name_plural = 'GPU Server Status'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
