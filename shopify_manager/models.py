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
    
    # PayPal-Konfiguration
    PAYPAL_ACCOUNT_TYPES = [
        ('standard', 'Standard Account'),
        ('business', 'Business Account'),
        ('handler', 'Handler Account'),
    ]
    
    paypal_account_type = models.CharField(
        max_length=20, 
        choices=PAYPAL_ACCOUNT_TYPES, 
        default='standard',
        help_text="PayPal Account-Typ für Gebührenberechnung"
    )
    paypal_monthly_volume = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Monatliches PayPal-Transaktionsvolumen für gestaffelte Gebühren"
    )
    paypal_handler_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=0.0199,
        help_text="Handler Account Gebührensatz (Standard: 1.99%)"
    )
    paypal_handler_fixed_fee = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.35,
        help_text="Handler Account Fixgebühr (Standard: 0.35€)"
    )
    
    # Google Ads API Zugangsdaten
    google_ads_customer_id = models.CharField(
        max_length=20, 
        blank=True, 
        help_text="Google Ads Customer ID (z.B. 123-456-7890)"
    )
    google_ads_developer_token = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Google Ads Developer Token"
    )
    google_ads_refresh_token = models.CharField(
        max_length=200, 
        blank=True, 
        help_text="Google Ads OAuth2 Refresh Token"
    )
    google_ads_client_id = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Google OAuth2 Client ID"
    )
    google_ads_client_secret = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Google OAuth2 Client Secret"
    )
    
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
    def collections_count(self):
        """Anzahl der Kategorien in diesem Store"""
        return self.collections.count()
    
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
    featured_image_url = models.URLField(max_length=2048, blank=True, help_text="Haupt-Produktbild URL")
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
    image_url = models.URLField(max_length=2048, help_text="Bild URL")
    alt_text = models.CharField(max_length=255, blank=True, null=True, help_text="Alt-Text")
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
    shopify_id = models.CharField(max_length=50, help_text="Shopify Blog ID")
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
    
    shopify_id = models.CharField(max_length=50, help_text="Shopify Article ID")
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
    featured_image_url = models.URLField(max_length=2048, blank=True, help_text="Haupt-Bild URL")
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
        ('import_collections', 'Collections importieren'),
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
        from django.utils import timezone
        
        if self.generated_seo_title:
            self.blog_post.seo_title = self.generated_seo_title
        if self.generated_seo_description:
            self.blog_post.seo_description = self.generated_seo_description
        
        # Markiere für Sync
        self.blog_post.needs_sync = True
        self.blog_post.save()
        
        self.is_applied = True
        self.save()
        
        # Synchronisiere zu Shopify
        from .shopify_api import ShopifyAPIClient
        api_client = ShopifyAPIClient(self.blog_post.blog.store)
        
        # Verwende update_blog_post_seo_only für SEO-only Updates
        success, message = api_client.update_blog_post_seo_only(
            self.blog_post.blog.shopify_id,
            self.blog_post.shopify_id,
            seo_title=self.blog_post.seo_title,
            seo_description=self.blog_post.seo_description
        )
        
        if success:
            self.blog_post.needs_sync = False
            self.blog_post.sync_error = ''
            self.blog_post.last_synced_at = timezone.now()
            self.blog_post.save(update_fields=['needs_sync', 'sync_error', 'last_synced_at'])
        else:
            self.blog_post.sync_error = f'SEO-Sync fehlgeschlagen: {message}'
            self.blog_post.save(update_fields=['sync_error'])


class ShippingProfile(models.Model):
    """Versandprofile für Kostenberechnung"""
    name = models.CharField(max_length=200, help_text="Name des Versandprofils")
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='shipping_profiles')
    
    # Versandkosten
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Tatsächliche Versandkosten")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.shipping_cost}€"
    
    class Meta:
        verbose_name = "Versandprofil"
        verbose_name_plural = "Versandprofile"
        unique_together = ['name', 'store']


class ProductShippingProfile(models.Model):
    """Zuordnung von Produkten zu Versandprofilen"""
    product = models.OneToOneField(ShopifyProduct, on_delete=models.CASCADE, related_name='shipping_profile')
    shipping_profile = models.ForeignKey(ShippingProfile, on_delete=models.CASCADE, related_name='products')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Produkt-Versandprofil"
        verbose_name_plural = "Produkt-Versandprofile"


class SalesData(models.Model):
    """Verkaufsdaten von Shopify"""
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='sales_data')
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='sales_data', null=True, blank=True)
    
    # Shopify Order/Line Item IDs
    shopify_order_id = models.CharField(max_length=50, help_text="Shopify Order ID")
    shopify_line_item_id = models.CharField(max_length=50, help_text="Shopify Line Item ID")
    
    # Verkaufsdaten
    order_date = models.DateTimeField(help_text="Bestelldatum")
    quantity = models.PositiveIntegerField(help_text="Verkaufte Menge")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Verkaufspreis pro Einheit")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Gesamtpreis")
    
    # Detaillierte Kostenaufschlüsselung
    # Beschaffungskosten (aus Shopify cost_per_item)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Einkaufspreis pro Einheit aus Shopify")
    
    # Versandkosten (getrennt: Shop vs. tatsächlich)
    shop_shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Versandkosten die der Kunde bezahlt hat")
    actual_shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Tatsächliche Versandkosten (aus Versandprofil)")
    
    # Provisionen und Gebühren
    shopify_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Shopify Provision")
    paypal_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="PayPal Provision")
    payment_gateway_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Payment Gateway Gebühren")
    
    # Steuern
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Mehrwertsteuer")
    
    # Payment Gateway Information
    payment_gateway = models.CharField(max_length=100, blank=True, help_text="Payment Gateway (z.B. paypal, shopify_payments, manual)")
    
    # Legacy-Feld für Rückwärtskompatibilität
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Versandkosten (Legacy - nutze shop_shipping_cost)")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        product_name = self.product.title if self.product else "Unknown Product"
        return f"{product_name} - {self.order_date.strftime('%d.%m.%Y')}"
    
    @property
    def total_cost(self):
        """Gesamtkosten berechnen"""
        cost = 0
        if self.cost_price:
            cost += self.cost_price * self.quantity
        cost += self.get_actual_shipping_cost() + self.shopify_fee + self.paypal_fee + self.payment_gateway_fee
        return cost
    
    @property
    def total_procurement_cost(self):
        """Gesamte Beschaffungskosten"""
        if self.cost_price:
            return self.cost_price * self.quantity
        return 0
    
    @property
    def total_fees(self):
        """Gesamte Gebühren (Shopify + PayPal + Payment Gateway)"""
        return self.shopify_fee + self.paypal_fee + self.payment_gateway_fee
    
    def get_actual_shipping_cost(self):
        """Tatsächliche Versandkosten oder Fallback auf Shop-Versandkosten"""
        return self.actual_shipping_cost if self.actual_shipping_cost is not None else self.shop_shipping_cost
    
    @property
    def shipping_profit_loss(self):
        """Gewinn/Verlust bei Versandkosten"""
        return self.shop_shipping_cost - self.get_actual_shipping_cost()
    
    @property
    def profit(self):
        """Gewinn berechnen"""
        return self.total_price - self.total_cost
    
    @property
    def margin(self):
        """Gewinnmarge in Prozent"""
        if self.total_price == 0:
            return 0
        return (self.profit / self.total_price) * 100
    
    def get_cost_breakdown(self):
        """Detaillierte Kostenaufschlüsselung"""
        return {
            'procurement_cost': self.total_procurement_cost,
            'shop_shipping_cost': self.shop_shipping_cost,
            'actual_shipping_cost': self.get_actual_shipping_cost(),
            'shipping_profit_loss': self.shipping_profit_loss,
            'shopify_fee': self.shopify_fee,
            'paypal_fee': self.paypal_fee,
            'payment_gateway_fee': self.payment_gateway_fee,
            'tax_amount': self.tax_amount,
            'total_cost': self.total_cost,
            'total_revenue': self.total_price,
            'profit': self.profit,
            'margin': self.margin
        }
    
    class Meta:
        verbose_name = "Verkaufsdaten"
        verbose_name_plural = "Verkaufsdaten"
        ordering = ['-order_date']
        unique_together = ['shopify_order_id', 'shopify_line_item_id']


class RecurringCost(models.Model):
    """Laufende Kosten"""
    FREQUENCY_CHOICES = [
        ('monthly', 'Monatlich'),
        ('yearly', 'Jährlich'),
        ('one_time', 'Einmalig'),
    ]
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='recurring_costs')
    name = models.CharField(max_length=200, help_text="Name der laufenden Kosten")
    description = models.TextField(blank=True, help_text="Beschreibung der Kosten")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Kostenbetrag")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    
    # Zeitraum
    start_date = models.DateField(help_text="Startdatum der Kosten")
    end_date = models.DateField(null=True, blank=True, help_text="Enddatum (optional)")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.amount}€ ({self.get_frequency_display()})"
    
    def get_monthly_cost(self):
        """Monatliche Kosten berechnen"""
        if self.frequency == 'monthly':
            return self.amount
        elif self.frequency == 'yearly':
            return self.amount / 12
        else:  # one_time
            return 0
    
    class Meta:
        verbose_name = "Laufende Kosten"
        verbose_name_plural = "Laufende Kosten"
        ordering = ['-created_at']


class AdsCost(models.Model):
    """Werbekosten"""
    PLATFORM_CHOICES = [
        ('google_ads', 'Google Ads'),
        ('facebook_ads', 'Facebook Ads'),
        ('instagram_ads', 'Instagram Ads'),
        ('tiktok_ads', 'TikTok Ads'),
        ('other', 'Andere'),
    ]
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='ads_costs')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, help_text="Werbeplattform")
    campaign_name = models.CharField(max_length=200, help_text="Name der Kampagne")
    
    # Kosten und Performance
    cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Werbekosten")
    clicks = models.PositiveIntegerField(default=0, help_text="Anzahl Klicks")
    impressions = models.PositiveIntegerField(default=0, help_text="Anzahl Impressionen")
    conversions = models.PositiveIntegerField(default=0, help_text="Anzahl Conversions")
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Umsatz aus Werbung")
    
    # Zeitraum
    date = models.DateField(help_text="Datum der Werbemaßnahme")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.campaign_name} - {self.cost}€ ({self.date})"
    
    @property
    def roas(self):
        """Return on Ad Spend berechnen"""
        if self.cost == 0:
            return 0
        return self.revenue / self.cost
    
    @property
    def cpc(self):
        """Cost per Click berechnen"""
        if self.clicks == 0:
            return 0
        return self.cost / self.clicks
    
    @property
    def cpm(self):
        """Cost per Mille (1000 Impressionen) berechnen"""
        if self.impressions == 0:
            return 0
        return (self.cost / self.impressions) * 1000
    
    @property
    def conversion_rate(self):
        """Conversion Rate berechnen"""
        if self.clicks == 0:
            return 0
        return (self.conversions / self.clicks) * 100
    
    class Meta:
        verbose_name = "Werbekosten"
        verbose_name_plural = "Werbekosten"
        ordering = ['-date']


class GoogleAdsProductData(models.Model):
    """Google Ads Daten pro Produkt"""
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='google_ads_product_data')
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='google_ads_data')
    
    # Google Ads Identifikatoren
    campaign_id = models.CharField(max_length=100, help_text="Google Ads Campaign ID")
    campaign_name = models.CharField(max_length=200, help_text="Campaign Name")
    ad_group_id = models.CharField(max_length=100, null=True, blank=True, help_text="Ad Group ID")
    ad_group_name = models.CharField(max_length=200, null=True, blank=True, help_text="Ad Group Name")
    
    # Performance Metriken
    impressions = models.PositiveIntegerField(default=0, help_text="Anzahl Impressionen")
    clicks = models.PositiveIntegerField(default=0, help_text="Anzahl Klicks")
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Werbekosten")
    conversions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Anzahl Conversions")
    conversion_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Conversion Wert")
    
    # Zeitraum
    date = models.DateField(help_text="Datum der Daten")
    
    # Berechnete Metriken
    ctr = models.DecimalField(max_digits=6, decimal_places=4, default=0.0000, help_text="Click-Through-Rate")
    cpc = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Cost per Click")
    conversion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0.0000, help_text="Conversion Rate")
    roas = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Return on Ad Spend")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Berechne abgeleitete Metriken
        if self.impressions > 0:
            self.ctr = self.clicks / self.impressions
        if self.clicks > 0:
            self.cpc = self.cost / self.clicks
            self.conversion_rate = self.conversions / self.clicks
        if self.cost > 0:
            self.roas = self.conversion_value / self.cost
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Google Ads Produktdaten"
        verbose_name_plural = "Google Ads Produktdaten"
        unique_together = [['store', 'product', 'campaign_id', 'date']]
        ordering = ['-date']


class ShopifyCollection(models.Model):
    """Shopify Collection/Category Model für lokale Verwaltung"""
    STATUS_CHOICES = [
        ('active', 'Aktiv'),
        ('archived', 'Archiviert'),
        ('draft', 'Entwurf'),
    ]
    
    COLLECTION_TYPE_CHOICES = [
        ('custom', 'Custom Collection'),
        ('smart', 'Smart Collection'),
    ]
    
    # Shopify IDs
    shopify_id = models.CharField(max_length=50, help_text="Shopify Collection ID")
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='collections')
    collection_type = models.CharField(max_length=20, choices=COLLECTION_TYPE_CHOICES, default='custom', help_text="Typ der Collection (Custom oder Smart)")
    
    # Grunddaten
    title = models.CharField(max_length=255, help_text="Kategorie-Titel")
    handle = models.CharField(max_length=255, help_text="URL Handle")
    description = models.TextField(blank=True, help_text="Kategorie-Beschreibung")
    
    # SEO Daten
    seo_title = models.CharField(max_length=70, blank=True, help_text="SEO Titel (max. 70 Zeichen)")
    seo_description = models.TextField(max_length=160, blank=True, help_text="SEO Beschreibung (max. 160 Zeichen)")
    
    # Bilder
    image_url = models.URLField(max_length=2048, blank=True, help_text="Kategorie-Bild URL")
    image_alt = models.CharField(max_length=255, blank=True, help_text="Alt-Text für Kategorie-Bild")
    
    # Sortierung und Sichtbarkeit
    sort_order = models.CharField(max_length=50, blank=True, help_text="Sortierung der Produkte")
    published = models.BooleanField(default=True, help_text="Ist die Kategorie veröffentlicht?")
    
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
    raw_shopify_data = models.JSONField(default=dict, blank=True, help_text="Komplette Shopify Collection-Daten")
    
    def __str__(self):
        return f"{self.title} ({self.shopify_id})"
    
    class Meta:
        verbose_name = "Shopify Kategorie"
        verbose_name_plural = "Shopify Kategorien"
        unique_together = ['shopify_id', 'store']
        ordering = ['-updated_at']
    
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
        """Berechnet Alt-Text-Status für Kategorie-Bild"""
        if self.image_url and self.image_alt:
            return 'good'
        elif self.image_url and not self.image_alt:
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
        if self.image_url:
            has_alt = bool(self.image_alt)
            return {
                'total_images': 1,
                'images_with_alt': 1 if has_alt else 0,
                'percentage': 100 if has_alt else 0,
                'status': self.get_alt_text_status()
            }
        return {'total_images': 0, 'images_with_alt': 0, 'percentage': 0, 'status': 'poor'}
    
    def get_absolute_url(self):
        return reverse('shopify_manager:collection_detail', kwargs={'pk': self.pk})
    
    def get_edit_url(self):
        return reverse('shopify_manager:collection_edit', kwargs={'pk': self.pk})
    
    def get_shopify_admin_url(self):
        """Gibt die Shopify Admin URL für die Kategorie zurück"""
        return f"https://{self.store.shop_domain}/admin/collections/{self.shopify_id}"
    
    def get_storefront_url(self):
        """Gibt die Shop-URL für die Kategorie zurück"""
        # Nutze Custom Domain falls gesetzt
        if self.store.custom_domain:
            return f"https://{self.store.custom_domain}/collections/{self.handle}"
        
        # Fallback: Nutze Shopify Domain
        return f"https://{self.store.shop_domain}/collections/{self.handle}"
    
    def mark_for_sync(self):
        """Markiert die Kategorie für Synchronisation"""
        self.needs_sync = True
        self.sync_error = ""
        self.save(update_fields=['needs_sync', 'sync_error'])
    
    def clear_sync_error(self):
        """Löscht Sync-Fehler"""
        self.sync_error = ""
        self.save(update_fields=['sync_error'])
    
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
    
    @property
    def products_count(self):
        """Anzahl der Produkte in dieser Kategorie"""
        # Dies würde eine Many-to-Many-Beziehung zu Produkten erfordern
        # Für jetzt als Platzhalter
        return 0


class CollectionSEOOptimization(models.Model):
    """SEO-Optimierung für Kategorien mit KI-Unterstützung"""
    
    AI_MODEL_CHOICES = [
        ('openai-gpt4', 'OpenAI GPT-4'),
        ('openai-gpt4o', 'OpenAI GPT-4o'),
        ('openai-gpt4o-mini', 'OpenAI GPT-4o Mini'),
        ('openai-gpt35', 'OpenAI GPT-3.5 Turbo'),
    ]
    
    collection = models.ForeignKey(ShopifyCollection, on_delete=models.CASCADE, related_name='seo_optimizations')
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
        verbose_name = "Kategorie SEO-Optimierung"
        verbose_name_plural = "Kategorie SEO-Optimierungen"
    
    def __str__(self):
        return f"SEO für {self.collection.title} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def get_keywords_list(self):
        """Gibt Keywords als Liste zurück"""
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]
    
    def apply_to_collection(self):
        """Wendet die generierten SEO-Daten auf die Kategorie an"""
        if self.generated_seo_title:
            self.collection.seo_title = self.generated_seo_title
        if self.generated_seo_description:
            self.collection.seo_description = self.generated_seo_description
        
        self.collection.needs_sync = True
        self.collection.save()
        
        self.is_applied = True
        self.save()


class SalesStatistics(models.Model):
    """Vorberechnete Verkaufsstatistiken für Performance"""
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='sales_statistics')
    
    # Zeitraum
    date = models.DateField(help_text="Datum der Statistik")
    period_type = models.CharField(max_length=20, choices=[
        ('daily', 'Täglich'),
        ('weekly', 'Wöchentlich'),
        ('monthly', 'Monatlich'),
    ], default='daily')
    
    # Verkaufszahlen
    total_orders = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Kosten
    total_shipping_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_shopify_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_paypal_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_ads_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_recurring_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Statistik {self.store.name} - {self.date} ({self.get_period_type_display()})"
    
    @property
    def contribution_margin(self):
        """Deckungsbeitrag berechnen"""
        return self.total_revenue - self.total_cost - self.total_recurring_costs
    
    @property
    def margin_percentage(self):
        """Gewinnmarge in Prozent"""
        if self.total_revenue == 0:
            return 0
        return (self.total_profit / self.total_revenue) * 100
    
    @property
    def roas(self):
        """Return on Ad Spend für den Zeitraum"""
        if self.total_ads_costs == 0:
            return 0
        return self.total_revenue / self.total_ads_costs
    
    class Meta:
        verbose_name = "Verkaufsstatistik"
        verbose_name_plural = "Verkaufsstatistiken"
        ordering = ['-date']
        unique_together = ['store', 'date', 'period_type']


class ShopifyProductCollection(models.Model):
    """Many-to-Many-Beziehung zwischen Produkten und Kategorien"""
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='collections')
    collection = models.ForeignKey(ShopifyCollection, on_delete=models.CASCADE, related_name='products')
    
    # Shopify-spezifische Felder
    shopify_product_id = models.CharField(max_length=50, help_text="Shopify Product ID")
    shopify_collection_id = models.CharField(max_length=50, help_text="Shopify Collection ID")
    
    # Position des Produkts in der Kategorie
    position = models.PositiveIntegerField(default=1, help_text="Position in der Kategorie")
    
    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Produkt-Kategorie-Zuordnung"
        verbose_name_plural = "Produkt-Kategorie-Zuordnungen"
        unique_together = ['product', 'collection']
        ordering = ['position']
    
    def __str__(self):
        return f"{self.product.title} in {self.collection.title}"


# ============================================
# BACKUP & RESTORE MODELS
# ============================================

class ShopifyBackup(models.Model):
    """Hauptmodel für Backup-Sessions"""
    BACKUP_STATUS = [
        ('pending', 'Ausstehend'),
        ('running', 'Läuft'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopify_backups')
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='backups')
    name = models.CharField(max_length=255, help_text="Name des Backups z.B. 'Vollbackup 2025-01-15'")
    status = models.CharField(max_length=20, choices=BACKUP_STATUS, default='pending')

    # Backup-Optionen
    include_products = models.BooleanField(default=True, help_text="Produkte sichern")
    include_product_images = models.BooleanField(default=False, help_text="Produktbilder herunterladen")
    include_blogs = models.BooleanField(default=True, help_text="Blogs und Posts sichern")
    include_blog_images = models.BooleanField(default=False, help_text="Blog-Bilder herunterladen")
    include_collections = models.BooleanField(default=True, help_text="Collections sichern")
    include_orders = models.BooleanField(default=False, help_text="Bestellungen sichern")
    include_customers = models.BooleanField(default=False, help_text="Kundendaten sichern")
    include_pages = models.BooleanField(default=True, help_text="Statische Seiten sichern")
    include_menus = models.BooleanField(default=True, help_text="Navigationsmenüs sichern")
    include_redirects = models.BooleanField(default=True, help_text="URL-Weiterleitungen sichern")
    include_metafields = models.BooleanField(default=False, help_text="Metafields sichern")
    include_discounts = models.BooleanField(default=False, help_text="Rabattcodes sichern")

    # Statistiken
    products_count = models.IntegerField(default=0)
    blogs_count = models.IntegerField(default=0)
    posts_count = models.IntegerField(default=0)
    collections_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    customers_count = models.IntegerField(default=0)
    pages_count = models.IntegerField(default=0)
    menus_count = models.IntegerField(default=0)
    redirects_count = models.IntegerField(default=0)
    metafields_count = models.IntegerField(default=0)
    discounts_count = models.IntegerField(default=0)
    images_count = models.IntegerField(default=0)
    total_size_bytes = models.BigIntegerField(default=0)

    # Fortschritts-Tracking
    current_step = models.CharField(max_length=50, blank=True, help_text="Aktueller Backup-Schritt")
    progress_message = models.CharField(max_length=255, blank=True, help_text="Aktuelle Fortschrittsnachricht")

    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Shopify Backup"
        verbose_name_plural = "Shopify Backups"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.store.name} ({self.get_status_display()})"

    @property
    def total_items_count(self):
        """Gesamtzahl aller gesicherten Elemente"""
        return (
            self.products_count + self.blogs_count + self.posts_count +
            self.collections_count + self.orders_count + self.customers_count +
            self.pages_count + self.menus_count + self.redirects_count +
            self.metafields_count + self.discounts_count
        )

    def get_size_display(self):
        """Formatierte Größenanzeige"""
        if self.total_size_bytes < 1024:
            return f"{self.total_size_bytes} B"
        elif self.total_size_bytes < 1024 * 1024:
            return f"{self.total_size_bytes / 1024:.1f} KB"
        elif self.total_size_bytes < 1024 * 1024 * 1024:
            return f"{self.total_size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.total_size_bytes / (1024 * 1024 * 1024):.2f} GB"


class BackupItem(models.Model):
    """Einzelne Elemente eines Backups"""
    ITEM_TYPES = [
        ('product', 'Produkt'),
        ('product_image', 'Produktbild'),
        ('blog', 'Blog'),
        ('blog_post', 'Blog-Beitrag'),
        ('blog_image', 'Blog-Bild'),
        ('collection', 'Collection'),
        ('order', 'Bestellung'),
        ('customer', 'Kunde'),
        ('page', 'Seite'),
        ('menu', 'Menü'),
        ('redirect', 'Weiterleitung'),
        ('metafield', 'Metafield'),
        ('discount', 'Rabattcode'),
    ]

    backup = models.ForeignKey(ShopifyBackup, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    shopify_id = models.BigIntegerField(help_text="Shopify ID des Elements")
    title = models.CharField(max_length=500, help_text="Titel/Name für Anzeige")
    raw_data = models.JSONField(help_text="Komplette API-Antwort als JSON")
    image_data = models.BinaryField(null=True, blank=True, help_text="Optional: Bild als Blob")
    image_url = models.URLField(max_length=2048, blank=True, help_text="Original Bild-URL")
    parent_id = models.BigIntegerField(null=True, blank=True, help_text="Parent ID z.B. Blog-ID für Posts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Backup-Element"
        verbose_name_plural = "Backup-Elemente"
        ordering = ['item_type', 'title']
        indexes = [
            models.Index(fields=['backup', 'item_type']),
            models.Index(fields=['shopify_id']),
        ]

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.title}"

    def get_data_size(self):
        """Größe der gespeicherten Daten in Bytes"""
        size = len(json.dumps(self.raw_data).encode('utf-8'))
        if self.image_data:
            size += len(self.image_data)
        return size


class RestoreLog(models.Model):
    """Log für Wiederherstellungen"""
    RESTORE_STATUS = [
        ('success', 'Erfolgreich'),
        ('skipped', 'Übersprungen'),
        ('failed', 'Fehlgeschlagen'),
        ('exists', 'Existiert bereits'),
    ]

    backup = models.ForeignKey(ShopifyBackup, on_delete=models.CASCADE, related_name='restore_logs')
    backup_item = models.ForeignKey(BackupItem, on_delete=models.CASCADE, related_name='restore_logs')
    status = models.CharField(max_length=20, choices=RESTORE_STATUS)
    new_shopify_id = models.BigIntegerField(null=True, blank=True, help_text="Neue Shopify ID nach Wiederherstellung")
    message = models.TextField(blank=True, help_text="Status-Nachricht oder Fehlerbeschreibung")
    restored_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Wiederherstellungs-Log"
        verbose_name_plural = "Wiederherstellungs-Logs"
        ordering = ['-restored_at']

    def __str__(self):
        return f"{self.backup_item} - {self.get_status_display()}"