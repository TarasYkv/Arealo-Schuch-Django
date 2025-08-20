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


class TextOverlay(models.Model):
    """
    Text-Overlays für Creative-Bilder
    """
    FONT_FAMILY_CHOICES = [
        ('arial', 'Arial'),
        ('helvetica', 'Helvetica'),
        ('times', 'Times New Roman'),
        ('georgia', 'Georgia'),
        ('courier', 'Courier New'),
        ('verdana', 'Verdana'),
        ('tahoma', 'Tahoma'),
        ('impact', 'Impact'),
        ('comic-sans', 'Comic Sans MS'),
        ('trebuchet', 'Trebuchet MS'),
    ]
    
    FONT_WEIGHT_CHOICES = [
        ('normal', 'Normal'),
        ('bold', 'Bold'),
        ('light', 'Light'),
        ('black', 'Black'),
    ]
    
    TEXT_ALIGN_CHOICES = [
        ('left', 'Links'),
        ('center', 'Zentriert'),
        ('right', 'Rechts'),
        ('justify', 'Blocksatz'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creative = models.ForeignKey(Creative, on_delete=models.CASCADE, related_name='text_overlays')
    text_content = models.TextField(verbose_name='Overlay-Text')
    
    # Position (percentage-based for responsive design)
    x_position = models.FloatField(verbose_name='X-Position (%)', default=10.0)
    y_position = models.FloatField(verbose_name='Y-Position (%)', default=10.0)
    
    # Design properties
    font_family = models.CharField(
        max_length=20,
        choices=FONT_FAMILY_CHOICES,
        default='arial',
        verbose_name='Schriftart'
    )
    font_size = models.PositiveIntegerField(default=24, verbose_name='Schriftgröße (px)')
    font_weight = models.CharField(
        max_length=10,
        choices=FONT_WEIGHT_CHOICES,
        default='normal',
        verbose_name='Schriftgewicht'
    )
    text_color = models.CharField(
        max_length=7, 
        default='#FFFFFF',
        verbose_name='Textfarbe (Hex)'
    )
    background_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Hintergrundfarbe (Hex)',
        blank=True,
        null=True
    )
    background_opacity = models.FloatField(
        default=0.0,
        verbose_name='Hintergrund-Transparenz (0-1)'
    )
    text_align = models.CharField(
        max_length=10,
        choices=TEXT_ALIGN_CHOICES,
        default='left',
        verbose_name='Textausrichtung'
    )
    
    # Shadow and effects
    has_shadow = models.BooleanField(default=True, verbose_name='Text-Schatten')
    shadow_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Schatten-Farbe (Hex)'
    )
    shadow_blur = models.PositiveIntegerField(default=4, verbose_name='Schatten-Weichzeichnung')
    
    # Border/Stroke
    has_border = models.BooleanField(default=False, verbose_name='Text-Rahmen')
    border_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Rahmen-Farbe (Hex)'
    )
    border_width = models.PositiveIntegerField(default=1, verbose_name='Rahmen-Breite (px)')
    
    # Dimensions and rotation
    width = models.PositiveIntegerField(
        default=200,
        verbose_name='Breite (px)',
        help_text='Maximale Breite des Text-Containers'
    )
    line_height = models.FloatField(
        default=1.2,
        verbose_name='Zeilenhöhe'
    )
    letter_spacing = models.FloatField(
        default=0.0,
        verbose_name='Buchstabenabstand (px)'
    )
    rotation = models.FloatField(
        default=0.0,
        verbose_name='Rotation (Grad)'
    )
    
    # AI-generated metadata
    ai_generated = models.BooleanField(default=False, verbose_name='KI-generiert')
    ai_prompt_used = models.TextField(
        verbose_name='Verwendeter AI-Prompt',
        blank=True,
        null=True
    )
    
    # Advanced text effects
    has_gradient = models.BooleanField(default=False, verbose_name='Farbverlauf')
    gradient_start_color = models.CharField(
        max_length=7,
        default='#FF0000',
        verbose_name='Verlauf Startfarbe (Hex)',
        blank=True,
        null=True
    )
    gradient_end_color = models.CharField(
        max_length=7,
        default='#0000FF',
        verbose_name='Verlauf Endfarbe (Hex)',
        blank=True,
        null=True
    )
    gradient_direction = models.CharField(
        max_length=20,
        choices=[
            ('to right', 'Horizontal →'),
            ('to left', 'Horizontal ←'),
            ('to bottom', 'Vertikal ↓'),
            ('to top', 'Vertikal ↑'),
            ('45deg', 'Diagonal ↗'),
            ('135deg', 'Diagonal ↘'),
            ('radial', 'Radial')
        ],
        default='to right',
        verbose_name='Verlauf-Richtung'
    )
    
    # Glow effect
    has_glow = models.BooleanField(default=False, verbose_name='Leuchteffekt')
    glow_color = models.CharField(
        max_length=7,
        default='#00FFFF',
        verbose_name='Leuchtfarbe (Hex)',
        blank=True,
        null=True
    )
    glow_intensity = models.PositiveIntegerField(default=10, verbose_name='Leuchtintensität (px)')
    
    # Outline/Stroke effect
    has_outline = models.BooleanField(default=False, verbose_name='Textumriss')
    outline_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Umriss-Farbe (Hex)',
        blank=True,
        null=True
    )
    outline_width = models.FloatField(default=1.0, verbose_name='Umriss-Breite (px)')
    
    # 3D effect
    has_3d_effect = models.BooleanField(default=False, verbose_name='3D-Effekt')
    effect_depth = models.PositiveIntegerField(default=3, verbose_name='3D-Tiefe (px)')
    effect_color = models.CharField(
        max_length=7,
        default='#333333',
        verbose_name='3D-Effekt-Farbe (Hex)',
        blank=True,
        null=True
    )
    
    # Visibility
    is_active = models.BooleanField(default=True, verbose_name='Sichtbar')
    z_index = models.PositiveIntegerField(default=1, verbose_name='Ebene (Z-Index)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Text-Overlay'
        verbose_name_plural = 'Text-Overlays'
        ordering = ['z_index', '-created_at']
    
    def __str__(self):
        text_preview = (self.text_content[:30] + '...') if len(self.text_content) > 30 else self.text_content
        return f"{text_preview} - {self.creative.title}"
    
    def get_css_styles(self):
        """Generate CSS styles for frontend rendering"""
        styles = {
            'position': 'absolute',
            'left': f'{self.x_position}%',
            'top': f'{self.y_position}%',
            'font-family': self.font_family,
            'font-size': f'{self.font_size}px',
            'font-weight': self.font_weight,
            'color': self.text_color,
            'text-align': self.text_align,
            'max-width': f'{self.width}px',
            'line-height': str(self.line_height),
            'letter-spacing': f'{self.letter_spacing}px',
            'z-index': str(self.z_index),
            'transform': f'rotate({self.rotation}deg)',
            'cursor': 'move',
            'user-select': 'none',
            'white-space': 'pre-wrap',
            'word-wrap': 'break-word',
        }
        
        if self.background_color and self.background_opacity > 0:
            # Convert hex to rgba
            bg_color = self.background_color.lstrip('#')
            rgb = tuple(int(bg_color[i:i+2], 16) for i in (0, 2, 4))
            styles['background-color'] = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {self.background_opacity})'
            styles['padding'] = '8px 12px'
            styles['border-radius'] = '4px'
        
        if self.has_shadow:
            shadow_color = self.shadow_color.lstrip('#')
            rgb = tuple(int(shadow_color[i:i+2], 16) for i in (0, 2, 4))
            styles['text-shadow'] = f'2px 2px {self.shadow_blur}px rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.8)'
        
        if self.has_border:
            styles['text-stroke'] = f'{self.border_width}px {self.border_color}'
            styles['-webkit-text-stroke'] = f'{self.border_width}px {self.border_color}'
        
        # Gradient text effect
        if self.has_gradient and self.gradient_start_color and self.gradient_end_color:
            if self.gradient_direction == 'radial':
                gradient = f'radial-gradient(circle, {self.gradient_start_color}, {self.gradient_end_color})'
            else:
                gradient = f'linear-gradient({self.gradient_direction}, {self.gradient_start_color}, {self.gradient_end_color})'
            
            styles['background'] = gradient
            styles['-webkit-background-clip'] = 'text'
            styles['background-clip'] = 'text'
            styles['-webkit-text-fill-color'] = 'transparent'
            styles['color'] = 'transparent'
        
        # Glow effect
        if self.has_glow and self.glow_color:
            glow_color = self.glow_color.lstrip('#')
            rgb = tuple(int(glow_color[i:i+2], 16) for i in (0, 2, 4))
            glow_shadow = f'0 0 {self.glow_intensity}px rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.8)'
            
            if 'text-shadow' in styles:
                styles['text-shadow'] += f', {glow_shadow}'
            else:
                styles['text-shadow'] = glow_shadow
        
        # Text outline effect
        if self.has_outline and self.outline_color:
            styles['-webkit-text-stroke'] = f'{self.outline_width}px {self.outline_color}'
            styles['text-stroke'] = f'{self.outline_width}px {self.outline_color}'
        
        # 3D effect
        if self.has_3d_effect and self.effect_color:
            effect_shadows = []
            for i in range(1, self.effect_depth + 1):
                effect_shadows.append(f'{i}px {i}px 0 {self.effect_color}')
            
            effect_shadow_string = ', '.join(effect_shadows)
            if 'text-shadow' in styles:
                styles['text-shadow'] += f', {effect_shadow_string}'
            else:
                styles['text-shadow'] = effect_shadow_string
        
        return styles
    
    def get_style_string(self):
        """Get CSS styles as a string for inline styling"""
        styles = self.get_css_styles()
        return '; '.join([f'{key}: {value}' for key, value in styles.items()])


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