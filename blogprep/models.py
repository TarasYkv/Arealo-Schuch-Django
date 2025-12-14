from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class BlogPrepSettings(models.Model):
    """Einstellungen pro User für BlogPrep"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blogprep_settings'
    )

    # Unternehmensinformationen
    company_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Unternehmensname'
    )
    company_description = models.TextField(
        blank=True,
        verbose_name='Unternehmensbeschreibung',
        help_text='Beschreibe dein Unternehmen, seine Geschichte und Werte'
    )
    company_expertise = models.TextField(
        blank=True,
        verbose_name='Fachgebiete & Expertise',
        help_text='In welchen Bereichen bist du/ist dein Unternehmen Experte?'
    )

    WRITING_STYLE_CHOICES = [
        ('du', 'Du-Form (persönlich, nahbar)'),
        ('sie', 'Sie-Form (formell, professionell)'),
        ('neutral', 'Neutral (ohne direkte Anrede)'),
    ]
    writing_style = models.CharField(
        max_length=20,
        choices=WRITING_STYLE_CHOICES,
        default='du',
        verbose_name='Schreibstil'
    )

    # Produkte
    product_info = models.TextField(
        blank=True,
        verbose_name='Produktinformationen',
        help_text='Beschreibe deine Hauptprodukte oder Dienstleistungen'
    )
    product_links = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Produktlinks',
        help_text='URLs zu deinen Produktseiten (werden automatisch analysiert)'
    )
    scraped_product_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Extrahierte Produktdaten'
    )

    # KI-Einstellungen für Text
    AI_PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('gemini', 'Google Gemini'),
    ]
    ai_provider = models.CharField(
        max_length=20,
        choices=AI_PROVIDER_CHOICES,
        default='openai',
        verbose_name='KI-Anbieter (Text)'
    )

    # OpenAI Modelle (Stand: Dezember 2025)
    OPENAI_MODEL_CHOICES = [
        ('gpt-4.1', 'GPT-4.1'),
        ('gpt-4.1-mini', 'GPT-4.1 Mini'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
        ('o4-mini', 'o4-mini'),
    ]
    OPENAI_MODEL_DESCRIPTIONS = {
        'gpt-4.1': 'Neuestes Modell, 1M Context, beste Coding-Performance',
        'gpt-4.1-mini': 'Schnell & günstig, übertrifft GPT-4o, 83% günstiger',
        'gpt-4o': 'Bewährt, multimodal, 128K Context',
        'gpt-4o-mini': 'Günstig & schnell, ideal für einfache Aufgaben',
        'o4-mini': 'Reasoning-Modell für komplexe Logik',
    }

    # Gemini Modelle (Stand: Dezember 2025)
    GEMINI_MODEL_CHOICES = [
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
    ]
    GEMINI_MODEL_DESCRIPTIONS = {
        'gemini-2.5-pro': 'Beste Qualität, komplexes Reasoning, 1M Context',
        'gemini-2.5-flash': 'Schnell & intelligent, gute Balance',
        'gemini-2.0-flash': 'Günstig, gut für einfache Aufgaben',
    }

    ai_model = models.CharField(
        max_length=50,
        default='gpt-4o',
        verbose_name='KI-Modell'
    )

    # Bild-Einstellungen
    IMAGE_PROVIDER_CHOICES = [
        ('gemini', 'Google Gemini'),
        ('dalle', 'OpenAI DALL-E'),
    ]
    image_provider = models.CharField(
        max_length=20,
        choices=IMAGE_PROVIDER_CHOICES,
        default='gemini',
        verbose_name='KI-Anbieter (Bilder)'
    )

    # Bild-Modelle (Stand: Dezember 2025)
    GEMINI_IMAGE_MODEL_CHOICES = [
        ('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image'),
        ('imagen-3.0-generate-002', 'Imagen 3'),
    ]
    GEMINI_IMAGE_MODEL_DESCRIPTIONS = {
        'gemini-2.5-flash-image': 'Neuestes Modell, Editing & Multi-Image, $0.039/Bild',
        'imagen-3.0-generate-002': 'Hohe Qualität, fotorealistisch, $0.04/Bild',
    }

    DALLE_IMAGE_MODEL_CHOICES = [
        ('gpt-image-1', 'GPT Image 1'),
        ('dall-e-3', 'DALL-E 3'),
    ]
    DALLE_IMAGE_MODEL_DESCRIPTIONS = {
        'gpt-image-1': 'Neuestes Modell, beste Qualität, präzise Prompts',
        'dall-e-3': 'Bewährt, gute Qualität, $0.04-0.12/Bild',
    }

    image_model = models.CharField(
        max_length=50,
        default='gemini-2.5-flash-image',
        verbose_name='Bild-Modell'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'BlogPrep Einstellung'
        verbose_name_plural = 'BlogPrep Einstellungen'

    def __str__(self):
        return f"BlogPrep Settings für {self.user.username}"

    @classmethod
    def get_model_choices(cls, provider):
        """Gibt die verfügbaren Modelle für einen Provider zurück"""
        if provider == 'openai':
            return cls.OPENAI_MODEL_CHOICES
        elif provider == 'gemini':
            return cls.GEMINI_MODEL_CHOICES
        elif provider == 'anthropic':
            return cls.ANTHROPIC_MODEL_CHOICES
        return []


class BlogPrepProject(models.Model):
    """Ein einzelnes Blog-Projekt"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blogprep_projects'
    )

    # Metadaten
    title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Projekttitel'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Status
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('step1', 'Keywords eingegeben'),
        ('step2', 'Recherche abgeschlossen'),
        ('step3', 'Content erstellt'),
        ('step4', 'Bilder erstellt'),
        ('step5', 'Diagramm erstellt'),
        ('step6', 'Video-Skript erstellt'),
        ('step7', 'Bereit zum Export'),
        ('completed', 'Exportiert'),
        ('published', 'Veröffentlicht'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Schritt 1: Keywords
    main_keyword = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Hauptkeyword'
    )
    secondary_keywords = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Sekundäre Keywords'
    )

    # Schritt 2: Recherche-Ergebnisse
    research_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Recherche-Daten',
        help_text='Top-Themen, verwandte Keywords, Leserfragen'
    )
    outline = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Gliederung',
        help_text='H2-Überschriften und Struktur'
    )

    # Schritt 3: Content
    seo_title = models.CharField(
        max_length=70,
        blank=True,
        verbose_name='SEO-Titel'
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='Meta-Beschreibung'
    )
    summary = models.TextField(
        blank=True,
        verbose_name='Zusammenfassung'
    )
    content_intro = models.TextField(
        blank=True,
        verbose_name='Einleitung (~800 Wörter)'
    )
    content_main = models.TextField(
        blank=True,
        verbose_name='Hauptteil (~800 Wörter)'
    )
    content_tips = models.TextField(
        blank=True,
        verbose_name='Tipps & Do\'s/Don\'ts (~800 Wörter)'
    )
    faqs = models.JSONField(
        default=list,
        blank=True,
        verbose_name='FAQs',
        help_text='Liste von {question, answer} Objekten'
    )

    # Schritt 4: Bilder
    title_image = models.ImageField(
        upload_to='blogprep/images/',
        blank=True,
        null=True,
        verbose_name='Titelbild'
    )
    title_image_prompt = models.TextField(
        blank=True,
        verbose_name='Titelbild-Prompt'
    )
    section_images = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Abschnittsbilder',
        help_text='Liste von {section, image_path, prompt} Objekten'
    )

    # Schritt 5: Diagramm (Optional)
    skip_diagram = models.BooleanField(
        default=False,
        verbose_name='Diagramm überspringen'
    )
    DIAGRAM_TYPE_CHOICES = [
        ('bar', 'Balkendiagramm'),
        ('pie', 'Tortendiagramm'),
        ('line', 'Liniendiagramm'),
        ('comparison', 'Vergleichstabelle'),
        ('flow', 'Flussdiagramm'),
        ('timeline', 'Zeitstrahl'),
    ]
    diagram_type = models.CharField(
        max_length=20,
        choices=DIAGRAM_TYPE_CHOICES,
        blank=True,
        verbose_name='Diagrammtyp'
    )
    diagram_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Diagramm-Daten'
    )
    diagram_image = models.ImageField(
        upload_to='blogprep/diagrams/',
        blank=True,
        null=True,
        verbose_name='Diagramm-Bild'
    )

    # Schritt 6: Video-Skript (Optional)
    skip_video = models.BooleanField(
        default=False,
        verbose_name='Video-Skript überspringen'
    )
    video_duration = models.IntegerField(
        default=5,
        verbose_name='Video-Länge (Minuten)'
    )
    video_script = models.TextField(
        blank=True,
        verbose_name='Video-Skript'
    )

    # Schritt 7: Export
    shopify_store = models.ForeignKey(
        'shopify_manager.ShopifyStore',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blogprep_projects',
        verbose_name='Shopify Store'
    )
    shopify_blog = models.ForeignKey(
        'shopify_manager.ShopifyBlog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blogprep_projects',
        verbose_name='Shopify Blog'
    )
    shopify_article_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Shopify Article ID'
    )
    exported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Exportiert am'
    )

    # Vollständiger HTML-Content
    full_html_content = models.TextField(
        blank=True,
        verbose_name='Vollständiger HTML-Content'
    )

    class Meta:
        verbose_name = 'BlogPrep Projekt'
        verbose_name_plural = 'BlogPrep Projekte'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Blog: {self.main_keyword}" or f"Projekt {self.id}"

    def get_progress_percentage(self):
        """Berechnet den Fortschritt in Prozent"""
        status_progress = {
            'draft': 0,
            'step1': 14,
            'step2': 28,
            'step3': 42,
            'step4': 57,
            'step5': 71,
            'step6': 85,
            'step7': 95,
            'completed': 100,
            'published': 100,
        }
        return status_progress.get(self.status, 0)

    def get_current_step_number(self):
        """Gibt die aktuelle Schrittnummer zurück"""
        status_to_step = {
            'draft': 1,
            'step1': 2,
            'step2': 3,
            'step3': 4,
            'step4': 5,
            'step5': 6,
            'step6': 7,
            'step7': 7,
            'completed': 7,
            'published': 7,
        }
        return status_to_step.get(self.status, 1)

    def get_word_count(self):
        """Zählt die Wörter im Content"""
        total = 0
        for field in [self.content_intro, self.content_main, self.content_tips]:
            if field:
                total += len(field.split())
        return total

    def generate_full_html(self):
        """Generiert den vollständigen HTML-Content für den Blog"""
        html_parts = []

        # Titelbild
        if self.title_image:
            html_parts.append(f'<img src="{self.title_image.url}" alt="{self.seo_title}" class="blog-title-image" />')

        # Einleitung
        if self.content_intro:
            html_parts.append(f'<div class="blog-intro">{self.content_intro}</div>')

        # Hauptteil
        if self.content_main:
            html_parts.append(f'<div class="blog-main">{self.content_main}</div>')

        # Diagramm
        if self.diagram_image:
            html_parts.append(f'<div class="blog-diagram"><img src="{self.diagram_image.url}" alt="Diagramm" /></div>')

        # Tipps
        if self.content_tips:
            html_parts.append(f'<div class="blog-tips">{self.content_tips}</div>')

        # FAQs
        if self.faqs:
            faq_html = '<div class="blog-faqs"><h2>Häufig gestellte Fragen</h2>'
            for faq in self.faqs:
                faq_html += f'''
                <div class="faq-item" itemscope itemtype="https://schema.org/Question">
                    <h3 itemprop="name">{faq.get("question", "")}</h3>
                    <div itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">
                        <p itemprop="text">{faq.get("answer", "")}</p>
                    </div>
                </div>
                '''
            faq_html += '</div>'
            html_parts.append(faq_html)

        self.full_html_content = '\n'.join(html_parts)
        return self.full_html_content


class BlogPrepGenerationLog(models.Model):
    """Log für KI-Generierungen (für Debugging und Kostentracking)"""

    project = models.ForeignKey(
        BlogPrepProject,
        on_delete=models.CASCADE,
        related_name='generation_logs'
    )

    STEP_CHOICES = [
        ('research', 'Web-Recherche'),
        ('outline', 'Gliederung'),
        ('content_intro', 'Einleitung'),
        ('content_main', 'Hauptteil'),
        ('content_tips', 'Tipps'),
        ('faqs', 'FAQs'),
        ('seo', 'SEO-Meta'),
        ('image_title', 'Titelbild'),
        ('image_section', 'Abschnittsbild'),
        ('diagram', 'Diagramm'),
        ('video_script', 'Video-Skript'),
    ]
    step = models.CharField(max_length=20, choices=STEP_CHOICES)

    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=50)
    prompt = models.TextField()
    response = models.TextField()

    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)

    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.FloatField(default=0)

    class Meta:
        verbose_name = 'Generierungs-Log'
        verbose_name_plural = 'Generierungs-Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.step} - {self.project.main_keyword} ({self.created_at})"
