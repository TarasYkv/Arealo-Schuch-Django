from django import forms
from .models import PDFDocument, PDFSummary


class PDFUploadForm(forms.ModelForm):
    """Formular für PDF-Upload"""
    
    class Meta:
        model = PDFDocument
        fields = ['title', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titel des Dokuments eingeben...',
                'required': True
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf',
                'required': True
            })
        }
        labels = {
            'title': 'Dokumenttitel',
            'file': 'PDF-Datei'
        }
        help_texts = {
            'title': 'Geben Sie einen aussagekräftigen Titel für das Dokument an',
            'file': 'Wählen Sie eine PDF-Datei (max. 50MB)'
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Dateigröße prüfen (50MB Limit)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('Die Datei ist zu groß. Maximum: 50MB')
            
            # Dateierweiterung prüfen
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Nur PDF-Dateien sind erlaubt.')
        
        return file


class SummaryCreationForm(forms.ModelForm):
    """Formular zur Erstellung einer Zusammenfassung"""
    
    class Meta:
        model = PDFSummary
        fields = ['ai_model']
        widgets = {
            'ai_model': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            })
        }
        labels = {
            'ai_model': 'KI-Modell auswählen'
        }
        help_texts = {
            'ai_model': 'Wählen Sie das KI-Modell für die Analyse der Ausschreibung'
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Verfügbare Modelle basierend auf Benutzer-API-Keys filtern
        if user:
            available_models = self.get_available_models_for_user(user)
            self.fields['ai_model'].choices = [
                (key, label) for key, label in PDFSummary.AI_MODEL_CHOICES 
                if key in available_models
            ]
            
            if not available_models:
                self.fields['ai_model'].widget.attrs['disabled'] = True
                self.fields['ai_model'].help_text = 'Keine API-Schlüssel konfiguriert. Bitte konfigurieren Sie Ihre API-Schlüssel in den Kontoeinstellungen.'
    
    def get_available_models_for_user(self, user):
        """Ermittelt verfügbare KI-Modelle basierend auf konfigurierten API-Schlüsseln"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            
            available_models = []
            
            # OpenAI prüfen
            if get_user_api_key(user, 'openai'):
                available_models.extend(['openai_gpt4', 'openai_gpt35'])
            
            # Google prüfen
            if get_user_api_key(user, 'google'):
                available_models.append('google_gemini')
            
            # Anthropic prüfen
            if get_user_api_key(user, 'anthropic'):
                available_models.append('anthropic_claude')
            
            return available_models
        
        except ImportError:
            # Fallback falls die API-Helper nicht verfügbar sind
            return [choice[0] for choice in PDFSummary.AI_MODEL_CHOICES]


class PositionEditForm(forms.Form):
    """Formular zur Bearbeitung einer Ausschreibungsposition"""
    position_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label='Position'
    )
    title = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label='Titel'
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        label='Beschreibung'
    )
    quantity = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        label='Menge'
    )
    unit = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label='Einheit'
    )
    unit_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        label='Einzelpreis'
    )
    total_price = forms.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        label='Gesamtpreis'
    )
    category = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        label='Kategorie'
    )


class SummaryFilterForm(forms.Form):
    """Formular zum Filtern von Zusammenfassungen"""
    ai_model = forms.ChoiceField(
        required=False,
        choices=[('', 'Alle Modelle')] + PDFSummary.AI_MODEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label='KI-Modell'
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Alle Status')] + PDFSummary.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label='Status'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        label='Von Datum'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        label='Bis Datum'
    )
    search = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Dokumente durchsuchen...'
        }),
        label='Suche'
    )