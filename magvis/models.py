"""Magvis Models — Wizard-Orchestrierung für Naturmacher-Workflow

Reuse-First: Magvis hält keine eigenen Video/Produkt/Blog-Daten,
sondern verweist über ForeignKeys auf vidgen, videos, ploom.
"""
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class MagvisSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='magvis_settings',
    )

    # KI-Provider + Modell fuer Texte (Multi-Provider, configurable)
    text_provider = models.CharField(
        max_length=32, default='zhipu',
        help_text='openai, anthropic, gemini, zhipu, deepseek, openrouter',
    )
    text_model = models.CharField(max_length=64, default='glm-5.1')

    # Legacy (backward compat, wird in v2-Migration entfernt):
    glm_model = models.CharField(max_length=64, default='glm-5.1')
    glm_base_url = models.URLField(default='https://api.z.ai/api/coding/paas/v4')

    # Gemini (Bilder)
    gemini_image_model = models.CharField(max_length=64, default='gemini-2.5-flash-image')

    # Defaults Video
    default_video_template = models.CharField(max_length=32, default='youtube_short')
    default_video_duration = models.IntegerField(default=45)
    default_voice = models.CharField(max_length=32, default='alloy')

    # Defaults Blog
    default_quiz_questions = models.IntegerField(default=4)
    default_faq_count = models.IntegerField(default=5)
    naturmacher_brand_voice = models.TextField(
        blank=True,
        default='Naturmacher.de — herzlich, persönlich, naturverbunden, du-Form, deutscher Familienbetrieb.',
    )

    # Defaults Produkte (FK auf bestehende ploom-Settings)
    default_ploom_settings = models.ForeignKey(
        'ploom.PLoomSettings', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    fixed_cdn_image_urls = models.JSONField(
        default=list,
        help_text='3 fixe Naturmacher-CDN-Bild-URLs für Phase 2 der Produktbilder',
    )

    # Defaults Bild-Posten
    default_image_platforms = models.JSONField(default=list)
    upload_post_user = models.CharField(max_length=64, blank=True)

    # Auto-Run aus Themen-Queue
    auto_run_enabled = models.BooleanField(default=False)
    auto_run_schedule = models.CharField(
        max_length=64, blank=True,
        help_text='Cron-Expression, z.B. "0 6 * * *" für täglich 06:00',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Magvis-Einstellungen'
        verbose_name_plural = 'Magvis-Einstellungen'

    def __str__(self):
        return f'Magvis-Settings {self.user}'


class MagvisReportConfig(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='magvis_report_config',
    )
    report_email = models.EmailField()
    cc_emails = models.JSONField(default=list, blank=True)

    include_video_link = models.BooleanField(default=True)
    include_youtube_link = models.BooleanField(default=True)
    include_product_links = models.BooleanField(default=True)
    include_product_thumbnails = models.BooleanField(default=True)
    include_blog_link = models.BooleanField(default=True)
    include_blog_excerpt = models.BooleanField(default=True)
    include_diagram_image = models.BooleanField(default=True)
    include_brainstorm_image = models.BooleanField(default=True)
    include_image_post_summary = models.BooleanField(default=True)
    include_costs = models.BooleanField(default=False)

    subject_template = models.CharField(
        max_length=255,
        default='[Magvis] {project_title} — fertig',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Magvis Report-Konfiguration'
        verbose_name_plural = 'Magvis Report-Konfigurationen'

    def __str__(self):
        return f'Magvis-Report → {self.report_email}'


class MagvisTopicQueue(models.Model):
    """Unbegrenzte Themen-Liste. Agenten/Scheduled-Runs ziehen das nächste pending-Topic.

    pop_next() ist atomar (select_for_update + skip_locked) — bei parallelen
    Workern kann das gleiche Item nicht zweimal verwendet werden.
    """
    STATUS_PENDING = 'pending'
    STATUS_USED = 'used'
    STATUS_SKIPPED = 'skipped'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Offen'),
        (STATUS_USED, 'Verwendet'),
        (STATUS_SKIPPED, 'Übersprungen'),
        (STATUS_FAILED, 'Fehlgeschlagen'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='magvis_topics',
    )
    topic = models.CharField(max_length=500)
    keywords = models.JSONField(default=list, blank=True)
    target_audience = models.CharField(max_length=255, blank=True)
    priority = models.IntegerField(
        default=100,
        help_text='Niedriger = früher dran (0 = höchste Priorität)',
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    used_at = models.DateTimeField(null=True, blank=True)
    used_by_project = models.ForeignKey(
        'MagvisProject', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'priority']),
        ]
        verbose_name = 'Magvis Themen-Queue Eintrag'
        verbose_name_plural = 'Magvis Themen-Queue'

    def __str__(self):
        return f'[{self.status}] {self.topic[:60]}'

    @classmethod
    def pop_next(cls, user):
        """Atomar: nächstes pending-Topic des Users holen, auf 'used' setzen.

        Returns MagvisTopicQueue oder None wenn Queue leer.
        """
        with transaction.atomic():
            item = (
                cls.objects.select_for_update(skip_locked=True)
                .filter(user=user, status=cls.STATUS_PENDING)
                .order_by('priority', 'created_at')
                .first()
            )
            if item:
                item.status = cls.STATUS_USED
                item.used_at = timezone.now()
                item.save(update_fields=['status', 'used_at'])
            return item

    @classmethod
    def peek_next(cls, user):
        """Vorschau ohne Pop."""
        return (
            cls.objects.filter(user=user, status=cls.STATUS_PENDING)
            .order_by('priority', 'created_at')
            .first()
        )


class MagvisProject(models.Model):
    STAGE_CREATED = 'created'
    STAGE_SCHEDULED = 'scheduled'
    STAGE_VIDEO_RUNNING = 'video_running'
    STAGE_VIDEO_DONE = 'video_done'
    STAGE_POST_VIDEO_RUNNING = 'post_video_running'
    STAGE_POST_VIDEO_DONE = 'post_video_done'
    STAGE_PRODUCTS_RUNNING = 'products_running'
    STAGE_PRODUCTS_DONE = 'products_done'
    STAGE_BLOG_RUNNING = 'blog_running'
    STAGE_BLOG_DONE = 'blog_done'
    STAGE_IMAGE_POSTS_RUNNING = 'image_posts_running'
    STAGE_IMAGE_POSTS_DONE = 'image_posts_done'
    STAGE_REPORT_SENT = 'report_sent'
    STAGE_COMPLETED = 'completed'
    STAGE_FAILED = 'failed'

    STAGE_CHOICES = [
        (STAGE_CREATED, 'Erstellt'),
        (STAGE_SCHEDULED, 'Geplant'),
        (STAGE_VIDEO_RUNNING, 'Video läuft'),
        (STAGE_VIDEO_DONE, 'Video fertig'),
        (STAGE_POST_VIDEO_RUNNING, 'Posten läuft'),
        (STAGE_POST_VIDEO_DONE, 'Gepostet'),
        (STAGE_PRODUCTS_RUNNING, 'Produkte werden erstellt'),
        (STAGE_PRODUCTS_DONE, 'Produkte veröffentlicht'),
        (STAGE_BLOG_RUNNING, 'Blog wird erstellt'),
        (STAGE_BLOG_DONE, 'Blog fertig'),
        (STAGE_IMAGE_POSTS_RUNNING, 'Bilder werden gepostet'),
        (STAGE_IMAGE_POSTS_DONE, 'Bilder gepostet'),
        (STAGE_REPORT_SENT, 'Report verschickt'),
        (STAGE_COMPLETED, 'Abgeschlossen'),
        (STAGE_FAILED, 'Fehler'),
    ]

    # Logische Stage-Reihenfolge für advance()
    STAGE_ORDER = [
        STAGE_CREATED,
        STAGE_VIDEO_RUNNING, STAGE_VIDEO_DONE,
        STAGE_POST_VIDEO_RUNNING, STAGE_POST_VIDEO_DONE,
        STAGE_PRODUCTS_RUNNING, STAGE_PRODUCTS_DONE,
        STAGE_BLOG_RUNNING, STAGE_BLOG_DONE,
        STAGE_IMAGE_POSTS_RUNNING, STAGE_IMAGE_POSTS_DONE,
        STAGE_REPORT_SENT, STAGE_COMPLETED,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='magvis_projects',
    )

    # Eingabe
    title = models.CharField(max_length=255)
    topic = models.CharField(max_length=500)
    keywords = models.JSONField(default=list, blank=True)
    target_audience = models.CharField(max_length=255, blank=True)
    source_queue_item = models.ForeignKey(
        MagvisTopicQueue, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='spawned_projects',
    )

    # Status
    stage = models.CharField(
        max_length=32, choices=STAGE_CHOICES, default=STAGE_CREATED,
    )
    progress_pct = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    auto_advance = models.BooleanField(default=True)
    celery_eta_task_id = models.CharField(max_length=128, blank=True)

    # Sub-Objekt-Referenzen (Reuse-First)
    vidgen_project = models.ForeignKey(
        'vidgen.VideoProject', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    posted_video = models.ForeignKey(
        'videos.Video', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    youtube_url = models.URLField(blank=True)
    youtube_video_id = models.CharField(max_length=32, blank=True)

    # db_constraint=False vermeidet MySQL-Charset-Mismatches (ploom-Tabellen
    # haben gemischte utf8mb3/utf8mb4-Collations). Referenzielle Integrität
    # bleibt auf App-Ebene durch Django.
    ploom_session_1 = models.ForeignKey(
        'ploom.PLoomWorkflowSession', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    ploom_session_2 = models.ForeignKey(
        'ploom.PLoomWorkflowSession', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    product_1 = models.ForeignKey(
        'ploom.PLoomProduct', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    product_2 = models.ForeignKey(
        'ploom.PLoomProduct', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )

    task_ids = models.JSONField(default=dict, blank=True)
    stage_logs = models.JSONField(default=list, blank=True)
    cost_total = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'stage']),
            models.Index(fields=['scheduled_at']),
        ]
        verbose_name = 'Magvis-Projekt'
        verbose_name_plural = 'Magvis-Projekte'

    def __str__(self):
        return f'{self.title} [{self.stage}]'

    def log_stage(self, stage, message, level='info'):
        """Stage-Log-Eintrag anhängen."""
        self.stage_logs = (self.stage_logs or []) + [{
            'stage': stage,
            'level': level,
            'message': message,
            'ts': timezone.now().isoformat(),
        }]
        self.save(update_fields=['stage_logs', 'updated_at'])

    def next_stage_slug(self):
        """Liefert den nächsten Stage-Slug für advance()."""
        mapping = {
            self.STAGE_CREATED: 'video',
            self.STAGE_VIDEO_DONE: 'post_video',
            self.STAGE_POST_VIDEO_DONE: 'products',
            self.STAGE_PRODUCTS_DONE: 'blog',
            self.STAGE_BLOG_DONE: 'image_posts',
            self.STAGE_IMAGE_POSTS_DONE: 'report',
        }
        return mapping.get(self.stage)


class MagvisBlog(models.Model):
    project = models.OneToOneField(
        MagvisProject, on_delete=models.CASCADE, related_name='blog',
    )
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, blank=True)

    toc_html = models.TextField(blank=True)
    sections = models.JSONField(default=list, blank=True)
    quiz_data = models.JSONField(default=list, blank=True)
    minigame_data = models.JSONField(default=dict, blank=True)
    faqs = models.JSONField(default=list, blank=True)

    diagram_image_path = models.CharField(max_length=500, blank=True)
    brainstorm_image_path = models.CharField(max_length=500, blank=True)

    final_html = models.TextField(blank=True)
    shopify_blog_id = models.CharField(max_length=64, blank=True)
    shopify_article_id = models.CharField(max_length=64, blank=True)
    shopify_published_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Magvis-Blog'
        verbose_name_plural = 'Magvis-Blogs'

    def __str__(self):
        return self.seo_title or f'Magvis-Blog für {self.project.title}'


class MagvisImageAsset(models.Model):
    SOURCE_PRODUCT_AI = 'product_ai'
    SOURCE_PRODUCT_CDN = 'product_cdn'
    SOURCE_BLOG_DIAGRAM = 'blog_diagram'
    SOURCE_BLOG_BRAINSTORM = 'blog_brainstorm'
    SOURCE_CHOICES = [
        (SOURCE_PRODUCT_AI, 'Produkt KI-Bild'),
        (SOURCE_PRODUCT_CDN, 'Produkt CDN-Bild'),
        (SOURCE_BLOG_DIAGRAM, 'Blog Diagramm'),
        (SOURCE_BLOG_BRAINSTORM, 'Blog Brainstorming'),
    ]

    OVERLAY_PIL = 'pil'
    OVERLAY_GEMINI = 'gemini'
    OVERLAY_CHOICES = [
        (OVERLAY_PIL, 'PIL (Text auf Bild)'),
        (OVERLAY_GEMINI, 'Gemini (KI-Text in Bild)'),
    ]

    project = models.ForeignKey(
        MagvisProject, on_delete=models.CASCADE, related_name='image_assets',
    )
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    source_ref = models.CharField(
        max_length=255, blank=True,
        help_text='ID des Quellobjekts (z.B. PLoomProductImage.id)',
    )
    src_path = models.CharField(max_length=500)
    src_url = models.URLField(blank=True, help_text='Externe URL falls CDN-Bild')

    title_de = models.CharField(max_length=255, blank=True)
    description_de = models.TextField(blank=True)

    overlay_text = models.CharField(max_length=255, blank=True)
    use_overlay = models.BooleanField(default=False)
    overlay_method = models.CharField(
        max_length=16, choices=OVERLAY_CHOICES, default=OVERLAY_PIL,
    )
    processed_path = models.CharField(
        max_length=500, blank=True,
        help_text='Pfad zum Bild MIT Overlay (nach Processing)',
    )

    target_platforms = models.JSONField(default=list, blank=True)
    posted_status = models.JSONField(default=dict, blank=True)
    upload_post_request_id = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project', 'source', 'created_at']
        verbose_name = 'Magvis-Bild-Asset'
        verbose_name_plural = 'Magvis-Bild-Assets'

    def __str__(self):
        return f'{self.source}: {self.title_de or self.src_path[:60]}'

    @property
    def effective_path(self):
        """Liefert Pfad zum aktuell relevanten Bild (Overlay-Version falls vorhanden)."""
        return self.processed_path or self.src_path
