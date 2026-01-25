from django import forms
from .models import PLoomSettings, ProductTheme, PLoomProduct, PLoomProductVariant


class PLoomSettingsForm(forms.ModelForm):
    """Formular für P-Loom Einstellungen"""

    class Meta:
        model = PLoomSettings
        fields = ['default_store', 'ai_provider', 'ai_model', 'writing_style']
        widgets = {
            'default_store': forms.Select(attrs={'class': 'form-select'}),
            'ai_provider': forms.Select(attrs={'class': 'form-select'}),
            'ai_model': forms.Select(attrs={'class': 'form-select'}),
            'writing_style': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            from shopify_manager.models import ShopifyStore
            self.fields['default_store'].queryset = ShopifyStore.objects.filter(user=user)

        # Dynamische AI-Model Choices basierend auf Provider
        self.fields['ai_model'].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[
                # OpenAI Modelle
                ('gpt-4o', 'GPT-4o'),
                ('gpt-4o-mini', 'GPT-4o Mini'),
                ('gpt-4-turbo', 'GPT-4 Turbo'),
                ('o1', 'O1 (Reasoning)'),
                ('o1-mini', 'O1 Mini'),
                ('o3-mini', 'O3 Mini'),
                # Anthropic Modelle
                ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet'),
                ('claude-3-5-haiku-20241022', 'Claude 3.5 Haiku'),
                ('claude-3-opus-20240229', 'Claude 3 Opus'),
                # Google Gemini Modelle
                ('gemini-2.0-flash-exp', 'Gemini 2.0 Flash (Neu)'),
                ('gemini-2.0-flash-thinking-exp', 'Gemini 2.0 Flash Thinking'),
                ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
                ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
                ('gemini-1.5-flash-8b', 'Gemini 1.5 Flash 8B'),
            ]
        )


class ProductThemeForm(forms.ModelForm):
    """Formular für Produkt-Themes"""

    class Meta:
        model = ProductTheme
        fields = [
            'name', 'title_template', 'description_template',
            'seo_title_template', 'seo_description_template',
            'default_metafields', 'is_default',
            'default_price', 'default_compare_at_price',
            'default_vendor', 'default_product_type', 'default_tags'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'title_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'description_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'seo_title_template': forms.TextInput(attrs={'class': 'form-control'}),
            'seo_description_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'default_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_compare_at_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_vendor': forms.TextInput(attrs={'class': 'form-control'}),
            'default_product_type': forms.TextInput(attrs={'class': 'form-control'}),
            'default_tags': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PLoomProductForm(forms.ModelForm):
    """Formular für P-Loom Produkte"""

    class Meta:
        model = PLoomProduct
        fields = [
            'title', 'description', 'vendor', 'product_type', 'tags',
            'seo_title', 'seo_description',
            'price', 'compare_at_price',
            'product_metafields', 'category_metafields',
            'collection_id', 'collection_name',
            'template_suffix',
            'theme', 'shopify_store'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Produkttitel eingeben'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Produktbeschreibung (HTML wird unterstützt)'
            }),
            'vendor': forms.TextInput(attrs={'class': 'form-control'}),
            'product_type': forms.TextInput(attrs={'class': 'form-control'}),
            'tags': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Komma-getrennte Tags'
            }),
            'seo_title': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 70,
                'placeholder': 'SEO-Titel (max. 70 Zeichen)'
            }),
            'seo_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'maxlength': 160,
                'placeholder': 'SEO-Beschreibung (max. 160 Zeichen)'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'compare_at_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'collection_id': forms.HiddenInput(),
            'collection_name': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'template_suffix': forms.TextInput(attrs={'class': 'form-control'}),
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'shopify_store': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            from shopify_manager.models import ShopifyStore
            self.fields['shopify_store'].queryset = ShopifyStore.objects.filter(user=user)
            self.fields['theme'].queryset = ProductTheme.objects.filter(user=user)

        # Template Suffix wird dynamisch via JavaScript geladen
        # Hier nur als CharField definieren, damit es validiert wird
        self.fields['template_suffix'].required = False


class PLoomProductVariantForm(forms.ModelForm):
    """Formular für Produkt-Varianten"""

    class Meta:
        model = PLoomProductVariant
        fields = [
            'title', 'sku', 'price', 'compare_at_price',
            'option1_name', 'option1_value',
            'option2_name', 'option2_value',
            'option3_name', 'option3_value',
            'barcode', 'inventory_quantity', 'inventory_policy',
            'weight', 'weight_unit', 'requires_shipping', 'taxable'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'compare_at_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'option1_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Größe'}),
            'option1_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. M'}),
            'option2_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Farbe'}),
            'option2_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. Rot'}),
            'option3_name': forms.TextInput(attrs={'class': 'form-control'}),
            'option3_value': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'inventory_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'inventory_policy': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'weight_unit': forms.Select(attrs={'class': 'form-select'}),
            'requires_shipping': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'taxable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ImageUploadForm(forms.Form):
    """Formular für Bild-Uploads"""
    image = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    alt_text = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Alt-Text für SEO'
        })
    )


class AIGenerateForm(forms.Form):
    """Formular für KI-Textgenerierung"""
    product_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Produktname oder Beschreibung'
        })
    )
    keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Zusätzliche Keywords (optional)'
        })
    )
    tone = forms.ChoiceField(
        choices=[
            ('professional', 'Professionell'),
            ('casual', 'Locker'),
            ('enthusiastic', 'Begeistert'),
            ('luxury', 'Luxuriös'),
            ('technical', 'Technisch'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='professional'
    )
