from django import forms

from .services.council import MODELS as COUNCIL_MODELS
from .services.pipeline import LAYERS as PIPELINE_LAYERS


MODE_CHOICES = (
    ('rag', 'RAG — aus deiner Library antworten (mit Zitaten)'),
    ('council', 'Council — mehrere Modelle parallel fragen'),
    ('council_edited', 'Council + Redakteur — Primär-Modell strukturiert die Antworten'),
    ('hybrid', 'Hybrid — RAG-Kontext + Council-Perspektiven'),
    ('pipeline', 'Pipeline — externe Quellen (PubMed, OpenAlex, Europe PMC …)'),
)


def _model_choices():
    return [(k, v['name']) for k, v in COUNCIL_MODELS.items()]


def _layer_choices():
    return [(k, f'{v["name"]} — {v["desc"]}') for k, v in PIPELINE_LAYERS.items()]


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
        label='Primär-Modell (RAG + Hybrid + Council-Redakteur)',
        choices=[], initial='glm52',
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
    )
    council_models = forms.MultipleChoiceField(
        label='Council-Modelle (Council + Hybrid)',
        choices=[], required=False,
        widget=forms.CheckboxSelectMultiple,
        # Default: breit gefächerter Council — Frontier + Reasoning + Schreib-Spezialisten.
        # Free-Tier-Modelle (nemotron, glm_air_free) bleiben opt-in wegen Rate-Limits.
        initial=[
            'opus', 'gpt', 'gemini', 'deepseek', 'glm', 'grok',
            'qwen_max_thinking', 'kimi_thinking',
            'palmyra', 'nova',
        ],
    )
    top_k = forms.IntegerField(
        label='RAG Top-K', min_value=2, max_value=15, initial=6,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    # --- Pipeline-Mode ---------------------------------------------------
    pipeline_layers = forms.MultipleChoiceField(
        label='Aktive Layer (Pipeline)',
        choices=[], required=False,
        widget=forms.CheckboxSelectMultiple,
        # Default: alle kostenlosen Open-Access-Quellen; lens nur wenn Token vorhanden
        initial=['pubmed', 'semantic', 'openalex', 'epmc', 'crossref'],
    )
    pipeline_product_filter = forms.CharField(
        label='Produkt-/Kontext-Filter (optional)',
        required=False, max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'z.B. spinach AND postharvest AND storage',
        }),
        help_text='Wird als zusaetzlicher Boolean-Filter an die Frage gehaengt.',
    )
    pipeline_max_papers = forms.IntegerField(
        label='Top-N pro Layer (Pipeline)', min_value=3, max_value=25, initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False,
    )
    pipeline_cooccurrence = forms.BooleanField(
        label='Co-Occurrence-Spezifitaet berechnen',
        required=False, initial=False,
        help_text='Misst wie spezifisch die Verbindung zwischen Frage und Filter '
                  'ist. Berechnung: count(M ∩ P) / √(count(M) × count(P)). '
                  'Erfordert ausgefüllten Filter. Verdreifacht die Layer-Calls.',
    )
    pipeline_w_lit = forms.FloatField(
        required=False, min_value=0.0, max_value=1.0,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = _model_choices()
        self.fields['primary_model'].choices = choices
        self.fields['council_models'].choices = choices
        self.fields['pipeline_layers'].choices = _layer_choices()
