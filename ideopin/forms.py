from django import forms
from .models import PinProject, PinSettings


class Step1KeywordsForm(forms.ModelForm):
    """Schritt 1: Keywords eingeben"""

    class Meta:
        model = PinProject
        fields = ['keywords']
        widgets = {
            'keywords': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Keywords eingeben (kommagetrennt oder einzeln)'
            }),
        }


class Step2TextForm(forms.ModelForm):
    """Schritt 2: Text-Overlay konfigurieren"""

    class Meta:
        model = PinProject
        fields = [
            'overlay_text',
            'text_font',
            'text_size',
            'text_color',
            'text_position',
            'text_background_color',
            'text_background_opacity'
        ]
        widgets = {
            'overlay_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Catchy Pin-Text eingeben...',
                'maxlength': 200
            }),
            'text_font': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('Arial', 'Arial'),
                ('Helvetica', 'Helvetica'),
                ('Times New Roman', 'Times New Roman'),
                ('Georgia', 'Georgia'),
                ('Verdana', 'Verdana'),
                ('Impact', 'Impact'),
                ('Comic Sans MS', 'Comic Sans MS'),
            ]),
            'text_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 12,
                'max': 120,
            }),
            'text_color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
            }),
            'text_position': forms.Select(attrs={'class': 'form-select'}),
            'text_background_color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
            }),
            'text_background_opacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 1,
                'step': 0.1,
            }),
        }


class Step3ImageForm(forms.ModelForm):
    """Schritt 3: Bild-Einstellungen"""

    class Meta:
        model = PinProject
        fields = ['product_image', 'background_description', 'pin_format', 'text_integration_mode']
        widgets = {
            'product_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'background_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibe den gewünschten Hintergrund...'
            }),
            'pin_format': forms.Select(attrs={'class': 'form-select'}),
            'text_integration_mode': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            }),
        }


class Step4LinkForm(forms.ModelForm):
    """Schritt 4: Pin-Link eingeben"""

    class Meta:
        model = PinProject
        fields = ['pin_url']
        widgets = {
            'pin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/product-page'
            }),
        }


class Step5SEOForm(forms.ModelForm):
    """Schritt 5: SEO-Beschreibung"""

    class Meta:
        model = PinProject
        fields = ['seo_description']
        widgets = {
            'seo_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Pinterest-optimierte Beschreibung...',
                'maxlength': 500
            }),
        }


class PinSettingsForm(forms.ModelForm):
    """User-Einstellungen für Defaults"""

    class Meta:
        model = PinSettings
        exclude = ['user', 'created_at', 'updated_at']
        widgets = {
            'ideogram_model': forms.Select(attrs={'class': 'form-select'}),
            'ideogram_style': forms.Select(attrs={'class': 'form-select'}),
            'default_font': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('Arial', 'Arial'),
                ('Helvetica', 'Helvetica'),
                ('Times New Roman', 'Times New Roman'),
                ('Georgia', 'Georgia'),
                ('Verdana', 'Verdana'),
                ('Impact', 'Impact'),
            ]),
            'default_text_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 12,
                'max': 120,
            }),
            'default_text_color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
            }),
            'default_text_position': forms.Select(attrs={'class': 'form-select'}),
            'default_text_background_color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
            }),
            'default_text_background_opacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 1,
                'step': 0.1,
            }),
            'default_pin_format': forms.Select(attrs={'class': 'form-select'}),
        }
