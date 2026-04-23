from django.db import models
import uuid


class VideoProject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    exported_video_url = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Video Project'
        verbose_name_plural = 'Video Projects'

    def __str__(self):
        return self.name


class VideoAsset(models.Model):
    ASSET_TYPES = [
        ('character', 'Character'),
        ('style', 'Style'),
        ('product', 'Product'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='assets')
    type = models.CharField(max_length=20, choices=ASSET_TYPES)
    name = models.CharField(max_length=255)
    file = models.ImageField(upload_to='videocreator/uploads/')
    original_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Video Asset'
        verbose_name_plural = 'Video Assets'

    def __str__(self):
        return f"{self.type}: {self.name}"


class GeneratedImage(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('done', 'Done'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='generated_images')
    prompt = models.TextField(blank=True)
    model = models.CharField(max_length=50, default='nano-banana-pro')
    image = models.ImageField(upload_to='videocreator/generated/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    task_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Generated Image'
        verbose_name_plural = 'Generated Images'

    def __str__(self):
        return f"Image: {self.prompt[:50]}"


class VideoScene(models.Model):
    VIDEO_MODELS = [
        # Kling (Kuaishou) - Most Popular
        ('kling/3.0', 'Kling 3.0'),
        ('kling/2.6', 'Kling 2.6'),
        ('kling/2.5-turbo', 'Kling 2.5 Turbo'),
        ('kling/2.1', 'Kling 2.1'),
        ('kling/3.0-motion-control', 'Kling 3.0 Motion Control'),
        ('kling/2.6-motion-control', 'Kling 2.6 Motion Control'),
        
        # Google Veo
        ('veo/3.1-fast', 'Veo 3.1 Fast'),
        ('veo/3.1-quality', 'Veo 3.1 Quality'),
        ('veo/3.1-extend', 'Veo 3.1 Extend'),
        
        # OpenAI Sora
        ('sora2/stable', 'Sora2 Stable'),
        ('sora2/standard', 'Sora2 Standard'),
        ('sora2-pro/standard', 'Sora2 Pro Standard'),
        ('sora2-pro/high', 'Sora2 Pro High'),
        ('sora2-storyboard', 'Sora2 Storyboard'),
        
        # Hailuo/MiniMax
        ('hailuo/2.3-standard', 'Hailuo 2.3 Standard'),
        ('hailuo/2.3-pro', 'Hailuo 2.3 Pro'),
        ('hailuo/02-standard', 'Hailuo 02 Standard'),
        ('hailuo/02-pro', 'Hailuo 02 Pro'),
        
        # Wan (Alibaba)
        ('wan/2.6', 'Wan 2.6'),
        ('wan/2.5', 'Wan 2.5'),
        ('wan/2.2', 'Wan 2.2'),
        ('wan/2.2-animate', 'Wan 2.2 Animate'),
        
        # Grok (xAI)
        ('grok-imagine', 'Grok Imagine'),
        ('grok-imagine/extend', 'Grok Imagine Extend'),
        ('grok-imagine/upscale', 'Grok Imagine Upscale'),
        
        # Runway
        ('runway', 'Runway'),
        ('runway-aleph', 'Runway Aleph'),
        
        # Lip Sync
        ('kling-avatar', 'Kling Avatar'),
        ('meigen-infinitetalk', 'Meigen InfiniteTalk'),
        
        # Legacy models (for backward compatibility)
        ('kling/3.0-image-to-video', 'Kling 3.0 (Legacy)'),
        ('kling/2.6-image-to-video', 'Kling 2.6 (Legacy)'),
        ('sora2/image-to-video', 'Sora 2 (Legacy)'),
        ('sora2/pro-image-to-video', 'Sora 2 Pro (Legacy)'),
        ('veo3_fast', 'Veo 3.1 Fast (Legacy)'),
        ('veo3', 'Veo 3.1 Quality (Legacy)'),
        ('wan/2.6-image-to-video', 'Wan 2.6 (Legacy)'),
        ('hailuo/2.3-image-to-video', 'Hailuo 2.3 (Legacy)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('done', 'Done'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='scenes')
    order = models.PositiveIntegerField(default=0)
    
    start_frame = models.ForeignKey(
        GeneratedImage, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='start_frame_scenes'
    )
    end_frame = models.ForeignKey(
        GeneratedImage, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='end_frame_scenes'
    )
    
    prompt = models.TextField(blank=True)
    video_model = models.CharField(max_length=50, choices=VIDEO_MODELS, default='kling/2.6')
    duration = models.PositiveIntegerField(default=5)
    video_task_id = models.CharField(max_length=100, blank=True, null=True)
    video_url = models.CharField(max_length=500, blank=True, null=True)
    video_file = models.FileField(upload_to='videocreator/generated/', blank=True, null=True)
    video_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    audio_source = models.CharField(max_length=20, blank=True, null=True)
    audio_tts_text = models.TextField(blank=True)
    audio_task_id = models.CharField(max_length=100, blank=True, null=True)
    audio_url = models.CharField(max_length=500, blank=True, null=True)
    audio_file = models.FileField(upload_to='videocreator/generated/', blank=True, null=True)
    audio_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['order']
        verbose_name = 'Video Scene'
        verbose_name_plural = 'Video Scenes'

    def __str__(self):
        return f"Scene {self.order + 1}: {self.prompt[:30]}"