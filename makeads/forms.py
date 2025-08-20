from django import forms
from django.forms import formset_factory
from .models import Campaign, ReferenceImage, Creative
from .utils import get_available_ai_services


class CampaignStep1Form(forms.ModelForm):
    """
    Schritt 1: Ideeneingabe
    """
    class Meta:
        model = Campaign
        fields = ['name', 'basic_idea', 'detailed_description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Geben Sie einen Namen für Ihre Kampagne ein...'
            }),
            'basic_idea': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Beschreiben Sie Ihre grundlegende Creative-Idee...'
            }),
            'detailed_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Geben Sie hier eine detaillierte Beschreibung ein...'
            })
        }
        labels = {
            'name': 'Kampagnenname',
            'basic_idea': 'Grundlegende Creative-Idee',
            'detailed_description': 'Detaillierte Beschreibung'
        }


class CampaignStep2Form(forms.ModelForm):
    """
    Schritt 2: Referenzmaterial hinzufügen
    """
    class Meta:
        model = Campaign
        fields = ['web_links', 'additional_info']
        widgets = {
            'web_links': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Fügen Sie relevante Web-Links hinzu (ein Link pro Zeile)...'
            }),
            'additional_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Weitere Informationen oder Hinweise...'
            })
        }
        labels = {
            'web_links': 'Web-Links',
            'additional_info': 'Zusätzliche Informationen'
        }


class ReferenceImageForm(forms.ModelForm):
    """
    Form für das Hochladen von Referenzbildern
    """
    class Meta:
        model = ReferenceImage
        fields = ['image', 'description']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'multiple': False
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Beschreibung des Bildes (optional)...'
            })
        }
        labels = {
            'image': 'Referenzbild',
            'description': 'Bildbeschreibung'
        }


# Formset für mehrere Referenzbilder
ReferenceImageFormSet = formset_factory(
    ReferenceImageForm,
    extra=3,  # 3 leere Formulare standardmäßig
    max_num=10,  # Maximum 10 Bilder
    can_delete=True
)


class CreativeGenerationForm(forms.Form):
    """
    Form für Creative-Generierungs-Optionen
    """
    GENERATION_COUNT_CHOICES = [
        (10, '10 Creatives'),
        (15, '15 Creatives'),
        (20, '20 Creatives'),
    ]
    
    AI_SERVICE_CHOICES = [
        ('openai', 'ChatGPT + DALL-E (OpenAI)'),
    ]
    
    STYLE_CHOICES = [
        ('modern', 'Modern'),
        ('classic', 'Klassisch'),
        ('minimal', 'Minimal'),
        ('bold', 'Auffällig'),
        ('elegant', 'Elegant'),
        ('playful', 'Verspielt'),
    ]
    
    COLOR_SCHEME_CHOICES = [
        ('vibrant', 'Lebendige Farben'),
        ('pastel', 'Pastellfarben'),
        ('monochrome', 'Schwarz-Weiß'),
        ('warm', 'Warme Farben'),
        ('cool', 'Kühle Farben'),
        ('brand', 'Markenfarben verwenden'),
    ]
    
    generation_count = forms.ChoiceField(
        choices=GENERATION_COUNT_CHOICES,
        initial=10,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Anzahl zu generierender Creatives'
    )
    
    ai_service = forms.ChoiceField(
        choices=AI_SERVICE_CHOICES,
        initial='openai',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='KI-Service'
    )
    
    style_preference = forms.ChoiceField(
        choices=STYLE_CHOICES,
        initial='modern',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Stil-Präferenz'
    )
    
    color_scheme = forms.ChoiceField(
        choices=COLOR_SCHEME_CHOICES,
        initial='vibrant',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Farbschema'
    )
    
    target_audience = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'z.B. Junge Erwachsene, 25-35 Jahre, technikaffin...'
        }),
        label='Zielgruppe'
    )
    
    custom_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Zusätzliche Anweisungen für die KI...'
        }),
        label='Spezielle Anweisungen'
    )


class CreativeRevisionForm(forms.Form):
    """
    Form für die Überarbeitung eines Creatives
    """
    REVISION_TYPE_CHOICES = [
        ('text_only', 'Nur Text ändern'),
        ('image_only', 'Nur Bild ändern'),
        ('both', 'Text und Bild ändern'),
    ]
    
    revision_type = forms.ChoiceField(
        choices=REVISION_TYPE_CHOICES,
        widget=forms.RadioSelect(),
        label='Was möchten Sie überarbeiten?'
    )
    
    text_changes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Beschreiben Sie, wie der Text geändert werden soll...'
        }),
        label='Text-Änderungen'
    )
    
    image_changes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Beschreiben Sie, wie das Bild geändert werden soll...'
        }),
        label='Bild-Änderungen'
    )
    
    style_adjustments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Stil-Anpassungen (z.B. "moderner", "weniger Text", "andere Farben")...'
        }),
        label='Stil-Anpassungen'
    )


class CreativeFeedbackForm(forms.Form):
    """
    Form für Feedback zu Creatives
    """
    RATING_CHOICES = [
        (5, '⭐⭐⭐⭐⭐ Ausgezeichnet'),
        (4, '⭐⭐⭐⭐ Gut'),
        (3, '⭐⭐⭐ Durchschnittlich'),
        (2, '⭐⭐ Schlecht'),
        (1, '⭐ Sehr schlecht'),
    ]
    
    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(),
        label='Bewertung'
    )
    
    feedback_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Ihr Feedback hilft uns, bessere Creatives zu generieren...'
        }),
        label='Feedback'
    )
    
    is_favorite = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Als Favorit markieren'
    )


class BulkActionForm(forms.Form):
    """
    Form für Bulk-Aktionen auf Creatives
    """
    ACTION_CHOICES = [
        ('export', 'Exportieren'),
        ('delete', 'Löschen'),
        ('favorite', 'Als Favorit markieren'),
        ('unfavorite', 'Favorit entfernen'),
        ('regenerate', 'Neu generieren'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Aktion'
    )
    
    selected_creatives = forms.CharField(
        widget=forms.HiddenInput(),
        label='Ausgewählte Creatives'
    )
    
    export_format = forms.ChoiceField(
        choices=[
            ('zip', 'ZIP-Archiv'),
            ('pdf', 'PDF-Dokument'),
            ('json', 'JSON-Daten'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Export-Format'
    )