from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import json

User = get_user_model()


class Platform(models.Model):
    """Social Media Plattformen"""
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome Icon Klasse")
    color = models.CharField(max_length=20, default="#007bff", help_text="Bootstrap Farbe oder Hex-Code")
    character_limit = models.IntegerField(default=280, help_text="Zeichen-Limit für Posts")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Plattform"
        verbose_name_plural = "Plattformen"
    
    def __str__(self):
        return self.name


class PostingPlan(models.Model):
    """Container für einen kompletten Posting-Plan"""
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('active', 'Aktiv'), 
        ('completed', 'Abgeschlossen'),
        ('archived', 'Archiviert'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posting_plans')
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)
    
    # Strategie-Daten (JSON für Flexibilität)
    strategy_data = models.JSONField(default=dict, blank=True, help_text="KI-generierte Strategie-Vorschläge")
    
    # User-Input aus Schritt 1
    user_profile = models.TextField(help_text="Was bin ich, was habe ich, was kann ich")
    target_audience = models.TextField(help_text="Zielgruppe und Themenbereich")
    goals = models.TextField(help_text="Zielsetzung der Social Media Strategie")
    vision = models.TextField(help_text="Wunschvorstellung/Vision")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Posting-Plan"
        verbose_name_plural = "Posting-Pläne"
    
    def __str__(self):
        return f"{self.title} ({self.platform.name})"
    
    def get_absolute_url(self):
        return reverse('somi_plan:plan_detail', kwargs={'pk': self.pk})
    
    def get_post_count(self):
        return self.posts.count()
    
    def get_scheduled_posts_count(self):
        return self.posts.filter(schedule__isnull=False).count()


class PlanningSession(models.Model):
    """Verfolgt den 3-Stufen-Assistenten-Prozess"""
    STEP_CHOICES = [
        (1, 'Schritt 1: Basis-Setup'),
        (2, 'Schritt 2: Strategie-Entwicklung'),
        (3, 'Schritt 3: Content-Erstellung'),
    ]
    
    posting_plan = models.OneToOneField(PostingPlan, on_delete=models.CASCADE, related_name='session')
    current_step = models.IntegerField(choices=STEP_CHOICES, default=1)
    session_data = models.JSONField(default=dict, blank=True, help_text="Temporary data während der Session")
    completed_steps = models.JSONField(default=list, blank=True, help_text="Liste der abgeschlossenen Schritte")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Planning Session"
        verbose_name_plural = "Planning Sessions"
    
    def __str__(self):
        return f"Session für {self.posting_plan.title} - Schritt {self.current_step}"
    
    def is_step_completed(self, step):
        return step in self.completed_steps
    
    def complete_step(self, step):
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            self.save()
    
    def next_step(self):
        if self.current_step < 3:
            self.current_step += 1
            self.save()


class PostContent(models.Model):
    """Einzelne Posts/Kacheln mit KI-generierten Inhalten"""
    posting_plan = models.ForeignKey(PostingPlan, on_delete=models.CASCADE, related_name='posts')
    
    title = models.CharField(max_length=200, help_text="Überschrift der Kachel")
    content = models.TextField(help_text="Haupt-Content des Posts")
    script = models.TextField(help_text="Detailliertes Skript und Anweisungen")
    
    # KI-Metadaten
    ai_generated = models.BooleanField(default=True)
    ai_model_used = models.CharField(max_length=50, blank=True)
    ai_prompt_used = models.TextField(blank=True)
    
    # Post-Metadaten
    character_count = models.IntegerField(default=0)
    hashtags = models.CharField(max_length=500, blank=True, help_text="Vorgeschlagene Hashtags")
    call_to_action = models.CharField(max_length=200, blank=True)
    
    # Kategorisierung
    post_type = models.CharField(max_length=50, blank=True, help_text="z.B. Tipp, Story, Werbung")
    priority = models.IntegerField(default=3, help_text="1=Hoch, 2=Mittel, 3=Niedrig")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Post Content"
        verbose_name_plural = "Post Contents"
    
    def __str__(self):
        return f"{self.title} - {self.posting_plan.title}"
    
    def save(self, *args, **kwargs):
        # Automatische Zeichen-Zählung
        self.character_count = len(self.content)
        super().save(*args, **kwargs)
    
    def is_within_character_limit(self):
        return self.character_count <= self.posting_plan.platform.character_limit
    
    def get_character_limit_percentage(self):
        limit = self.posting_plan.platform.character_limit
        return (self.character_count / limit) * 100 if limit > 0 else 0


class PostSchedule(models.Model):
    """Terminplanung für Posts (Kalender-Integration)"""
    STATUS_CHOICES = [
        ('scheduled', 'Geplant'),
        ('posted', 'Veröffentlicht'),
        ('completed', 'Erledigt'),
        ('cancelled', 'Abgebrochen'),
    ]
    
    post_content = models.OneToOneField(PostContent, on_delete=models.CASCADE, related_name='schedule')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Notizen und Tracking
    notes = models.TextField(blank=True, help_text="Notizen zur Umsetzung")
    actual_post_url = models.URLField(blank=True, help_text="Link zum veröffentlichten Post")
    completion_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']
        unique_together = ['post_content']
        verbose_name = "Post Schedule"
        verbose_name_plural = "Post Schedules"
    
    def __str__(self):
        return f"{self.post_content.title} - {self.scheduled_date} {self.scheduled_time}"
    
    def mark_completed(self, url=None):
        self.status = 'completed'
        self.completion_date = timezone.now()
        if url:
            self.actual_post_url = url
        self.save()
    
    def is_overdue(self):
        if self.status in ['completed', 'cancelled']:
            return False
        
        from datetime import datetime, time
        scheduled_datetime = datetime.combine(self.scheduled_date, self.scheduled_time)
        return timezone.now() > timezone.make_aware(scheduled_datetime)
    
    @property
    def scheduled_datetime(self):
        from datetime import datetime
        return datetime.combine(self.scheduled_date, self.scheduled_time)


class TemplateCategory(models.Model):
    """Kategorien für Post-Templates (eigene Idee zur Erweiterung)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, related_name='template_categories')
    icon = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'platform']
        verbose_name = "Template Kategorie"
        verbose_name_plural = "Template Kategorien"
    
    def __str__(self):
        return f"{self.name} ({self.platform.name})"


class PostTemplate(models.Model):
    """Vordefinierte Templates für verschiedene Post-Typen (eigene Erweiterung)"""
    name = models.CharField(max_length=200)
    category = models.ForeignKey(TemplateCategory, on_delete=models.CASCADE, related_name='templates')
    
    content_template = models.TextField(help_text="Template mit Platzhaltern: {thema}, {zielgruppe}, etc.")
    script_template = models.TextField(help_text="Anweisungs-Template")
    
    # AI Prompts für bessere Generierung
    ai_system_prompt = models.TextField(blank=True)
    ai_user_prompt_template = models.TextField(blank=True)
    
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-usage_count', 'name']
        verbose_name = "Post Template"
        verbose_name_plural = "Post Templates"
    
    def __str__(self):
        return f"{self.name} - {self.category.name}"
    
    def increment_usage(self):
        self.usage_count += 1
        self.save(update_fields=['usage_count'])
