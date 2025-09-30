from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import (
    ZohoMailServerConnection, 
    EmailTemplateCategory, 
    EmailTemplate, 
    EmailSendLog,
    EmailTrigger
)


class ZohoMailServerConnectionForm(forms.ModelForm):
    """Form for creating/editing Zoho Mail Server connections"""
    
    class Meta:
        model = ZohoMailServerConnection
        fields = [
            'name', 'description', 'email_address', 'display_name',
            'client_id', 'client_secret', 'redirect_uri', 'region',
            'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Hauptverbindung'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optionale Beschreibung der Verbindung'
            }),
            'email_address': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anzeigename für E-Mails'
            }),
            'client_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Zoho Client ID'
            }),
            'client_secret': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Zoho Client Secret'
            }),
            'redirect_uri': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-domain.com/oauth/callback'
            }),
            'region': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        # Check for uniqueness (excluding current instance if editing)
        qs = ZohoMailServerConnection.objects.filter(name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Eine Verbindung mit diesem Namen existiert bereits.')
        return name


class EmailTemplateCategoryForm(forms.ModelForm):
    """Form for creating/editing email template categories"""
    
    class Meta:
        model = EmailTemplateCategory
        fields = ['name', 'slug', 'description', 'icon', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kategoriename'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'kategorie-slug'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der Kategorie'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'fas fa-envelope'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if not slug:
            # Auto-generate slug from name
            slug = slugify(self.cleaned_data.get('name', ''))
        
        # Check for uniqueness
        qs = EmailTemplateCategory.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Eine Kategorie mit diesem Slug existiert bereits.')
        return slug


class EmailTemplateForm(forms.ModelForm):
    """Form for creating/editing email templates"""
    
    preview_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': '{"customer_name": "Max Mustermann", "order_number": "12345"}'
        }),
        help_text='JSON-Daten für Vorschau (optional)'
    )
    
    class Meta:
        model = EmailTemplate
        fields = [
            'name', 'slug', 'category', 'template_type', 'trigger',
            'subject', 'html_content', 'text_content',
            'use_base_template', 'custom_css',
            'available_variables', 'is_active', 'is_default'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vorlagenname'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'vorlage-slug'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'template_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'trigger': forms.Select(attrs={
                'class': 'form-control'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E-Mail Betreff mit {{variablen}}'
            }),
            'html_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'HTML-Inhalt der E-Mail...'
            }),
            'text_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Text-Version wird NICHT automatisch synchronisiert! Button "Aus HTML generieren" nutzen.'
            }),
            'custom_css': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': '/* Benutzerdefiniertes CSS */'
            }),
            'available_variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': '{"customer_name": "Name des Kunden", "order_number": "Bestellnummer"}'
            }),
            'use_base_template': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add rich text editor classes
        self.fields['html_content'].widget.attrs.update({
            'data-editor': 'html',
            'data-theme': 'default'
        })

        # Add help texts with sync warning
        self.fields['html_content'].help_text = (
            'HTML-Version der E-Mail. Änderungen werden NICHT automatisch in Text-Inhalt übernommen!'
        )
        self.fields['text_content'].help_text = (
            'WICHTIG: Wird NICHT automatisch synchronisiert! '
            'Nach HTML-Änderungen im Editor den Button "Aus HTML generieren" nutzen.'
        )

        # Set up trigger field
        self.fields['trigger'].queryset = EmailTrigger.objects.filter(is_active=True).order_by('category', 'name')
        self.fields['trigger'].empty_label = "Kein Trigger (manueller Versand)"
        self.fields['trigger'].required = False

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if not slug:
            # Auto-generate slug from name
            slug = slugify(self.cleaned_data.get('name', ''))
        
        # Check for uniqueness
        qs = EmailTemplate.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Eine Vorlage mit diesem Slug existiert bereits.')
        return slug

    def clean_available_variables(self):
        variables = self.cleaned_data['available_variables']
        if isinstance(variables, str):
            try:
                import json
                variables = json.loads(variables)
            except json.JSONDecodeError:
                raise ValidationError('Ungültiges JSON-Format für verfügbare Variablen.')
        return variables

    def clean_preview_data(self):
        preview_data = self.cleaned_data['preview_data']
        if preview_data:
            try:
                import json
                json.loads(preview_data)
            except json.JSONDecodeError:
                raise ValidationError('Ungültiges JSON-Format für Vorschau-Daten.')
        return preview_data


class TestEmailForm(forms.Form):
    """Form for sending test emails"""
    
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Vorlage'
    )
    
    # WICHTIG: Keine Connection mehr nötig - verwendet SuperConfig!
    # connection field entfernt, da wir jetzt immer SuperConfig verwenden
    
    recipient_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'test@example.com'
        }),
        label='Empfänger E-Mail'
    )
    
    recipient_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Mustermann'
        }),
        label='Empfänger Name (optional)'
    )
    
    test_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': '{"customer_name": "Max Mustermann", "order_number": "12345"}'
        }),
        label='Test-Daten (JSON)',
        help_text='JSON-Daten für Template-Variablen'
    )

    def clean_test_data(self):
        test_data = self.cleaned_data['test_data']
        if test_data:
            try:
                import json
                json.loads(test_data)
            except json.JSONDecodeError:
                raise ValidationError('Ungültiges JSON-Format für Test-Daten.')
        return test_data


class EmailTemplateSearchForm(forms.Form):
    """Form for searching and filtering email templates"""
    
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Name, Betreff oder Inhalt...'
        }),
        label='Suche'
    )
    
    category = forms.ModelChoiceField(
        queryset=EmailTemplateCategory.objects.filter(is_active=True),
        required=False,
        empty_label='Alle Kategorien',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Kategorie'
    )
    
    template_type = forms.ChoiceField(
        choices=[('', 'Alle Typen')] + EmailTemplate.TEMPLATE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Typ'
    )
    
    is_active = forms.ChoiceField(
        choices=[('', 'Alle'), ('true', 'Aktiv'), ('false', 'Inaktiv')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )
    
    is_default = forms.ChoiceField(
        choices=[('', 'Alle'), ('true', 'Standard'), ('false', 'Nicht Standard')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Standard'
    )


class ConnectionTestForm(forms.Form):
    """Form for testing Zoho mail connections"""
    
    connection = forms.ModelChoiceField(
        queryset=ZohoMailServerConnection.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Verbindung'
    )
    
    test_type = forms.ChoiceField(
        choices=[
            ('auth', 'OAuth-Authentifizierung testen'),
            ('send', 'Test-E-Mail senden'),
            ('folders', 'Ordner abrufen'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Test-Typ'
    )
    
    test_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'test@example.com'
        }),
        label='Test E-Mail (für Send-Test)',
        help_text='Wird nur für "Test-E-Mail senden" benötigt'
    )

    def clean(self):
        cleaned_data = super().clean()
        test_type = cleaned_data.get('test_type')
        test_email = cleaned_data.get('test_email')
        
        if test_type == 'send' and not test_email:
            raise ValidationError('Test-E-Mail ist erforderlich für "Test-E-Mail senden".')
        
        return cleaned_data