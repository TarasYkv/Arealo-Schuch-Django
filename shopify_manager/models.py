from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Count, Q
import json

User = get_user_model()


class ShopifyStore(models.Model):
    """Shopify Store Konfiguration"""
    name = models.CharField(max_length=200, help_text="Name des Shops")
    shop_domain = models.CharField(max_length=200, help_text="mystore.myshopify.com")
    access_token = models.CharField(max_length=255, help_text="Shopify Access Token")
    api_key = models.CharField(max_length=255, blank=True, help_text="Shopify API Key")
    api_secret = models.CharField(max_length=255, blank=True, help_text="Shopify API Secret")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopify_stores')
    description = models.TextField(blank=True, help_text="Optionale Beschreibung")
    custom_domain = models.CharField(max_length=200, blank=True, help_text="Custom Domain (z.B. naturmacher.de)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.shop_domain})"
    
    def get_api_url(self):
        """Gibt die Shopify API Base URL zurück"""
        return f"https://{self.shop_domain}/admin/api/2023-10"
    
    @property
    def products_count(self):
        """Anzahl der Produkte in diesem Store"""
        return self.products.count()
    
    @property
    def sync_problems_count(self):
        """Anzahl der Produkte mit Sync-Problemen"""
        return self.products.filter(
            Q(needs_sync=True) | ~Q(sync_error='')
        ).count()
    
    @property
    def last_sync(self):
        """Zeitpunkt der letzten Synchronisation"""
        last_log = self.sync_logs.filter(
            status__in=['success', 'partial']
        ).order_by('-completed_at').first()
        return last_log.completed_at if last_log else None
    
    
    class Meta:
        verbose_name = "Shopify Store"
        verbose_name_plural = "Shopify Stores"
        unique_together = ['shop_domain', 'user']


class ShopifyProduct(models.Model):
    """Shopify Product Model für lokale Verwaltung"""
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('archived', 'Archiviert'),
        ('draft', 'Entwurf'),
    ]
    
    # Shopify IDs
    shopify_id = models.CharField(max_length=50, help_text="Shopify Product ID")
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='products')
    
    # Grunddaten
    title = models.CharField(max_length=255, help_text="Produkttitel")
    handle = models.CharField(max_length=255, help_text="URL Handle")
    body_html = models.TextField(blank=True, help_text="Produktbeschreibung (HTML)")
    vendor = models.CharField(max_length=255, blank=True, help_text="Hersteller")
    product_type = models.CharField(max_length=255, blank=True, help_text="Produkttyp")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # SEO Daten
    seo_title = models.CharField(max_length=70, blank=True, help_text="SEO Titel (max. 70 Zeichen)")
    seo_description = models.TextField(max_length=160, blank=True, help_text="SEO Beschreibung (max. 160 Zeichen)")
    
    # Bilder
    featured_image_url = models.URLField(blank=True, help_text="Haupt-Produktbild URL")
    featured_image_alt = models.CharField(max_length=255, blank=True, help_text="Alt-Text für Hauptbild")
    
    # Preise
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Tags und Kategorien
    tags = models.TextField(blank=True, help_text="Tags (kommagetrennt)")
    
    # Sync-Status
    last_synced_at = models.DateTimeField(null=True, blank=True)
    needs_sync = models.BooleanField(default=False, help_text="Wurde lokal geändert und muss synchronisiert werden")
    sync_error = models.TextField(blank=True, help_text="Letzter Sync-Fehler")
    
    # Metadaten
    shopify_created_at = models.DateTimeField(null=True, blank=True)
    shopify_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Raw Shopify Data für erweiterte Felder
    raw_shopify_data = models.JSONField(default=dict, blank=True, help_text="Komplette Shopify Produktdaten")
    
    
    def __str__(self):
        return f"{self.title} ({self.shopify_id})"
    
    class Meta:
        verbose_name = "Shopify Produkt"
        verbose_name_plural = "Shopify Produkte"
        unique_together = ['shopify_id', 'store']
    
    def get_seo_status(self):
        """Berechnet SEO-Status nur für SEO-Titel und SEO-Beschreibung (good/warning/poor)"""
        seo_score = 0
        
        # SEO-Titel Bewertung (50 Punkte möglich)
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:  # Optimale Länge
                seo_score += 50
            elif 20 <= title_length <= 80:  # Akzeptable Länge
                seo_score += 30
            else:  # Zu kurz oder zu lang
                seo_score += 15
        
        # SEO-Beschreibung Bewertung (50 Punkte möglich)
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:  # Optimale Länge
                seo_score += 50
            elif 80 <= desc_length <= 180:  # Akzeptable Länge
                seo_score += 30
            else:  # Zu kurz oder zu lang
                seo_score += 15
        
        # Status bestimmen (0-100 Punkte, nur SEO-Felder)
        if seo_score >= 80:  # Sehr gut
            return 'good'
        elif seo_score >= 40:  # Verbesserungsbedarf
            return 'warning'
        else:  # Schlecht
            return 'poor'
    
    def get_seo_score(self):
        """Berechnet numerischen SEO-Score (0-100)"""
        seo_score = 0
        
        # SEO-Titel Bewertung (40 Punkte möglich)
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:
                seo_score += 40
            elif 20 <= title_length <= 80:
                seo_score += 25
            else:
                seo_score += 10
        
        # SEO-Beschreibung Bewertung (40 Punkte möglich)
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:
                seo_score += 40
            elif 80 <= desc_length <= 180:
                seo_score += 25
            else:
                seo_score += 10
        
        # Alt-Text Bewertung (20 Punkte möglich)
        alt_status = self.get_alt_text_status()
        if alt_status == 'good':
            seo_score += 20
        elif alt_status == 'warning':
            seo_score += 10
        
        return min(seo_score, 100)  # Maximum 100 Punkte
    
    def get_combined_seo_status(self):
        """Berechnet kombinierten SEO-Status mit Alt-Text Beschränkung (good/warning/poor)"""
        seo_score = self.get_seo_score()
        alt_status = self.get_alt_text_status()
        
        # WICHTIG: Kein "good" Status wenn Alt-Texte schlecht sind (ab 80/100 + gute Alt-Texte = grün)
        if alt_status == 'poor':
            # Bei schlechten Alt-Texten maximal "warning" möglich
            if seo_score >= 40:
                return 'warning'
            else:
                return 'poor'
        else:
            # Normale Bewertung wenn Alt-Texte ok sind
            if seo_score >= 80:  # Sehr gut
                return 'good'
            elif seo_score >= 40:  # Verbesserungsbedarf
                return 'warning'
            else:  # Schlecht
                return 'poor'
    
    def get_alt_text_status(self):
        """Berechnet Alt-Text-Status für Ampelsystem (good/warning/poor)"""
        if not self.raw_shopify_data:
            return 'poor'
        
        images = self.raw_shopify_data.get('images', [])
        if not images:
            return 'poor'  # Keine Bilder vorhanden
        
        total_images = len(images)
        images_with_alt = 0
        
        for image in images:
            alt_text = image.get('alt', '').strip() if image.get('alt') else ''
            if alt_text:
                images_with_alt += 1
        
        # Prozentualer Anteil der Bilder mit Alt-Text
        alt_percentage = (images_with_alt / total_images) * 100
        
        if alt_percentage >= 80:  # 80%+ haben Alt-Texte
            return 'good'
        elif alt_percentage >= 40:  # 40-79% haben Alt-Texte
            return 'warning'
        else:  # Weniger als 40% haben Alt-Texte
            return 'poor'
    
    def get_seo_details(self):
        """Gibt detaillierte SEO-Informationen zurück"""
        # Berechne einzelne Score-Komponenten
        title_score = 0
        desc_score = 0
        alt_score = 0
        
        # SEO-Titel Score
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:
                title_score = 40
            elif 20 <= title_length <= 80:
                title_score = 25
            else:
                title_score = 10
        
        # SEO-Beschreibung Score
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:
                desc_score = 40
            elif 80 <= desc_length <= 180:
                desc_score = 25
            else:
                desc_score = 10
        
        # Alt-Text Score
        alt_status = self.get_alt_text_status()
        if alt_status == 'good':
            alt_score = 20
        elif alt_status == 'warning':
            alt_score = 10
        
        return {
            'title_length': len(self.seo_title) if self.seo_title else 0,
            'description_length': len(self.seo_description) if self.seo_description else 0,
            'has_title': bool(self.seo_title),
            'has_description': bool(self.seo_description),
            'status': self.get_seo_status(),
            'combined_status': self.get_combined_seo_status(),
            'total_score': self.get_seo_score(),
            'title_score': title_score,
            'description_score': desc_score,
            'alt_text_score': alt_score,
            'breakdown': f'SEO-Titel: {title_score}/40, SEO-Beschreibung: {desc_score}/40, Alt-Texte: {alt_score}/20'
        }
    
    def get_alt_text_details(self):
        """Gibt detaillierte Alt-Text-Informationen zurück"""
        if not self.raw_shopify_data:
            return {'total_images': 0, 'images_with_alt': 0, 'percentage': 0, 'status': 'poor'}
        
        images = self.raw_shopify_data.get('images', [])
        total_images = len(images)
        
        if total_images == 0:
            return {'total_images': 0, 'images_with_alt': 0, 'percentage': 0, 'status': 'poor'}
        
        images_with_alt = sum(1 for img in images if img.get('alt') and str(img.get('alt')).strip())
        percentage = (images_with_alt / total_images) * 100
        
        return {
            'total_images': total_images,
            'images_with_alt': images_with_alt,
            'percentage': round(percentage, 1),
            'status': self.get_alt_text_status()
        }
    
    def get_absolute_url(self):
        return reverse('shopify_manager:product_detail', kwargs={'pk': self.pk})
    
    def get_edit_url(self):
        return reverse('shopify_manager:product_edit', kwargs={'pk': self.pk})
    
    @property
    def image_url(self):
        """Alias für featured_image_url für Template-Kompatibilität"""
        return self.featured_image_url
    
    def get_shopify_admin_url(self):
        """Gibt die Shopify Admin URL für das Produkt zurück"""
        return f"https://{self.store.shop_domain}/admin/products/{self.shopify_id}"
    
    def get_storefront_url(self):
        """Gibt die Shop-URL für das Produkt zurück"""
        # Nutze Custom Domain falls gesetzt
        if self.store.custom_domain:
            return f"https://{self.store.custom_domain}/products/{self.handle}"
        
        # Fallback: Nutze Shopify Domain
        return f"https://{self.store.shop_domain}/products/{self.handle}"
    
    def get_tags_list(self):
        """Gibt Tags als Liste zurück"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def set_tags_from_list(self, tags_list):
        """Setzt Tags aus einer Liste"""
        self.tags = ', '.join(tags_list)
    
    def mark_for_sync(self):
        """Markiert das Produkt für Synchronisation"""
        self.needs_sync = True
        self.sync_error = ""
        self.save(update_fields=['needs_sync', 'sync_error'])
    
    def clear_sync_error(self):
        """Löscht Sync-Fehler"""
        self.sync_error = ""
        self.save(update_fields=['sync_error'])
    
    def has_seo_issues(self):
        """Prüft ob das Produkt SEO-Probleme hat"""
        return {
            'missing_seo_title': not self.seo_title,
            'missing_seo_description': not self.seo_description,
            'seo_title_too_long': len(self.seo_title) > 70 if self.seo_title else False,
            'seo_description_too_long': len(self.seo_description) > 160 if self.seo_description else False,
        }
    
    def get_seo_title_length(self):
        """Gibt die Länge des SEO Titels zurück"""
        return len(self.seo_title) if self.seo_title else 0
    
    def get_seo_description_length(self):
        """Gibt die Länge der SEO Beschreibung zurück"""
        return len(self.seo_description) if self.seo_description else 0
    
    def has_seo_issues(self):
        """Prüft ob es SEO-Probleme gibt"""
        issues = []
        if not self.seo_title:
            issues.append("Kein SEO-Titel")
        elif len(self.seo_title) > 70:
            issues.append("SEO-Titel zu lang")
        
        if not self.seo_description:
            issues.append("Keine SEO-Beschreibung")
        elif len(self.seo_description) > 160:
            issues.append("SEO-Beschreibung zu lang")
        
        return issues
    
    class Meta:
        verbose_name = "Shopify Produkt"
        verbose_name_plural = "Shopify Produkte"
        ordering = ['-updated_at']


class ShopifyProductImage(models.Model):
    """Zusätzliche Produktbilder"""
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='images')
    shopify_image_id = models.CharField(max_length=50, help_text="Shopify Image ID")
    image_url = models.URLField(help_text="Bild URL")
    alt_text = models.CharField(max_length=255, blank=True, help_text="Alt-Text")
    position = models.PositiveIntegerField(default=1, help_text="Reihenfolge der Bilder")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Bild {self.position} für {self.product.title}"
    
    class Meta:
        verbose_name = "Produktbild"
        verbose_name_plural = "Produktbilder"
        ordering = ['position']


class ProductSEOOptimization(models.Model):
    """SEO-Optimierung für ein Produkt mit KI-Unterstützung"""
    
    AI_MODEL_CHOICES = [
        ('openai-gpt4', 'OpenAI GPT-4'),
        ('openai-gpt35', 'OpenAI GPT-3.5 Turbo'),
        ('claude-3-sonnet', 'Claude 3 Sonnet'),
        ('claude-3-haiku', 'Claude 3 Haiku'),
        ('gemini-pro', 'Google Gemini Pro'),
    ]
    
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='seo_optimizations')
    keywords = models.TextField(help_text="Kommagetrennte Keywords für SEO-Optimierung")
    ai_model = models.CharField(max_length=50, choices=AI_MODEL_CHOICES, default='openai-gpt4')
    
    # Original Daten (zur Referenz)
    original_title = models.CharField(max_length=255, blank=True)
    original_description = models.TextField(blank=True)
    original_seo_title = models.CharField(max_length=70, blank=True)
    original_seo_description = models.CharField(max_length=160, blank=True)
    
    # KI-generierte SEO Daten
    generated_seo_title = models.CharField(max_length=70, blank=True)
    generated_seo_description = models.CharField(max_length=160, blank=True)
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_applied = models.BooleanField(default=False, help_text="Wurden die generierten SEO-Daten angewendet?")
    ai_prompt_used = models.TextField(blank=True, help_text="Der verwendete AI-Prompt")
    ai_response_raw = models.TextField(blank=True, help_text="Rohe AI-Antwort für Debug")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "SEO-Optimierung"
        verbose_name_plural = "SEO-Optimierungen"
    
    def __str__(self):
        return f"SEO für {self.product.title} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def get_keywords_list(self):
        """Gibt Keywords als Liste zurück"""
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]
    
    def apply_to_product(self):
        """Wendet die generierten SEO-Daten auf das Produkt an"""
        if self.generated_seo_title:
            self.product.seo_title = self.generated_seo_title
        if self.generated_seo_description:
            self.product.seo_description = self.generated_seo_description
        
        self.product.needs_sync = True
        self.product.save()
        
        self.is_applied = True
        self.save()



class SEOAnalysisResult(models.Model):
    """Gespeicherte SEO-Analyse-Ergebnisse"""
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='seo_analyses')
    
    # Analysezeitpunkt
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Zusammenfassung
    total_products = models.PositiveIntegerField(default=0)
    products_with_good_seo = models.PositiveIntegerField(default=0)
    products_with_poor_seo = models.PositiveIntegerField(default=0)
    products_with_alt_texts = models.PositiveIntegerField(default=0)
    products_without_alt_texts = models.PositiveIntegerField(default=0)
    
    # Legacy-Felder für Kompatibilität
    products_with_global_seo = models.PositiveIntegerField(default=0)
    products_with_woo_data = models.PositiveIntegerField(default=0)
    products_with_webrex_data = models.PositiveIntegerField(default=0)
    products_with_no_metafields = models.PositiveIntegerField(default=0)
    
    # Detaillierte Ergebnisse als JSON
    detailed_results = models.JSONField(default=list, blank=True)
    
    # Cache-Status
    is_current = models.BooleanField(default=True, help_text="Ist diese Analyse noch aktuell?")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "SEO-Analyse-Ergebnis"
        verbose_name_plural = "SEO-Analyse-Ergebnisse"
        
    def __str__(self):
        return f"SEO-Analyse {self.store.name} vom {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def get_overall_score(self):
        """Berechnet den Gesamt-SEO-Score"""
        if self.total_products == 0:
            return 0
        return round((self.products_with_good_seo / self.total_products) * 100)
    
    def invalidate_cache(self):
        """Markiert diese Analyse als veraltet"""
        self.is_current = False
        self.save(update_fields=['is_current'])
    
    @classmethod
    def get_latest_for_store(cls, store):
        """Holt die neueste aktuelle Analyse für einen Store"""
        return cls.objects.filter(store=store, is_current=True).first()
    
    @classmethod 
    def invalidate_store_cache(cls, store):
        """Invalidiert alle Analysen für einen Store"""
        cls.objects.filter(store=store, is_current=True).update(is_current=False)


class ShopifyBlog(models.Model):
    """Shopify Blog Model"""
    shopify_id = models.CharField(max_length=50, unique=True, help_text="Shopify Blog ID")
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='blogs')
    
    # Grunddaten
    title = models.CharField(max_length=255, help_text="Blog-Titel")
    handle = models.CharField(max_length=255, help_text="URL Handle")
    
    # Meta-Daten
    shopify_created_at = models.DateTimeField(null=True, blank=True)
    shopify_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Raw Shopify Data
    raw_shopify_data = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.title} ({self.shopify_id})"
    
    @property
    def posts_count(self):
        """Anzahl der Blog-Posts"""
        return self.posts.count()
    
    def get_shopify_admin_url(self):
        """Gibt die Shopify Admin URL für den Blog zurück"""
        return f"https://{self.store.shop_domain}/admin/blogs/{self.shopify_id}"
    
    def get_storefront_url(self):
        """Gibt die Shop-URL für den Blog zurück"""
        if self.store.custom_domain:
            return f"https://{self.store.custom_domain}/blogs/{self.handle}"
        return f"https://{self.store.shop_domain}/blogs/{self.handle}"
    
    class Meta:
        verbose_name = "Shopify Blog"
        verbose_name_plural = "Shopify Blogs"
        ordering = ['-updated_at']
        unique_together = ['shopify_id', 'store']


class ShopifyBlogPost(models.Model):
    """Shopify Blog Post Model"""
    STATUS_CHOICES = [
        ('published', 'Veröffentlicht'),
        ('draft', 'Entwurf'),
        ('hidden', 'Versteckt'),
    ]
    
    shopify_id = models.CharField(max_length=50, unique=True, help_text="Shopify Article ID")
    blog = models.ForeignKey(ShopifyBlog, on_delete=models.CASCADE, related_name='posts')
    
    # Grunddaten
    title = models.CharField(max_length=255, help_text="Beitrag-Titel")
    handle = models.CharField(max_length=255, help_text="URL Handle")
    content = models.TextField(help_text="Beitrag-Inhalt (HTML)")
    summary = models.TextField(blank=True, help_text="Zusammenfassung")
    author = models.CharField(max_length=255, blank=True, help_text="Autor")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # SEO Daten
    seo_title = models.CharField(max_length=70, blank=True, help_text="SEO Titel (max. 70 Zeichen)")
    seo_description = models.TextField(max_length=160, blank=True, help_text="SEO Beschreibung (max. 160 Zeichen)")
    
    # Bilder
    featured_image_url = models.URLField(blank=True, help_text="Haupt-Bild URL")
    featured_image_alt = models.CharField(max_length=255, blank=True, help_text="Alt-Text für Hauptbild")
    
    # Tags
    tags = models.TextField(blank=True, help_text="Tags (kommagetrennt)")
    
    # Veröffentlichung
    published_at = models.DateTimeField(null=True, blank=True, help_text="Veröffentlichungsdatum")
    
    # Sync-Status
    last_synced_at = models.DateTimeField(null=True, blank=True)
    needs_sync = models.BooleanField(default=False, help_text="Wurde lokal geändert und muss synchronisiert werden")
    sync_error = models.TextField(blank=True, help_text="Letzter Sync-Fehler")
    
    # Meta-Daten
    shopify_created_at = models.DateTimeField(null=True, blank=True)
    shopify_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Raw Shopify Data
    raw_shopify_data = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.title} ({self.shopify_id})"
    
    def get_seo_status(self):
        """Berechnet SEO-Status nur für SEO-Titel und SEO-Beschreibung (good/warning/poor)"""
        seo_score = 0
        
        # SEO-Titel Bewertung (50 Punkte möglich)
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:  # Optimale Länge
                seo_score += 50
            elif 20 <= title_length <= 80:  # Akzeptable Länge
                seo_score += 30
            else:  # Zu kurz oder zu lang
                seo_score += 15
        
        # SEO-Beschreibung Bewertung (50 Punkte möglich)
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:  # Optimale Länge
                seo_score += 50
            elif 80 <= desc_length <= 180:  # Akzeptable Länge
                seo_score += 30
            else:  # Zu kurz oder zu lang
                seo_score += 15
        
        # Status bestimmen (0-100 Punkte, nur SEO-Felder)
        if seo_score >= 80:  # Sehr gut
            return 'good'
        elif seo_score >= 40:  # Verbesserungsbedarf
            return 'warning'
        else:  # Schlecht
            return 'poor'
    
    def get_seo_score(self):
        """Berechnet numerischen SEO-Score (0-100)"""
        seo_score = 0
        
        # SEO-Titel Bewertung (40 Punkte möglich)
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:
                seo_score += 40
            elif 20 <= title_length <= 80:
                seo_score += 25
            else:
                seo_score += 10
        
        # SEO-Beschreibung Bewertung (40 Punkte möglich)
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:
                seo_score += 40
            elif 80 <= desc_length <= 180:
                seo_score += 25
            else:
                seo_score += 10
        
        # Alt-Text Bewertung (20 Punkte möglich)
        alt_status = self.get_alt_text_status()
        if alt_status == 'good':
            seo_score += 20
        elif alt_status == 'warning':
            seo_score += 10
        
        return min(seo_score, 100)  # Maximum 100 Punkte
    
    def get_combined_seo_status(self):
        """Berechnet kombinierten SEO-Status mit Alt-Text Beschränkung (good/warning/poor)"""
        seo_score = self.get_seo_score()
        alt_status = self.get_alt_text_status()
        
        # WICHTIG: Kein "good" Status wenn Alt-Texte schlecht sind (ab 80/100 + gute Alt-Texte = grün)
        if alt_status == 'poor':
            # Bei schlechten Alt-Texten maximal "warning" möglich
            if seo_score >= 40:
                return 'warning'
            else:
                return 'poor'
        else:
            # Normale Bewertung wenn Alt-Texte ok sind
            if seo_score >= 80:  # Sehr gut
                return 'good'
            elif seo_score >= 40:  # Verbesserungsbedarf
                return 'warning'
            else:  # Schlecht
                return 'poor'
    
    def get_alt_text_status(self):
        """Berechnet Alt-Text-Status für Bilder im Beitrag"""
        # Prüfe Haupt-Bild
        if self.featured_image_url and self.featured_image_alt:
            return 'good'
        elif self.featured_image_url and not self.featured_image_alt:
            return 'warning'
        else:
            return 'poor'
    
    def get_seo_details(self):
        """Gibt detaillierte SEO-Informationen zurück"""
        # Berechne einzelne Score-Komponenten
        title_score = 0
        desc_score = 0
        alt_score = 0
        
        # SEO-Titel Score
        if self.seo_title:
            title_length = len(self.seo_title)
            if 30 <= title_length <= 70:
                title_score = 40
            elif 20 <= title_length <= 80:
                title_score = 25
            else:
                title_score = 10
        
        # SEO-Beschreibung Score
        if self.seo_description:
            desc_length = len(self.seo_description)
            if 120 <= desc_length <= 160:
                desc_score = 40
            elif 80 <= desc_length <= 180:
                desc_score = 25
            else:
                desc_score = 10
        
        # Alt-Text Score
        alt_status = self.get_alt_text_status()
        if alt_status == 'good':
            alt_score = 20
        elif alt_status == 'warning':
            alt_score = 10
        
        return {
            'title_length': len(self.seo_title) if self.seo_title else 0,
            'description_length': len(self.seo_description) if self.seo_description else 0,
            'has_title': bool(self.seo_title),
            'has_description': bool(self.seo_description),
            'status': self.get_seo_status(),
            'combined_status': self.get_combined_seo_status(),
            'total_score': self.get_seo_score(),
            'title_score': title_score,
            'description_score': desc_score,
            'alt_text_score': alt_score,
            'breakdown': f'SEO-Titel: {title_score}/40, SEO-Beschreibung: {desc_score}/40, Alt-Texte: {alt_score}/20'
        }
    
    def get_alt_text_details(self):
        """Gibt detaillierte Alt-Text-Informationen zurück"""
        # Für Blog-Posts prüfen wir das Featured Image
        has_featured_image = bool(self.featured_image_url)
        has_alt_text = bool(self.featured_image_alt)
        
        if not has_featured_image:
            return {'total_images': 0, 'images_with_alt': 0, 'percentage': 0, 'status': 'poor'}
        
        percentage = 100 if has_alt_text else 0
        
        return {
            'total_images': 1 if has_featured_image else 0,
            'images_with_alt': 1 if has_alt_text else 0,
            'percentage': percentage,
            'status': self.get_alt_text_status()
        }
    
    def get_tags_list(self):
        """Gibt Tags als Liste zurück"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def mark_for_sync(self):
        """Markiert den Blog-Post für Synchronisation"""
        self.needs_sync = True
        self.sync_error = ""
        self.save(update_fields=['needs_sync', 'sync_error'])
    
    def clear_sync_error(self):
        """Löscht Sync-Fehler"""
        self.sync_error = ""
        self.save(update_fields=['sync_error'])
    
    def get_shopify_admin_url(self):
        """Gibt die Shopify Admin URL für den Blog-Post zurück"""
        return f"https://{self.blog.store.shop_domain}/admin/blogs/{self.blog.shopify_id}/articles/{self.shopify_id}"
    
    def get_storefront_url(self):
        """Gibt die Shop-URL für den Blog-Post zurück"""
        if self.blog.store.custom_domain:
            return f"https://{self.blog.store.custom_domain}/blogs/{self.blog.handle}/{self.handle}"
        return f"https://{self.blog.store.shop_domain}/blogs/{self.blog.handle}/{self.handle}"
    
    class Meta:
        verbose_name = "Shopify Blog Post"
        verbose_name_plural = "Shopify Blog Posts"
        ordering = ['-published_at', '-updated_at']
        unique_together = ['shopify_id', 'blog']


class ShopifySyncLog(models.Model):
    """Log für Synchronisationsvorgänge"""
    ACTION_CHOICES = [
        ('import', 'Import von Shopify'),
        ('export', 'Export zu Shopify'),
        ('update', 'Update zu Shopify'),
        ('sync_all', 'Alle Produkte synchronisieren'),
        ('import_blogs', 'Blogs importieren'),
        ('import_blog_posts', 'Blog-Posts importieren'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Erfolgreich'),
        ('error', 'Fehler'),
        ('partial', 'Teilweise erfolgreich'),
    ]
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='sync_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    products_processed = models.PositiveIntegerField(default=0)
    products_success = models.PositiveIntegerField(default=0)
    products_failed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.get_status_display()} ({self.started_at})"
    
    class Meta:
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
        ordering = ['-started_at']


class BlogPostSEOOptimization(models.Model):
    """SEO-Optimierung für Blog-Posts mit KI-Unterstützung"""
    
    AI_MODEL_CHOICES = [
        ('openai-gpt4', 'OpenAI GPT-4'),
        ('openai-gpt35', 'OpenAI GPT-3.5 Turbo'),
        ('claude-3-sonnet', 'Claude 3 Sonnet'),
        ('claude-3-haiku', 'Claude 3 Haiku'),
        ('gemini-pro', 'Google Gemini Pro'),
    ]
    
    blog_post = models.ForeignKey(ShopifyBlogPost, on_delete=models.CASCADE, related_name='seo_optimizations')
    keywords = models.TextField(help_text="Kommagetrennte Keywords für SEO-Optimierung")
    ai_model = models.CharField(max_length=50, choices=AI_MODEL_CHOICES, default='openai-gpt4')
    
    # Original Daten (zur Referenz)
    original_title = models.CharField(max_length=255, blank=True)
    original_content = models.TextField(blank=True)
    original_summary = models.TextField(blank=True)
    original_seo_title = models.CharField(max_length=70, blank=True)
    original_seo_description = models.CharField(max_length=160, blank=True)
    
    # KI-generierte SEO Daten
    generated_seo_title = models.CharField(max_length=70, blank=True)
    generated_seo_description = models.CharField(max_length=160, blank=True)
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_applied = models.BooleanField(default=False, help_text="Wurden die generierten SEO-Daten angewendet?")
    ai_prompt_used = models.TextField(blank=True, help_text="Der verwendete AI-Prompt")
    ai_response_raw = models.TextField(blank=True, help_text="Rohe AI-Antwort für Debug")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Blog-Post SEO-Optimierung"
        verbose_name_plural = "Blog-Post SEO-Optimierungen"
    
    def __str__(self):
        return f"SEO für {self.blog_post.title} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def get_keywords_list(self):
        """Gibt Keywords als Liste zurück"""
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]
    
    def apply_to_blog_post(self):
        """Wendet die generierten SEO-Daten auf den Blog-Post an"""
        if self.generated_seo_title:
            self.blog_post.seo_title = self.generated_seo_title
        if self.generated_seo_description:
            self.blog_post.seo_description = self.generated_seo_description
        
        self.blog_post.save()
        
        self.is_applied = True
        self.save()