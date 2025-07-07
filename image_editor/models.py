from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import os

User = get_user_model()


class ImageProject(models.Model):
    """Hauptmodell für Bildbearbeitungsprojekte"""
    
    SOURCE_CHOICES = [
        ('upload', 'Hochgeladen'),
        ('ai_generated', 'KI-generiert'),
        ('canva_import', 'Canva Import'),
        ('shopify_import', 'Shopify Import'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('processing', 'Wird bearbeitet'),
        ('completed', 'Abgeschlossen'),
        ('error', 'Fehler'),
    ]
    
    # Basis-Informationen
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='image_projects')
    name = models.CharField(max_length=255, verbose_name="Projektname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    
    # Bildquelle
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='upload')
    
    # Original-Bild
    original_image = models.ImageField(upload_to='images/originals/', null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    
    # AI-Generation Details (falls KI-generiert)
    ai_prompt = models.TextField(blank=True, verbose_name="KI-Prompt")
    ai_model = models.CharField(max_length=50, blank=True, verbose_name="KI-Modell")
    ai_generation_params = models.JSONField(default=dict, blank=True)
    
    # Bearbeitet Bild
    processed_image = models.ImageField(upload_to='images/processed/', null=True, blank=True)
    
    # Bildbearbeitungs-Parameter
    processing_history = models.JSONField(default=list, blank=True)
    current_settings = models.JSONField(default=dict, blank=True)
    
    # Status und Metadaten
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Bildabmessungen
    original_width = models.PositiveIntegerField(null=True, blank=True)
    original_height = models.PositiveIntegerField(null=True, blank=True)
    processed_width = models.PositiveIntegerField(null=True, blank=True)
    processed_height = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Bildprojekt"
        verbose_name_plural = "Bildprojekte"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def get_file_size(self):
        """Gibt die Dateigröße des Original-Bildes zurück"""
        if self.original_image and os.path.exists(self.original_image.path):
            return os.path.getsize(self.original_image.path)
        return 0
    
    def get_processing_steps_count(self):
        """Anzahl der Bearbeitungsschritte"""
        return len(self.processing_history)


class ProcessingStep(models.Model):
    """Einzelne Bearbeitungsschritte für detaillierte Historie"""
    
    OPERATION_CHOICES = [
        # Basis-Bearbeitungen
        ('invert', 'Invertieren'),
        ('grayscale', 'Schwarzweiß'),
        ('brightness', 'Helligkeit'),
        ('contrast', 'Kontrast'),
        ('saturation', 'Sättigung'),
        ('hue', 'Farbton'),
        
        # Erweiterte Bearbeitungen
        ('resize', 'Größe ändern'),
        ('crop', 'Zuschneiden'),
        ('rotate', 'Drehen'),
        ('flip_horizontal', 'Horizontal spiegeln'),
        ('flip_vertical', 'Vertikal spiegeln'),
        
        # Spezial-Operationen
        ('remove_background', 'Hintergrund entfernen'),
        ('prepare_engraving', 'Gravur vorbereiten'),
        ('vectorize', 'Vektorisieren'),
        ('enhance_lines', 'Linien verstärken'),
        
        # Filter
        ('blur', 'Weichzeichnen'),
        ('sharpen', 'Schärfen'),
        ('emboss', 'Prägen'),
        ('edge_detect', 'Kantenerkennung'),
    ]
    
    project = models.ForeignKey(ImageProject, on_delete=models.CASCADE, related_name='steps')
    operation = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    parameters = models.JSONField(default=dict)
    applied_at = models.DateTimeField(default=timezone.now)
    
    # Resultat des Schritts
    result_image = models.ImageField(upload_to='images/steps/', null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True, help_text="Zeit in Sekunden")
    
    class Meta:
        verbose_name = "Bearbeitungsschritt"
        verbose_name_plural = "Bearbeitungsschritte"
        ordering = ['applied_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.get_operation_display()}"


class ExportFormat(models.Model):
    """Verfügbare Export-Formate"""
    
    FORMAT_CHOICES = [
        ('PNG', 'PNG - Verlustfrei'),
        ('JPEG', 'JPEG - Komprimiert'),
        ('WEBP', 'WebP - Modern'),
        ('SVG', 'SVG - Vektor'),
        ('PDF', 'PDF - Dokument'),
        ('TIFF', 'TIFF - Professionell'),
    ]
    
    QUALITY_CHOICES = [
        ('low', 'Niedrig (kleiner)'),
        ('medium', 'Mittel'),
        ('high', 'Hoch'),
        ('max', 'Maximum'),
    ]
    
    project = models.ForeignKey(ImageProject, on_delete=models.CASCADE, related_name='exports')
    format_type = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='high')
    
    # Zusätzliche Parameter
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    dpi = models.PositiveIntegerField(default=300, help_text="DPI für Druck")
    
    # Export-Details
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "Export-Format"
        verbose_name_plural = "Export-Formate"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name} - {self.format_type}"


class EngravingSettings(models.Model):
    """Spezielle Einstellungen für Laser-Gravur"""
    
    project = models.OneToOneField(ImageProject, on_delete=models.CASCADE, related_name='engraving_settings')
    
    # Laser-Parameter
    beam_width = models.FloatField(default=0.1, help_text="Laserstrahl-Breite in mm")
    line_thickness = models.FloatField(default=0.1, help_text="Mindest-Linienstärke in mm")
    
    # Gravur-Einstellungen
    depth_levels = models.PositiveIntegerField(default=5, help_text="Anzahl Tiefenstufen")
    max_depth = models.FloatField(default=0.5, help_text="Maximale Gravurtiefe in mm")
    
    # Vektor-Einstellungen
    vectorize_threshold = models.FloatField(default=128, help_text="Schwellwert für Vektorisierung (0-255)")
    simplify_tolerance = models.FloatField(default=1.0, help_text="Vereinfachungstoleranz")
    
    # Optimierungen
    optimize_paths = models.BooleanField(default=True, help_text="Gravurpfade optimieren")
    remove_duplicates = models.BooleanField(default=True, help_text="Doppelte Pfade entfernen")
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gravur-Einstellungen"
        verbose_name_plural = "Gravur-Einstellungen"
    
    def __str__(self):
        return f"Gravur: {self.project.name}"


class AIGenerationHistory(models.Model):
    """Historie der KI-Bildgenerierungen"""
    
    AI_MODELS = [
        ('dall-e-3', 'DALL-E 3'),
        ('dall-e-2', 'DALL-E 2'),
        ('midjourney', 'Midjourney'),
        ('stable-diffusion', 'Stable Diffusion'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_generations')
    prompt = models.TextField(verbose_name="Prompt")
    negative_prompt = models.TextField(blank=True, verbose_name="Negativ-Prompt")
    
    # AI-Parameter
    ai_model = models.CharField(max_length=30, choices=AI_MODELS, default='dall-e-3')
    style = models.CharField(max_length=50, blank=True)
    quality = models.CharField(max_length=20, default='standard')
    size = models.CharField(max_length=20, default='1024x1024')
    
    # Kosten und Status
    cost = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    generation_time = models.FloatField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    
    # Resultat
    generated_image = models.ImageField(upload_to='images/ai_generated/', null=True, blank=True)
    project = models.ForeignKey(ImageProject, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "KI-Generierung"
        verbose_name_plural = "KI-Generierungen"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.prompt[:50]}... ({self.ai_model})"