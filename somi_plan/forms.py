from django import forms
from django.core.exceptions import ValidationError
from .models import PostingPlan, Platform, PostContent, PostSchedule


class Step1Form(forms.ModelForm):
    """Schritt 1: Basis-Setup Formular"""
    
    class Meta:
        model = PostingPlan
        fields = ['title', 'platform', 'user_profile', 'target_audience', 'goals', 'vision']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Platform Queryset auf aktive Plattformen beschränken
        self.fields['platform'].queryset = Platform.objects.filter(is_active=True)
        
        # Custom Widgets und Styling
        self.fields['title'].widget = forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'z.B. "Instagram Marketing für Fitnessstudio"',
            'maxlength': 200
        })
        
        self.fields['platform'].widget = forms.Select(attrs={
            'class': 'form-control form-control-lg d-none',  # Hidden, wird über Custom UI gesteuert
        })
        
        self.fields['user_profile'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Beschreibe dich/dein Unternehmen: Was bietest du an? Was sind deine Stärken? Welche Ressourcen hast du?'
        })
        
        self.fields['target_audience'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Wer ist deine Zielgruppe? Welche Themen interessieren sie? Welche Probleme haben sie?'
        })
        
        self.fields['goals'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Was möchtest du mit Social Media erreichen? Mehr Kunden? Markenbekanntheit? Community aufbauen?'
        })
        
        self.fields['vision'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Wie stellst du dir deinen idealen Social Media Auftritt vor? Was soll das Gefühl/der Eindruck sein?'
        })
        
        # Labels anpassen
        self.fields['title'].label = 'Plan-Titel'
        self.fields['platform'].label = 'Plattform'
        self.fields['user_profile'].label = 'Über dich/dein Unternehmen'
        self.fields['target_audience'].label = 'Zielgruppe & Themenbereich'
        self.fields['goals'].label = 'Deine Ziele'
        self.fields['vision'].label = 'Deine Vision'

    def clean_title(self):
        title = self.cleaned_data['title']
        if len(title) < 5:
            raise ValidationError('Der Titel muss mindestens 5 Zeichen lang sein.')
        return title

    def clean_user_profile(self):
        profile = self.cleaned_data['user_profile']
        if len(profile) < 20:
            raise ValidationError('Bitte beschreibe dich etwas ausführlicher (mindestens 20 Zeichen).')
        return profile


class Step2StrategyForm(forms.Form):
    """Schritt 2: Strategie-Anpassung Formular"""
    
    use_ai_strategy = forms.BooleanField(
        label='KI-Strategie verwenden',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-bs-toggle': 'collapse',
            'data-bs-target': '#manual-strategy-options'
        }),
        help_text='Lasse die KI eine optimale Strategie für dich erstellen'
    )
    
    posting_frequency = forms.ChoiceField(
        label='Posting-Häufigkeit',
        choices=[
            ('', 'Von KI bestimmen lassen'),
            ('daily', 'Täglich'),
            ('every_other_day', 'Jeden 2. Tag'),
            ('3_times_week', '3x pro Woche'),
            ('2_times_week', '2x pro Woche'),
            ('weekly', 'Wöchentlich'),
            ('custom', 'Benutzerdefiniert'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=False
    )
    
    best_times = forms.MultipleChoiceField(
        label='Beste Posting-Zeiten',
        choices=[
            ('morning', 'Morgens (6-9 Uhr)'),
            ('midday', 'Mittags (11-14 Uhr)'),
            ('afternoon', 'Nachmittags (15-17 Uhr)'),
            ('evening', 'Abends (18-21 Uhr)'),
            ('night', 'Nachts (21-23 Uhr)'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )
    
    content_types = forms.MultipleChoiceField(
        label='Content-Typen',
        choices=[
            ('tips', 'Tipps & Tricks'),
            ('behind_scenes', 'Behind the Scenes'),
            ('product', 'Produktvorstellungen'),
            ('educational', 'Bildungsinhalte'),
            ('motivational', 'Motivierende Posts'),
            ('testimonials', 'Kundenstimmen'),
            ('news', 'News & Updates'),
            ('questions', 'Fragen an Community'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )
    
    cross_platform = forms.BooleanField(
        label='Content für andere Plattformen anpassen',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    additional_notes = forms.CharField(
        label='Zusätzliche Anmerkungen',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Weitere Wünsche oder Anpassungen zur KI-Strategie...'
        }),
        required=False
    )


class PostContentForm(forms.ModelForm):
    """Formular für Post-Content Bearbeitung"""
    
    class Meta:
        model = PostContent
        fields = ['title', 'content', 'script', 'hashtags', 'call_to_action', 'post_type', 'priority']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Character limit basierend auf Platform
        character_limit = 280  # Default
        if hasattr(self.instance, 'posting_plan') and self.instance.posting_plan:
            character_limit = self.instance.posting_plan.platform.character_limit
        
        self.fields['title'].widget = forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Überschrift des Posts'
        })
        
        self.fields['content'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'data-character-limit': character_limit,
            'data-counter': '#character-counter'
        })
        
        self.fields['script'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Detaillierte Anweisungen und Skript für die Umsetzung...'
        })
        
        self.fields['hashtags'].widget = forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '#beispiel #hashtag #social'
        })
        
        self.fields['call_to_action'].widget = forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'z.B. "Folge für mehr Tipps!" oder "Link in Bio"'
        })
        
        self.fields['post_type'].widget = forms.Select(attrs={
            'class': 'form-control'
        })
        
        self.fields['priority'].widget = forms.Select(
            choices=[(1, 'Hoch'), (2, 'Mittel'), (3, 'Niedrig')],
            attrs={'class': 'form-control'}
        )


class PostScheduleForm(forms.ModelForm):
    """Formular für Post-Terminierung"""
    
    class Meta:
        model = PostSchedule
        fields = ['scheduled_date', 'scheduled_time', 'notes']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['scheduled_date'].widget = forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
        
        self.fields['scheduled_time'].widget = forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
        
        self.fields['notes'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notizen zur Umsetzung...'
        })


class PlanFilterForm(forms.Form):
    """Filter-Form für Plan-Liste"""
    
    platform = forms.ModelChoiceField(
        queryset=Platform.objects.filter(is_active=True),
        required=False,
        empty_label="Alle Plattformen",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'Alle Status')] + PostingPlan.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Titel oder Beschreibung...'
        })
    )


class BulkPostActionForm(forms.Form):
    """Formular für Bulk-Aktionen auf Posts"""
    
    action = forms.ChoiceField(
        choices=[
            ('schedule', 'Terminieren'),
            ('delete', 'Löschen'),
            ('duplicate', 'Duplizieren'),
            ('change_priority', 'Priorität ändern'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    selected_posts = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    # Conditional fields
    schedule_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    schedule_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    
    new_priority = forms.ChoiceField(
        choices=[(1, 'Hoch'), (2, 'Mittel'), (3, 'Niedrig')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )