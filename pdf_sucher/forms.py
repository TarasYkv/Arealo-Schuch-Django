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
        """Ermittelt verfügbare KI-Modelle basierend auf konfigurierten API-Schlüsseln und Balance"""
        try:
            from naturmacher.utils.api_helpers import get_user_api_key
            from naturmacher.models import APIBalance
            
            available_models = []
            
            # OpenAI prüfen
            openai_key = get_user_api_key(user, 'openai')
            print(f"DEBUG: OpenAI key for {user.username}: {'SET' if openai_key else 'NOT SET'}")
            if openai_key:
                # Prüfe Balance
                try:
                    balance = APIBalance.objects.get(user=user, provider='openai')
                    if balance.balance > 0:
                        available_models.extend([
                            'openai_gpt4o', 'openai_gpt4o_mini', 'openai_gpt4_turbo', 
                            'openai_gpt4', 'openai_gpt35_turbo'
                        ])
                        print(f"DEBUG: OpenAI balance for {user.username}: {balance.balance}")
                    else:
                        print(f"DEBUG: OpenAI balance empty for {user.username}")
                except APIBalance.DoesNotExist:
                    # Wenn keine Balance-Info vorhanden, als verfügbar markieren
                    available_models.extend([
                        'openai_gpt4o', 'openai_gpt4o_mini', 'openai_gpt4_turbo', 
                        'openai_gpt4', 'openai_gpt35_turbo'
                    ])
                    print(f"DEBUG: No OpenAI balance info for {user.username}")
            
            # Google prüfen
            google_key = get_user_api_key(user, 'google')
            print(f"DEBUG: Google key for {user.username}: {'SET' if google_key else 'NOT SET'}")
            if google_key:
                # Prüfe Balance
                try:
                    balance = APIBalance.objects.get(user=user, provider='google')
                    if balance.balance > 0:
                        available_models.extend(['google_gemini_pro', 'google_gemini_flash'])
                        print(f"DEBUG: Google balance for {user.username}: {balance.balance}")
                    else:
                        print(f"DEBUG: Google balance empty for {user.username}")
                except APIBalance.DoesNotExist:
                    # Wenn keine Balance-Info vorhanden, als verfügbar markieren
                    available_models.extend(['google_gemini_pro', 'google_gemini_flash'])
                    print(f"DEBUG: No Google balance info for {user.username}")
            
            # Anthropic prüfen
            anthropic_key = get_user_api_key(user, 'anthropic')
            print(f"DEBUG: Anthropic key for {user.username}: {'SET' if anthropic_key else 'NOT SET'}")
            if anthropic_key:
                # Prüfe Balance
                try:
                    balance = APIBalance.objects.get(user=user, provider='anthropic')
                    if balance.balance > 0:
                        available_models.extend([
                            'anthropic_claude_opus', 'anthropic_claude_sonnet', 'anthropic_claude_haiku'
                        ])
                        print(f"DEBUG: Anthropic balance for {user.username}: {balance.balance}")
                    else:
                        print(f"DEBUG: Anthropic balance empty for {user.username}")
                except APIBalance.DoesNotExist:
                    # Wenn keine Balance-Info vorhanden, als verfügbar markieren
                    available_models.extend([
                        'anthropic_claude_opus', 'anthropic_claude_sonnet', 'anthropic_claude_haiku'
                    ])
                    print(f"DEBUG: No Anthropic balance info for {user.username}")
            
            print(f"DEBUG: Available models: {available_models}")
            return available_models
        
        except ImportError as e:
            print(f"DEBUG: ImportError in get_available_models_for_user: {e}")
            # Fallback falls die API-Helper nicht verfügbar sind
            return [choice[0] for choice in PDFSummary.AI_MODEL_CHOICES]
        except Exception as e:
            print(f"DEBUG: Exception in get_available_models_for_user: {e}")
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