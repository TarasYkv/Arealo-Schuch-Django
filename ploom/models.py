import uuid
from django.db import models
from django.conf import settings


class PLoomSettings(models.Model):
    """Benutzer-spezifische Einstellungen für P-Loom"""

    AI_PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('gemini', 'Google Gemini'),
    ]

    WRITING_STYLE_CHOICES = [
        ('du', 'Du-Anrede'),
        ('sie', 'Sie-Anrede'),
        ('neutral', 'Neutral'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_settings'
    )
    default_store = models.ForeignKey(
        'shopify_manager.ShopifyStore',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Standard-Store"
    )
    ai_provider = models.CharField(
        max_length=20,
        choices=AI_PROVIDER_CHOICES,
        default='openai',
        verbose_name="KI-Anbieter"
    )
    ai_model = models.CharField(
        max_length=50,
        default='gpt-4o-mini',
        verbose_name="KI-Modell"
    )
    writing_style = models.CharField(
        max_length=10,
        choices=WRITING_STYLE_CHOICES,
        default='du',
        verbose_name="Schreibstil"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "P-Loom Einstellung"
        verbose_name_plural = "P-Loom Einstellungen"

    def __str__(self):
        return f"P-Loom Einstellungen für {self.user.username}"


class ProductTheme(models.Model):
    """Vorlagen für Produkterstellung"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_themes'
    )
    name = models.CharField(max_length=100, verbose_name="Name")
    title_template = models.TextField(
        blank=True,
        verbose_name="Titel-Vorlage",
        help_text="Platzhalter: {product_name}, {brand}, {category}"
    )
    description_template = models.TextField(
        blank=True,
        verbose_name="Beschreibungs-Vorlage"
    )
    seo_title_template = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="SEO-Titel-Vorlage"
    )
    seo_description_template = models.TextField(
        blank=True,
        verbose_name="SEO-Beschreibungs-Vorlage"
    )
    default_metafields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Standard-Metafelder"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Standard-Theme"
    )

    # Erweiterte Felder für Standard-Produktdaten
    default_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Standard-Preis"
    )
    default_compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Standard-Vergleichspreis"
    )
    default_vendor = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Standard-Hersteller"
    )
    default_product_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Standard-Produkttyp"
    )
    default_tags = models.TextField(
        blank=True,
        verbose_name="Standard-Tags",
        help_text="Komma-getrennte Liste"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produkt-Theme"
        verbose_name_plural = "Produkt-Themes"
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Wenn dieses Theme als Standard gesetzt wird, andere zurücksetzen
        if self.is_default:
            ProductTheme.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PLoomProduct(models.Model):
    """Produkt-Entwurf für Shopify"""

    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('ready', 'Bereit zum Upload'),
        ('uploaded', 'Hochgeladen'),
        ('error', 'Fehler'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_products'
    )
    theme = models.ForeignKey(
        ProductTheme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Theme"
    )

    # Basis-Daten
    title = models.CharField(max_length=255, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    vendor = models.CharField(max_length=100, blank=True, verbose_name="Hersteller")
    product_type = models.CharField(max_length=100, blank=True, verbose_name="Produkttyp")
    tags = models.TextField(blank=True, verbose_name="Tags", help_text="Komma-getrennte Liste")

    # SEO
    seo_title = models.CharField(
        max_length=70,
        blank=True,
        verbose_name="SEO-Titel",
        help_text="Max 70 Zeichen"
    )
    seo_description = models.TextField(
        max_length=160,
        blank=True,
        verbose_name="SEO-Beschreibung",
        help_text="Max 160 Zeichen"
    )

    # Preise
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preis"
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Vergleichspreis"
    )

    # Gewicht
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Gewicht"
    )
    weight_unit = models.CharField(
        max_length=5,
        choices=[('kg', 'kg'), ('g', 'g'), ('lb', 'lb'), ('oz', 'oz')],
        default='kg',
        verbose_name="Gewichtseinheit"
    )

    # Inventar
    track_inventory = models.BooleanField(
        default=True,
        verbose_name="Inventar verfolgen",
        help_text="Wenn aktiviert, wird der Bestand in Shopify verfolgt"
    )
    inventory_quantity = models.IntegerField(
        default=0,
        verbose_name="Bestand"
    )

    # Metafelder
    product_metafields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Produkt-Metafelder"
    )
    category_metafields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Kategorie-Metafelder"
    )

    # Kategorie/Collection
    collection_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Collection ID"
    )
    collection_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Collection Name"
    )

    # Shopify Template
    template_suffix = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Shopify Template",
        help_text="z.B. 'featured' für product.featured.liquid"
    )

    # Sales Channels / Veröffentlichungskanäle
    sales_channels = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Vertriebskanäle",
        help_text="Liste der Publication IDs für Shopify Sales Channels"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Status"
    )
    shopify_product_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Shopify Produkt-ID"
    )
    shopify_store = models.ForeignKey(
        'shopify_manager.ShopifyStore',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Shopify Store"
    )
    upload_error = models.TextField(blank=True, verbose_name="Upload-Fehler")
    uploaded_at = models.DateTimeField(null=True, blank=True, verbose_name="Hochgeladen am")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "P-Loom Produkt"
        verbose_name_plural = "P-Loom Produkte"
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Produkt {self.id}"

    @property
    def tags_list(self):
        """Gibt Tags als Liste zurück"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    @property
    def featured_image(self):
        """Gibt das Hauptbild zurück"""
        return self.images.filter(is_featured=True).first() or self.images.first()


class PLoomProductImage(models.Model):
    """Bilder für P-Loom Produkte"""

    SOURCE_CHOICES = [
        ('imageforge_generation', 'ImageForge Generierung'),
        ('imageforge_mockup', 'ImageForge Mockup'),
        ('upload', 'Eigener Upload'),
        ('external_url', 'Externe URL (Shopify/CDN)'),
    ]

    product = models.ForeignKey(
        PLoomProduct,
        on_delete=models.CASCADE,
        related_name='images'
    )
    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default='upload',
        verbose_name="Quelle"
    )

    # Referenzen zu ImageForge
    imageforge_generation = models.ForeignKey(
        'imageforge.ImageGeneration',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ImageForge Generierung"
    )
    imageforge_mockup = models.ForeignKey(
        'imageforge.ProductMockup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ImageForge Mockup"
    )

    # Eigene Uploads
    image = models.ImageField(
        upload_to='ploom/images/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Bild"
    )

    # Externe URL (Shopify CDN, Videos, etc.)
    external_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Externe URL",
        help_text="URL zu Shopify CDN, Video oder externem Bild"
    )

    # Benutzerdefinierter Dateiname
    filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dateiname",
        help_text="Benutzerdefinierter Dateiname für Shopify"
    )

    # Meta
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="Alt-Text")
    position = models.PositiveIntegerField(default=0, verbose_name="Position")
    is_featured = models.BooleanField(default=False, verbose_name="Hauptbild")
    variant_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Varianten-ID",
        help_text="Für Varianten-spezifische Bilder"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Produkt-Bild"
        verbose_name_plural = "Produkt-Bilder"
        ordering = ['position', 'created_at']

    def __str__(self):
        return f"Bild {self.position} für {self.product.title}"

    @property
    def image_url(self):
        """Gibt die Bild-URL zurück, je nach Quelle"""
        if self.source == 'upload' and self.image:
            return self.image.url
        elif self.source == 'imageforge_generation' and self.imageforge_generation:
            return self.imageforge_generation.generated_image.url if self.imageforge_generation.generated_image else None
        elif self.source == 'imageforge_mockup' and self.imageforge_mockup:
            return self.imageforge_mockup.mockup_image.url if self.imageforge_mockup.mockup_image else None
        elif self.source == 'external_url' and self.external_url:
            return self.external_url
        return None

    @property
    def is_video(self):
        """Prüft ob es sich um ein Video handelt"""
        url = self.image_url or ''
        return any(ext in url.lower() for ext in ['.mp4', '.webm', '.mov', '.avi', '/videos/'])

    def save(self, *args, **kwargs):
        # Wenn dieses Bild als Hauptbild gesetzt wird, andere zurücksetzen
        if self.is_featured:
            PLoomProductImage.objects.filter(
                product=self.product,
                is_featured=True
            ).exclude(pk=self.pk).update(is_featured=False)
        super().save(*args, **kwargs)


class PLoomImageHistory(models.Model):
    """Verlauf der verwendeten Bilder für schnellen Zugriff"""

    SOURCE_CHOICES = [
        ('upload', 'Upload'),
        ('imageforge', 'ImageForge'),
        ('external_url', 'Externe URL'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_image_history'
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='upload'
    )
    url = models.URLField(max_length=500, verbose_name="Bild-URL")
    thumbnail_url = models.URLField(max_length=500, blank=True, verbose_name="Thumbnail-URL")
    filename = models.CharField(max_length=255, blank=True, verbose_name="Dateiname")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="Alt-Text")
    usage_count = models.PositiveIntegerField(default=1, verbose_name="Verwendungen")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bild-Verlauf"
        verbose_name_plural = "Bild-Verlauf"
        ordering = ['-last_used']
        unique_together = ['user', 'url']

    def __str__(self):
        return self.filename or self.url[:50]


class PLoomProductVariant(models.Model):
    """Varianten für P-Loom Produkte"""

    INVENTORY_POLICY_CHOICES = [
        ('deny', 'Nicht verkaufen wenn ausverkauft'),
        ('continue', 'Weiter verkaufen wenn ausverkauft'),
    ]

    WEIGHT_UNIT_CHOICES = [
        ('kg', 'Kilogramm'),
        ('g', 'Gramm'),
        ('lb', 'Pfund'),
        ('oz', 'Unzen'),
    ]

    product = models.ForeignKey(
        PLoomProduct,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    title = models.CharField(max_length=255, blank=True, verbose_name="Titel")
    sku = models.CharField(max_length=100, blank=True, verbose_name="SKU")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preis"
    )
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Vergleichspreis"
    )

    # Optionen (bis zu 3)
    option1_name = models.CharField(max_length=50, blank=True, verbose_name="Option 1 Name")
    option1_value = models.CharField(max_length=100, blank=True, verbose_name="Option 1 Wert")
    option2_name = models.CharField(max_length=50, blank=True, verbose_name="Option 2 Name")
    option2_value = models.CharField(max_length=100, blank=True, verbose_name="Option 2 Wert")
    option3_name = models.CharField(max_length=50, blank=True, verbose_name="Option 3 Name")
    option3_value = models.CharField(max_length=100, blank=True, verbose_name="Option 3 Wert")

    # Erweiterte Felder
    barcode = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Barcode",
        help_text="EAN, UPC, etc."
    )
    inventory_quantity = models.IntegerField(
        default=0,
        verbose_name="Lagerbestand"
    )
    inventory_policy = models.CharField(
        max_length=10,
        choices=INVENTORY_POLICY_CHOICES,
        default='deny',
        verbose_name="Bestandsrichtlinie"
    )
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Gewicht"
    )
    weight_unit = models.CharField(
        max_length=5,
        choices=WEIGHT_UNIT_CHOICES,
        default='kg',
        verbose_name="Gewichtseinheit"
    )
    requires_shipping = models.BooleanField(
        default=True,
        verbose_name="Versand erforderlich"
    )
    taxable = models.BooleanField(
        default=True,
        verbose_name="Steuerpflichtig"
    )

    position = models.PositiveIntegerField(default=0, verbose_name="Position")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produkt-Variante"
        verbose_name_plural = "Produkt-Varianten"
        ordering = ['position', 'created_at']

    def __str__(self):
        parts = []
        if self.option1_value:
            parts.append(self.option1_value)
        if self.option2_value:
            parts.append(self.option2_value)
        if self.option3_value:
            parts.append(self.option3_value)
        return ' / '.join(parts) if parts else self.title or f"Variante {self.pk}"

    @property
    def option_string(self):
        """Gibt die Optionen als String zurück"""
        parts = []
        if self.option1_name and self.option1_value:
            parts.append(f"{self.option1_name}: {self.option1_value}")
        if self.option2_name and self.option2_value:
            parts.append(f"{self.option2_name}: {self.option2_value}")
        if self.option3_name and self.option3_value:
            parts.append(f"{self.option3_name}: {self.option3_value}")
        return ', '.join(parts)


class PLoomHistory(models.Model):
    """Verlauf für generierte Inhalte"""

    FIELD_TYPE_CHOICES = [
        ('title', 'Titel'),
        ('description', 'Beschreibung'),
        ('seo_title', 'SEO-Titel'),
        ('seo_description', 'SEO-Beschreibung'),
        ('tags', 'Tags'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_history'
    )
    product = models.ForeignKey(
        PLoomProduct,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='history'
    )
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        verbose_name="Feldtyp"
    )
    content = models.TextField(verbose_name="Inhalt")
    prompt_used = models.TextField(blank=True, verbose_name="Verwendeter Prompt")
    ai_model_used = models.CharField(max_length=50, blank=True, verbose_name="Verwendetes KI-Modell")
    is_selected = models.BooleanField(default=False, verbose_name="Ausgewählt")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "P-Loom Verlauf"
        verbose_name_plural = "P-Loom Verlauf"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_field_type_display()}: {self.content[:50]}..."


class PLoomFavoritePrice(models.Model):
    """Favoriten-Preise für schnellen Zugriff"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ploom_favorite_prices'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Preis"
    )
    label = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Bezeichnung",
        help_text="z.B. 'Standard', 'Premium'"
    )
    usage_count = models.IntegerField(
        default=0,
        verbose_name="Verwendungen"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favoriten-Preis"
        verbose_name_plural = "Favoriten-Preise"
        ordering = ['-usage_count', '-created_at']

    def __str__(self):
        if self.label:
            return f"{self.label}: {self.price} EUR"
        return f"{self.price} EUR"

    def increment_usage(self):
        """Erhöht den Verwendungszähler"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])
