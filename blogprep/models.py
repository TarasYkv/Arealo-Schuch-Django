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
    # Nano Banana = Gemini 2.5 Flash Image, Nano Banana Pro = Gemini 3 Pro Image
    GEMINI_IMAGE_MODEL_CHOICES = [
        ('gemini-3-pro-image-preview', 'Nano Banana Pro'),
        ('gemini-2.5-flash-image', 'Nano Banana'),
        ('gemini-2.0-flash-exp-image-generation', 'Gemini 2.0 Flash'),
    ]
    GEMINI_IMAGE_MODEL_DESCRIPTIONS = {
        'gemini-3-pro-image-preview': 'Beste Qualität, 2K/4K, präziser Text in Bildern',
        'gemini-2.5-flash-image': 'Schnell & günstig, gute Qualität, $0.039/Bild',
        'gemini-2.0-flash-exp-image-generation': 'Schnelle Bildgenerierung, Fallback-Option',
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
        default='gemini-2.5-flash-image',  # Nano Banana als Standard
        verbose_name='Bild-Modell'
    )

    # SEO Update-Reminder Einstellungen
    update_reminder_warning_days = models.PositiveIntegerField(
        default=270,  # 9 Monate
        verbose_name='Warnung (Tage)',
        help_text='Ab diesem Alter wird eine Warnung angezeigt'
    )
    update_reminder_critical_days = models.PositiveIntegerField(
        default=365,  # 12 Monate
        verbose_name='Kritisch (Tage)',
        help_text='Ab diesem Alter ist eine Aktualisierung dringend empfohlen'
    )
    update_reminder_keywords = models.TextField(
        blank=True,
        default='2024,2025,aktuell,neu,jetzt,heute,dieses jahr',
        verbose_name='Zeitkritische Keywords',
        help_text='Komma-getrennte Liste von Keywords, die kürzere Fristen auslösen'
    )
    update_reminder_keyword_days = models.PositiveIntegerField(
        default=180,  # 6 Monate für zeitkritische Inhalte
        verbose_name='Zeitkritisch (Tage)',
        help_text='Kürzere Frist für Artikel mit zeitkritischen Keywords'
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
        verbose_name='Einleitung (~300 Wörter)'
    )
    content_main = models.TextField(
        blank=True,
        verbose_name='Hauptteil (~800 Wörter)'
    )
    content_tips = models.TextField(
        blank=True,
        verbose_name='Do\'s & Don\'ts (~300 Wörter)'
    )
    faqs = models.JSONField(
        default=list,
        blank=True,
        verbose_name='FAQs',
        help_text='Liste von {question, answer} Objekten'
    )

    # SEO Update-Reminder (projektspezifisch, überschreibt globale Einstellungen)
    custom_update_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Update-Erinnerung (Tage)',
        help_text='Leer = globale Einstellungen verwenden. Sonst: nach X Tagen als aktualisierungsbedürftig markieren'
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
    video_duration = models.FloatField(
        default=5,
        verbose_name='Video-Länge (Minuten)',
        help_text='0.25 = 15 Sek, 0.5 = 30 Sek, 1 = 1 Min'
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

    # SEO-Analyse Ergebnisse
    seo_analysis = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='SEO-Analyse',
        help_text='Ergebnisse der SEO-Analyse (Keyword-Dichte, Bild-SEO, etc.)'
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

    def get_faq_schema_json(self, pretty=True):
        """
        Generiert FAQ JSON-LD Schema für strukturierte Daten (SEO Rich Snippets).

        Args:
            pretty: Wenn True, wird das JSON formatiert ausgegeben

        Returns:
            JSON-LD Schema als String oder None wenn keine FAQs vorhanden
        """
        import json

        if not self.faqs or len(self.faqs) == 0:
            return None

        # FAQPage Schema nach Schema.org
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": []
        }

        for faq in self.faqs:
            question = faq.get("question", "").strip()
            answer = faq.get("answer", "").strip()

            if question and answer:
                schema["mainEntity"].append({
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": answer
                    }
                })

        if not schema["mainEntity"]:
            return None

        if pretty:
            return json.dumps(schema, indent=2, ensure_ascii=False)
        return json.dumps(schema, ensure_ascii=False)

    def get_faq_schema_script_tag(self):
        """
        Generiert das vollständige <script> Tag mit FAQ JSON-LD Schema.

        Returns:
            Vollständiges Script-Tag oder leerer String wenn keine FAQs
        """
        schema_json = self.get_faq_schema_json(pretty=True)
        if not schema_json:
            return ""

        return f'<script type="application/ld+json">\n{schema_json}\n</script>'

    def generate_full_html(self, base_url=None, include_title_image=False, include_section_images=True):
        """
        Generiert den vollständigen HTML-Content für den Blog.

        Args:
            base_url: Optionale Basis-URL für absolute Bild-Links (z.B. 'https://www.workloom.de')
                     Wenn angegeben, werden alle Bilder mit absoluten URLs versehen.
            include_title_image: Wenn False, wird das Titelbild NICHT im HTML eingefügt
                                (für Shopify, wo es als Article Image gesetzt wird)
            include_section_images: Wenn False, werden Abschnittsbilder (Base64) nicht eingefügt
                                   (für Shopify wegen 1MB Limit)
        """
        html_parts = []

        def get_h2_for_section(section_type):
            """Holt die H2-Überschrift aus dem Outline für einen Abschnitt"""
            if not self.outline:
                return None
            for item in self.outline:
                if item.get('section') == section_type:
                    return item.get('h2')
            return None

        def get_image_url(image_field):
            """Konvertiert Bild-URL zu absoluter URL wenn base_url gesetzt"""
            if not image_field:
                return None
            url = image_field.url
            if base_url and url.startswith('/'):
                return f"{base_url.rstrip('/')}{url}"
            return url

        def get_section_image_html(section_name):
            """Holt das Abschnittsbild für einen bestimmten Abschnitt"""
            if not include_section_images:
                return ''
            if not self.section_images:
                return ''
            for img in self.section_images:
                if img.get('section') == section_name:
                    # Alt-Text: Nutze gespeicherten oder generiere aus Keyword
                    alt_text = img.get('alt_text') or f"{self.main_keyword} - {section_name}"
                    # Bevorzuge URL (für Shopify), fallback auf Base64
                    if img.get('image_url'):
                        img_src = img['image_url']
                        # Mache URL absolut wenn base_url gesetzt
                        if base_url and img_src.startswith('/'):
                            img_src = f"{base_url.rstrip('/')}{img_src}"
                        return f'<div class="blog-section-image"><img src="{img_src}" alt="{alt_text}" style="width: 100%; max-width: 800px; height: auto; margin: 1rem 0;" /></div>'
                    elif img.get('image_data'):
                        return f'<div class="blog-section-image"><img src="data:image/png;base64,{img["image_data"]}" alt="{alt_text}" style="width: 100%; max-width: 800px; height: auto; margin: 1rem 0;" /></div>'
            return ''

        # Titelbild (nur wenn include_title_image=True)
        if include_title_image and self.title_image:
            img_url = get_image_url(self.title_image)
            html_parts.append(f'<img src="{img_url}" alt="{self.seo_title}" class="blog-title-image" style="width: 100%; max-width: 1200px; height: auto;" />')

        # Einleitung
        if self.content_intro:
            intro_h2 = get_h2_for_section('intro')
            intro_html = ''
            if intro_h2:
                intro_html = f'<h2>{intro_h2}</h2>\n'
            intro_html += f'<div class="blog-intro">{self.content_intro}</div>'
            html_parts.append(intro_html)
            # Abschnittsbild für Einleitung
            intro_img = get_section_image_html('intro')
            if intro_img:
                html_parts.append(intro_img)

        # Hauptteil
        if self.content_main:
            main_h2 = get_h2_for_section('main')
            main_html = ''
            if main_h2:
                main_html = f'<h2>{main_h2}</h2>\n'
            main_html += f'<div class="blog-main">{self.content_main}</div>'
            html_parts.append(main_html)
            # Abschnittsbild für Hauptteil
            main_img = get_section_image_html('main')
            if main_img:
                html_parts.append(main_img)

        # Diagramm
        if self.diagram_image:
            img_url = get_image_url(self.diagram_image)
            html_parts.append(f'<div class="blog-diagram"><img src="{img_url}" alt="Diagramm" style="width: 100%; max-width: 1000px; height: auto;" /></div>')

        # Tipps
        if self.content_tips:
            tips_h2 = get_h2_for_section('tips')
            tips_html = ''
            if tips_h2:
                tips_html = f'<h2>{tips_h2}</h2>\n'
            tips_html += f'<div class="blog-tips">{self.content_tips}</div>'
            html_parts.append(tips_html)
            # Abschnittsbild für Tipps
            tips_img = get_section_image_html('tips')
            if tips_img:
                html_parts.append(tips_img)

        # Benutzerdefinierte Abschnittsbilder
        custom_img = get_section_image_html('custom')
        if custom_img:
            html_parts.append(custom_img)

        # FAQs (ohne JSON-LD Schema im Body - Shopify entfernt Script-Tags)
        if self.faqs:
            # Hinweis: JSON-LD Schema für FAQs muss im Theme eingebaut werden,
            # da Shopify <script> Tags aus Blog-Content entfernt
            faq_html = '<div class="blog-faqs"><h2>Häufig gestellte Fragen</h2>'
            for faq in self.faqs:
                faq_html += f'''
                <div class="faq-item">
                    <h3>{faq.get("question", "")}</h3>
                    <p>{faq.get("answer", "")}</p>
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
        ('internal_links', 'Interne Verlinkung'),
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
