# mycut/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class EditProject(models.Model):
    """
    MyCut Video-Bearbeitungsprojekt.
    Speichert den Zustand eines Editing-Projekts.
    """
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('processing', 'Wird verarbeitet'),
        ('exporting', 'Wird exportiert'),
        ('completed', 'Abgeschlossen'),
        ('error', 'Fehler'),
    ]

    QUALITY_CHOICES = [
        ('720p', '720p HD'),
        ('1080p', '1080p Full HD'),
        ('4k', '4K Ultra HD'),
    ]

    FORMAT_CHOICES = [
        ('mp4', 'MP4 (H.264)'),
        ('webm', 'WebM (VP9)'),
    ]

    # Beziehungen
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mycut_projects'
    )
    source_video = models.ForeignKey(
        'videos.Video',
        on_delete=models.CASCADE,
        related_name='mycut_projects',
        verbose_name='Quell-Video'
    )
    output_video = models.ForeignKey(
        'videos.Video',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mycut_outputs',
        verbose_name='Exportiertes Video'
    )

    # Projekt-Metadaten
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255, verbose_name='Projektname')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Status'
    )

    # Timeline-Daten (als JSON gespeichert)
    project_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Projekt-Daten',
        help_text='Vollständiger Timeline-Zustand als JSON'
    )

    # AI-Transkription
    ai_transcription = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='AI-Transkription',
        help_text='Whisper-Ergebnis mit Word-Timestamps'
    )

    # Waveform-Daten für Audio-Visualisierung
    waveform_data = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Waveform-Daten'
    )

    # Export-Einstellungen
    export_quality = models.CharField(
        max_length=10,
        choices=QUALITY_CHOICES,
        default='1080p',
        verbose_name='Export-Qualität'
    )
    export_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='mp4',
        verbose_name='Export-Format'
    )

    # Progress
    processing_progress = models.IntegerField(
        default=0,
        verbose_name='Fortschritt (%)'
    )
    processing_message = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Status-Nachricht'
    )

    # Thumbnails
    thumbnail = models.ImageField(
        upload_to='mycut/thumbnails/',
        null=True,
        blank=True,
        verbose_name='Vorschaubild'
    )

    # Geschätzte Dauer nach Bearbeitung
    estimated_duration = models.FloatField(
        default=0,
        verbose_name='Geschätzte Dauer (Sekunden)'
    )

    # Zeitstempel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'MyCut Projekt'
        verbose_name_plural = 'MyCut Projekte'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('mycut:editor', kwargs={'project_id': self.id})


class TimelineClip(models.Model):
    """
    Ein Clip auf der Timeline.
    Kann Video, Audio, Untertitel oder Text-Overlay sein.
    """
    CLIP_TYPE_CHOICES = [
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('subtitle', 'Untertitel'),
        ('text_overlay', 'Text-Overlay'),
        ('image', 'Bild'),
    ]

    project = models.ForeignKey(
        EditProject,
        on_delete=models.CASCADE,
        related_name='clips'
    )

    # Clip-Typ
    clip_type = models.CharField(
        max_length=20,
        choices=CLIP_TYPE_CHOICES,
        default='video'
    )

    # Track-Zuordnung (für Multi-Track-Unterstützung)
    track_index = models.IntegerField(
        default=0,
        verbose_name='Track-Index'
    )

    # Position auf der Timeline (in Millisekunden)
    start_time = models.FloatField(
        default=0,
        verbose_name='Start (ms)'
    )
    duration = models.FloatField(
        default=0,
        verbose_name='Dauer (ms)'
    )

    # Quell-Bereich (Trim-Punkte im Original)
    source_start = models.FloatField(
        default=0,
        verbose_name='Quell-Start (ms)'
    )
    source_end = models.FloatField(
        default=0,
        verbose_name='Quell-Ende (ms)'
    )

    # Clip-spezifische Daten (Effekte, Speed, Filter, etc.)
    clip_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Clip-Daten',
        help_text='Filter, Effekte, Transformationen als JSON'
    )

    # Reihenfolge für Sortierung
    order = models.IntegerField(default=0)

    # Ist der Clip deaktiviert (muted/hidden)?
    is_muted = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)

    # Lautstärke (0.0 - 2.0, 1.0 = normal)
    volume = models.FloatField(default=1.0)

    # Speed-Faktor (0.5 - 2.0, 1.0 = normal)
    speed = models.FloatField(default=1.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Timeline-Clip'
        verbose_name_plural = 'Timeline-Clips'
        ordering = ['track_index', 'start_time', 'order']

    def __str__(self):
        return f"{self.get_clip_type_display()} @ {self.start_time}ms"


class Subtitle(models.Model):
    """
    Ein Untertitel-Segment.
    Kann automatisch (via Whisper) oder manuell erstellt werden.
    """
    project = models.ForeignKey(
        EditProject,
        on_delete=models.CASCADE,
        related_name='subtitles'
    )

    # Text und Timing
    text = models.TextField(verbose_name='Text')
    start_time = models.FloatField(verbose_name='Start (ms)')
    end_time = models.FloatField(verbose_name='Ende (ms)')

    # Word-Level-Timestamps von Whisper
    word_timestamps = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Wort-Timestamps',
        help_text='[{"word": "Hallo", "start": 0.0, "end": 0.5}, ...]'
    )

    # Styling
    style = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Stil',
        help_text='{"font": "Arial", "size": 24, "color": "#FFFFFF", "position": "bottom"}'
    )

    # Metadaten
    is_auto_generated = models.BooleanField(
        default=False,
        verbose_name='Automatisch generiert'
    )
    confidence = models.FloatField(
        default=1.0,
        verbose_name='Konfidenz',
        help_text='AI-Konfidenz (0.0 - 1.0)'
    )
    language = models.CharField(
        max_length=10,
        default='de',
        verbose_name='Sprache'
    )

    # Reihenfolge
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Untertitel'
        verbose_name_plural = 'Untertitel'
        ordering = ['start_time', 'order']

    def __str__(self):
        preview = self.text[:50] + '...' if len(self.text) > 50 else self.text
        return f"{preview} ({self.start_time}ms - {self.end_time}ms)"


class TextOverlay(models.Model):
    """
    Text-Overlay für das Video.
    Unterscheidet sich von Untertiteln durch freie Positionierung und Animationen.
    """
    ANIMATION_CHOICES = [
        ('none', 'Keine'),
        ('fade_in', 'Einblenden'),
        ('fade_out', 'Ausblenden'),
        ('fade_in_out', 'Ein- und Ausblenden'),
        ('slide_left', 'Von links einschieben'),
        ('slide_right', 'Von rechts einschieben'),
        ('slide_up', 'Von unten einschieben'),
        ('slide_down', 'Von oben einschieben'),
        ('typewriter', 'Schreibmaschine'),
        ('zoom_in', 'Heranzoomen'),
    ]

    project = models.ForeignKey(
        EditProject,
        on_delete=models.CASCADE,
        related_name='text_overlays'
    )

    # Text und Timing
    text = models.TextField(verbose_name='Text')
    start_time = models.FloatField(verbose_name='Start (ms)')
    end_time = models.FloatField(verbose_name='Ende (ms)')

    # Position (in Prozent, 0-100)
    position_x = models.FloatField(
        default=50,
        verbose_name='X-Position (%)'
    )
    position_y = models.FloatField(
        default=50,
        verbose_name='Y-Position (%)'
    )

    # Styling
    style = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Stil',
        help_text='{"font": "Arial", "size": 48, "color": "#FFFFFF", "bold": true}'
    )

    # Animation
    animation_in = models.CharField(
        max_length=20,
        choices=ANIMATION_CHOICES,
        default='fade_in',
        verbose_name='Eingangs-Animation'
    )
    animation_out = models.CharField(
        max_length=20,
        choices=ANIMATION_CHOICES,
        default='fade_out',
        verbose_name='Ausgangs-Animation'
    )
    animation_duration = models.FloatField(
        default=500,
        verbose_name='Animations-Dauer (ms)'
    )

    # Reihenfolge
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Text-Overlay'
        verbose_name_plural = 'Text-Overlays'
        ordering = ['start_time', 'order']

    def __str__(self):
        preview = self.text[:30] + '...' if len(self.text) > 30 else self.text
        return f"Overlay: {preview}"


class AIEditSuggestion(models.Model):
    """
    KI-generierter Bearbeitungsvorschlag.
    Z.B. Filler-Wörter, Stille, Speed-Änderungen, Zoom-Momente.
    """
    SUGGESTION_TYPE_CHOICES = [
        ('filler_word', 'Filler-Wort'),
        ('silence', 'Stille/Pause'),
        ('speed_up', 'Beschleunigen'),
        ('speed_down', 'Verlangsamen'),
        ('zoom_in', 'Heranzoomen'),
        ('zoom_out', 'Herauszoomen'),
        ('cut', 'Schneiden'),
    ]

    project = models.ForeignKey(
        EditProject,
        on_delete=models.CASCADE,
        related_name='ai_suggestions'
    )

    # Typ des Vorschlags
    suggestion_type = models.CharField(
        max_length=20,
        choices=SUGGESTION_TYPE_CHOICES,
        verbose_name='Typ'
    )

    # Zeitbereich
    start_time = models.FloatField(verbose_name='Start (ms)')
    end_time = models.FloatField(verbose_name='Ende (ms)')

    # Konfidenz der AI
    confidence = models.FloatField(
        default=0.8,
        verbose_name='Konfidenz',
        help_text='AI-Konfidenz (0.0 - 1.0)'
    )

    # Status
    is_applied = models.BooleanField(
        default=False,
        verbose_name='Angewendet'
    )
    is_rejected = models.BooleanField(
        default=False,
        verbose_name='Abgelehnt'
    )

    # Zusätzliche Daten
    suggestion_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Vorschlags-Daten',
        help_text='Typ-spezifische Parameter'
    )

    # Erkannter Text (bei Filler-Wörtern)
    text = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Erkannter Text'
    )

    # Vorgeschlagener Wert (z.B. Speed-Faktor)
    suggested_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Vorgeschlagener Wert'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI-Vorschlag'
        verbose_name_plural = 'AI-Vorschläge'
        ordering = ['start_time']

    def __str__(self):
        return f"{self.get_suggestion_type_display()}: {self.text or 'N/A'} @ {self.start_time}ms"


class ExportJob(models.Model):
    """
    Export-Auftrag für ein Projekt.
    Wird von Celery verarbeitet.
    """
    STATUS_CHOICES = [
        ('pending', 'Wartend'),
        ('processing', 'Wird verarbeitet'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
        ('cancelled', 'Abgebrochen'),
    ]

    project = models.ForeignKey(
        EditProject,
        on_delete=models.CASCADE,
        related_name='export_jobs'
    )

    # Celery Task ID
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Celery Task ID'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    progress = models.IntegerField(
        default=0,
        verbose_name='Fortschritt (%)'
    )

    # Ausgabedatei
    output_file = models.FileField(
        upload_to='mycut/exports/',
        null=True,
        blank=True,
        verbose_name='Ausgabedatei'
    )

    # Fehler-Nachricht
    error_message = models.TextField(
        blank=True,
        default='',
        verbose_name='Fehlermeldung'
    )

    # Dateigröße
    file_size = models.BigIntegerField(
        default=0,
        verbose_name='Dateigröße (Bytes)'
    )

    # Export-Einstellungen (Kopie zum Zeitpunkt des Exports)
    export_settings = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Export-Einstellungen'
    )

    # Zeitstempel
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Export-Auftrag'
        verbose_name_plural = 'Export-Aufträge'
        ordering = ['-created_at']

    def __str__(self):
        return f"Export {self.id} - {self.project.name} ({self.get_status_display()})"

    def start_processing(self):
        """Markiert den Job als gestartet."""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def complete(self, file_path, file_size):
        """Markiert den Job als abgeschlossen."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.output_file = file_path
        self.file_size = file_size
        self.progress = 100
        self.save(update_fields=['status', 'completed_at', 'output_file', 'file_size', 'progress'])

    def fail(self, error_message):
        """Markiert den Job als fehlgeschlagen."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message'])
