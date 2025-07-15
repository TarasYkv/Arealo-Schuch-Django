from django import forms
from .models import ShopifyStore, ShopifyProduct, ProductSEOOptimization, ShopifyBlogPost, BlogPostSEOOptimization, ShopifyCollection, CollectionSEOOptimization


class ShopifyStoreForm(forms.ModelForm):
    """Form für Shopify Store Konfiguration"""
    
    access_token = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'shpat_...'
        }),
        help_text="Private App Access Token oder Admin API Token"
    )
    
    class Meta:
        model = ShopifyStore
        fields = [
            'name', 'shop_domain', 'custom_domain', 'access_token', 'description', 
            'paypal_account_type', 'paypal_monthly_volume', 'paypal_handler_rate', 
            'paypal_handler_fixed_fee', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mein Shopify Store'
            }),
            'shop_domain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'meinshop.myshopify.com'
            }),
            'custom_domain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'naturmacher.de (optional)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optionale Beschreibung für internen Gebrauch'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'api_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional für Public Apps'
            }),
            'api_secret': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional für Public Apps'
            }),
            'paypal_account_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'paypal_monthly_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'paypal_handler_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.0199',
                'step': '0.0001'
            }),
            'paypal_handler_fixed_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.35',
                'step': '0.01'
            }),
        }
    
    def clean_shop_domain(self):
        domain = self.cleaned_data.get('shop_domain')
        if domain:
            # Entferne https:// falls vorhanden
            domain = domain.replace('https://', '').replace('http://', '')
            # Stelle sicher, dass .myshopify.com am Ende steht
            if not domain.endswith('.myshopify.com'):
                if '.' not in domain:
                    domain = f"{domain}.myshopify.com"
        return domain


class ShopifyProductEditForm(forms.ModelForm):
    """Form für Shopify Produkt Bearbeitung"""
    
    class Meta:
        model = ShopifyProduct
        fields = [
            'title', 'body_html', 'vendor', 'product_type', 'status',
            'seo_title', 'seo_description', 'featured_image_alt', 'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Produkttitel'
            }),
            'body_html': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Produktbeschreibung (HTML unterstützt)'
            }),
            'vendor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hersteller/Marke'
            }),
            'product_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Produktkategorie'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'seo_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO Titel (max. 70 Zeichen)',
                'maxlength': 70
            }),
            'seo_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'SEO Beschreibung (max. 160 Zeichen)',
                'maxlength': 160
            }),
            'featured_image_alt': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alt-Text für Hauptbild'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tags (kommagetrennt)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Füge Character Counter für SEO Felder hinzu
        self.fields['seo_title'].widget.attrs.update({
            'data-counter': 'seo-title-counter',
            'data-max': '70'
        })
        self.fields['seo_description'].widget.attrs.update({
            'data-counter': 'seo-description-counter',
            'data-max': '160'
        })
    
    def clean_seo_title(self):
        seo_title = self.cleaned_data.get('seo_title', '')
        if len(seo_title) > 70:
            raise forms.ValidationError('SEO Titel darf maximal 70 Zeichen lang sein.')
        return seo_title
    
    def clean_seo_description(self):
        seo_description = self.cleaned_data.get('seo_description', '')
        if len(seo_description) > 160:
            raise forms.ValidationError('SEO Beschreibung darf maximal 160 Zeichen lang sein.')
        return seo_description
    
    def save(self, commit=True):
        product = super().save(commit=False)
        
        print(f"=== FORM SAVE DEBUG ===")
        print(f"Form cleaned_data SEO-Titel: '{self.cleaned_data.get('seo_title', '')}'")
        print(f"Form cleaned_data SEO-Beschreibung: '{self.cleaned_data.get('seo_description', '')}'")
        print(f"Product instance SEO-Titel: '{product.seo_title}'")
        print(f"Product instance SEO-Beschreibung: '{product.seo_description}'")
        
        if commit:
            product.save()
            # Markiere das Produkt für Synchronisation
            product.needs_sync = True
            product.sync_error = ""
            product.save(update_fields=['needs_sync', 'sync_error'])
            
            print(f"Nach final save:")
            print(f"Product SEO-Titel: '{product.seo_title}'")
            print(f"Product SEO-Beschreibung: '{product.seo_description}'")
        
        return product


class ProductFilterForm(forms.Form):
    """Form für Produktfilter"""
    
    SORT_CHOICES = [
        ('-updated_at', 'Zuletzt bearbeitet'),
        ('title', 'Titel A-Z'),
        ('-title', 'Titel Z-A'),
        ('-shopify_updated_at', 'Zuletzt in Shopify geändert'),
        ('price', 'Preis aufsteigend'),
        ('-price', 'Preis absteigend'),
    ]
    
    STATUS_CHOICES = [
        ('', 'Alle Status'),
        ('active', 'Aktiv'),
        ('draft', 'Entwurf'),
        ('archived', 'Archiviert'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('', 'Alle'),
        ('needs_sync', 'Benötigt Sync'),
        ('sync_error', 'Sync-Fehler'),
        ('synced', 'Synchronisiert'),
    ]
    
    SEO_SCORE_CHOICES = [
        ('', 'Alle SEO-Scores'),
        ('good', 'Gut (≥80 Punkte)'),
        ('warning', 'Warnung (40-79 Punkte)'),
        ('poor', 'Schlecht (<40 Punkte)'),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Titel, Beschreibung, Tags...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial='active',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sync_status = forms.ChoiceField(
        choices=SYNC_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    vendor = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Hersteller'
        })
    )
    
    product_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Produkttyp'
        })
    )
    
    sort = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-updated_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    seo_score = forms.ChoiceField(
        choices=SEO_SCORE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    seo_issues_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class BlogPostFilterForm(forms.Form):
    """Form für Blog-Post Filter"""
    
    SORT_CHOICES = [
        ('-updated_at', 'Zuletzt bearbeitet'),
        ('title', 'Titel A-Z'),
        ('-title', 'Titel Z-A'),
        ('-published_at', 'Zuletzt veröffentlicht'),
        ('published_at', 'Zuerst veröffentlicht'),
        ('-shopify_updated_at', 'Zuletzt in Shopify geändert'),
    ]
    
    STATUS_CHOICES = [
        ('', 'Alle Status'),
        ('published', 'Sichtbar'),
        ('draft', 'Ausgeblendet'),
        ('hidden', 'Versteckt'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('', 'Alle'),
        ('needs_sync', 'Benötigt Sync'),
        ('sync_error', 'Sync-Fehler'),
        ('synced', 'Synchronisiert'),
    ]
    
    SEO_SCORE_CHOICES = [
        ('', 'Alle SEO-Scores'),
        ('good', 'Gut (≥80 Punkte)'),
        ('warning', 'Warnung (40-79 Punkte)'),
        ('poor', 'Schlecht (<40 Punkte)'),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Titel, Inhalt, Tags...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial='published',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sync_status = forms.ChoiceField(
        choices=SYNC_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    author = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Autor'
        })
    )
    
    sort = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-updated_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    seo_score = forms.ChoiceField(
        choices=SEO_SCORE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    seo_issues_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class BulkActionForm(forms.Form):
    """Form für Bulk-Aktionen auf Produkte"""
    
    ACTION_CHOICES = [
        ('', 'Aktion wählen...'),
        ('sync_to_shopify', 'Zu Shopify synchronisieren'),
        ('mark_needs_sync', 'Für Sync markieren'),
        ('clear_sync_errors', 'Sync-Fehler löschen'),
        ('update_status_active', 'Status: Aktiv setzen'),
        ('update_status_draft', 'Status: Entwurf setzen'),
        ('update_status_archived', 'Status: Archiviert setzen'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    selected_products = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    def clean_selected_products(self):
        product_ids = self.cleaned_data.get('selected_products', '')
        if not product_ids:
            raise forms.ValidationError('Keine Produkte ausgewählt.')
        
        try:
            # Konvertiere zu Liste von Integers
            ids = [int(id.strip()) for id in product_ids.split(',') if id.strip()]
            if not ids:
                raise forms.ValidationError('Keine gültigen Produkt-IDs gefunden.')
            return ids
        except ValueError:
            raise forms.ValidationError('Ungültige Produkt-IDs.')


class ProductImportForm(forms.Form):
    """Form für Produktimport von Shopify"""
    
    IMPORT_MODE_CHOICES = [
        ('all', 'Alle Produkte (überschreibt bestehende)'),
        ('new_only', 'Nur neue Produkte (überspringt bestehende)'),
    ]
    
    import_mode = forms.ChoiceField(
        choices=IMPORT_MODE_CHOICES,
        initial='new_only',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text="Wählen Sie, ob alle Produkte oder nur neue Produkte importiert werden sollen"
    )
    
    limit = forms.IntegerField(
        required=False,  # Nicht required, da bei "Alle Produkte" ignoriert
        initial=50,
        min_value=1,
        max_value=250,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '50'
        }),
        help_text="Anzahl der zu importierenden Produkte (max. 250)"
    )
    
    overwrite_existing = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Bestehende Produkte mit Shopify-Daten überschreiben (nur bei 'Alle Produkte')"
    )
    
    import_images = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Produktbilder mit importieren"
    )


class SEOOptimizationForm(forms.ModelForm):
    """Form für KI-gestützte SEO-Optimierung"""
    
    class Meta:
        model = ProductSEOOptimization
        fields = ['keywords', 'ai_model']
        widgets = {
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'baby, ratgeber, entwicklung, eltern',
                'data-bs-toggle': 'tooltip',
                'title': 'Kommagetrennte Keywords für SEO-Optimierung'
            }),
            'ai_model': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        
        # Initialisiere Keywords basierend auf Produktdaten
        if self.product and not self.instance.pk:
            suggested_keywords = self._generate_suggested_keywords()
            if suggested_keywords:
                self.fields['keywords'].widget.attrs['placeholder'] = suggested_keywords
    
    def _generate_suggested_keywords(self):
        """Generiert Keyword-Vorschläge basierend auf Produktdaten"""
        if not self.product:
            return ""
        
        keywords = []
        
        # Aus Titel extrahieren
        title_words = [word.lower().strip('.,!?"-()') for word in self.product.title.split() 
                      if len(word.strip('.,!?"-()')) > 3]
        keywords.extend(title_words[:3])  # Top 3 längste Wörter
        
        # Aus Tags
        if self.product.tags:
            tag_list = self.product.get_tags_list()
            keywords.extend(tag_list[:2])  # Top 2 Tags
        
        # Aus Produkttyp und Vendor
        if self.product.product_type:
            keywords.append(self.product.product_type.lower())
        if self.product.vendor:
            keywords.append(self.product.vendor.lower())
        
        return ', '.join(list(dict.fromkeys(keywords))[:5])  # Duplikate entfernen, max 5
    
    def save(self, commit=True):
        seo_optimization = super().save(commit=False)
        
        if self.product:
            seo_optimization.product = self.product
            # Speichere Original-Daten
            seo_optimization.original_title = self.product.title
            seo_optimization.original_description = self.product.body_html or ''
            seo_optimization.original_seo_title = self.product.seo_title or ''
            seo_optimization.original_seo_description = self.product.seo_description or ''
        
        if commit:
            seo_optimization.save()
        
        return seo_optimization


class BlogPostSEOOptimizationForm(forms.ModelForm):
    """Form für KI-gestützte SEO-Optimierung von Blog-Posts"""
    
    class Meta:
        model = BlogPostSEOOptimization
        fields = ['keywords', 'ai_model']
        widgets = {
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'baby, ratgeber, entwicklung, eltern',
                'data-bs-toggle': 'tooltip',
                'title': 'Kommagetrennte Keywords für SEO-Optimierung'
            }),
            'ai_model': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.blog_post = kwargs.pop('blog_post', None)
        super().__init__(*args, **kwargs)
        
        # Initialisiere Keywords basierend auf Blog-Post-Daten
        if self.blog_post and not self.instance.pk:
            suggested_keywords = self._generate_suggested_keywords()
            if suggested_keywords:
                self.fields['keywords'].widget.attrs['placeholder'] = suggested_keywords
    
    def _generate_suggested_keywords(self):
        """Generiert Keyword-Vorschläge basierend auf Blog-Post-Daten"""
        if not self.blog_post:
            return ""
        
        keywords = []
        
        # Aus Titel extrahieren
        title_words = [word.lower().strip('.,!?"-()') for word in self.blog_post.title.split() 
                      if len(word.strip('.,!?"-()')) > 3]
        keywords.extend(title_words[:3])  # Top 3 längste Wörter
        
        # Aus Tags
        if self.blog_post.tags:
            tag_list = self.blog_post.get_tags_list()
            keywords.extend(tag_list[:2])  # Top 2 Tags
        
        # Aus Summary extrahieren
        if self.blog_post.summary:
            summary_words = [word.lower().strip('.,!?"-()') for word in self.blog_post.summary.split() 
                           if len(word.strip('.,!?"-()')) > 4]
            keywords.extend(summary_words[:2])  # Top 2 Wörter aus Summary
        
        return ', '.join(list(dict.fromkeys(keywords))[:5])  # Duplikate entfernen, max 5
    
    def save(self, commit=True):
        seo_optimization = super().save(commit=False)
        
        if self.blog_post:
            seo_optimization.blog_post = self.blog_post
            # Speichere Original-Daten
            seo_optimization.original_title = self.blog_post.title
            seo_optimization.original_content = self.blog_post.content or ''
            seo_optimization.original_summary = self.blog_post.summary or ''
            seo_optimization.original_seo_title = self.blog_post.seo_title or ''
            seo_optimization.original_seo_description = self.blog_post.seo_description or ''
        
        if commit:
            seo_optimization.save()
        
        return seo_optimization


