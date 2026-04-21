from django import forms
from django.contrib.auth import get_user_model

from .services.council import MODELS as COUNCIL_MODELS


User = get_user_model()


PROVIDER_KEY_FIELDS = [
    ('openrouter_api_key',
        'OpenRouter — deckt ALLE Modelle ab (Claude, GPT, Gemini, Grok, DeepSeek, GLM, …)',
        'sk-or-v1-...', 'https://openrouter.ai/keys'),
]


class ApiKeyForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [f[0] for f in PROVIDER_KEY_FIELDS]
        widgets = {
            f[0]: forms.TextInput(attrs={
                'class': 'rs-input',
                'placeholder': f[2],
                'autocomplete': 'off',
            })
            for f in PROVIDER_KEY_FIELDS
        }


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
        initial=['opus', 'gpt', 'gemini', 'deepseek', 'glm'],
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
