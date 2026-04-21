from django import forms

from .services.council import MODELS as COUNCIL_MODELS


MODE_CHOICES = (
    ('rag', 'RAG — aus deiner Library antworten (mit Zitaten)'),
    ('council', 'Council — mehrere Modelle parallel fragen'),
    ('hybrid', 'Hybrid — RAG-Kontext + Council-Perspektiven'),
)


def _model_choices():
    return [(k, v['name']) for k, v in COUNCIL_MODELS.items()]


class AskForm(forms.Form):
    question = forms.CharField(
        label='Frage',
        widget=forms.Textarea(attrs={
            'rows': 5, 'class': 'form-control',
            'placeholder': 'z.B. Welche Wellenlänge verzögert Seneszenz bei Brokkoli?',
        }),
    )
    mode = forms.ChoiceField(
        label='Modus', choices=MODE_CHOICES, initial='rag',
        widget=forms.RadioSelect,
    )
    primary_model = forms.ChoiceField(
        label='Primär-Modell (RAG + Hybrid-Synthese)',
        choices=[], initial='opus',
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
    )
    council_models = forms.MultipleChoiceField(
        label='Council-Modelle (Council + Hybrid)',
        choices=[], required=False,
        widget=forms.CheckboxSelectMultiple,
        # Default: nur bezahlte, stabile Modelle. Free-Tier-Modelle (nemotron,
        # glm_air_free) sind rate-limited und müssen explizit aktiviert werden.
        initial=['opus', 'gpt', 'gemini', 'deepseek', 'glm', 'grok'],
    )
    top_k = forms.IntegerField(
        label='RAG Top-K', min_value=2, max_value=15, initial=6,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = _model_choices()
        self.fields['primary_model'].choices = choices
        self.fields['council_models'].choices = choices
