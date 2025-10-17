from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import (
    ConnectProfile, Skill, SkillCategory, UserSkill, UserNeed,
    ConnectPost, PostComment, ConnectRequest, ConnectStory
)


class OnboardingSkillsForm(forms.Form):
    """Schritt 1: Skills auswählen"""
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True, is_predefined=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'skill-checkbox-grid'
        }),
        required=False,
        label='Wähle bis zu 10 Skills aus',
        help_text='Wähle die Skills aus, die du beherrschst'
    )

    custom_skill_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Eigener Skill (z.B. "Unreal Engine")'
        }),
        label='Eigener Skill',
        error_messages={
            'max_length': 'Der Skill-Name darf maximal 100 Zeichen lang sein.',
        }
    )

    custom_skill_category = forms.ModelChoiceField(
        queryset=SkillCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Kategorie für eigenen Skill'
    )

    def clean(self):
        cleaned_data = super().clean()
        skills = cleaned_data.get('skills', [])
        custom_skill_name = cleaned_data.get('custom_skill_name')
        custom_skill_category = cleaned_data.get('custom_skill_category')

        # Validierung für Custom Skill
        if custom_skill_name and not custom_skill_category:
            raise ValidationError('Bitte wähle eine Kategorie für den eigenen Skill')

        # Max 10 Skills
        total_skills = len(skills) + (1 if custom_skill_name else 0)
        if total_skills > 10:
            raise ValidationError('Du kannst maximal 10 Skills auswählen')

        return cleaned_data


class OnboardingLevelForm(forms.Form):
    """Schritt 2: Level für ausgewählte Skills"""
    def __init__(self, *args, skills=None, **kwargs):
        super().__init__(*args, **kwargs)

        if skills:
            for skill in skills:
                # Level Field
                self.fields[f'skill_{skill.id}_level'] = forms.ChoiceField(
                    choices=UserSkill.LEVEL_CHOICES,
                    initial='fortgeschritten',
                    widget=forms.RadioSelect(attrs={
                        'class': 'level-radio-inline'
                    }),
                    label=f'{skill.name} - Level',
                    required=True
                )

                # Years Experience (optional)
                self.fields[f'skill_{skill.id}_years'] = forms.IntegerField(
                    min_value=0,
                    max_value=50,
                    required=False,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm',
                        'placeholder': 'Jahre'
                    }),
                    label=f'{skill.name} - Jahre Erfahrung',
                    error_messages={
                        'invalid': 'Bitte gib eine gültige Zahl ein.',
                        'min_value': 'Die Anzahl der Jahre muss mindestens 0 sein.',
                        'max_value': 'Die Anzahl der Jahre darf maximal 50 sein.',
                    }
                )

                # Offering Help
                self.fields[f'skill_{skill.id}_offering'] = forms.BooleanField(
                    initial=True,
                    required=False,
                    widget=forms.CheckboxInput(attrs={
                        'class': 'form-check-input'
                    }),
                    label=f'Ich biete Hilfe bei {skill.name} an'
                )


class OnboardingNeedsForm(forms.Form):
    """Schritt 3: Was suchst du?"""
    needs = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True, is_predefined=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'need-checkbox-grid'
        }),
        required=False,
        label='Bei welchen Skills brauchst du Hilfe?',
        help_text='Wähle bis zu 5 Skills aus'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamisch Felder für jedes Need hinzufügen
        if self.data:
            selected_needs = self.data.getlist('needs')
            for need_id in selected_needs:
                try:
                    skill = Skill.objects.get(id=need_id)

                    # Description Field
                    self.fields[f'need_{need_id}_description'] = forms.CharField(
                        widget=forms.Textarea(attrs={
                            'class': 'form-control',
                            'rows': 2,
                            'placeholder': f'Was genau brauchst du Hilfe bei {skill.name}?'
                        }),
                        label=f'Beschreibung für {skill.name}',
                        max_length=500,
                        required=False,
                        error_messages={
                            'max_length': 'Die Beschreibung darf maximal 500 Zeichen lang sein.',
                        }
                    )

                    # Urgency Field
                    self.fields[f'need_{need_id}_urgency'] = forms.ChoiceField(
                        choices=UserNeed.URGENCY_CHOICES,
                        initial='mittel',
                        widget=forms.RadioSelect(attrs={
                            'class': 'urgency-radio-inline'
                        }),
                        label=f'Dringlichkeit für {skill.name}',
                        required=False
                    )
                except Skill.DoesNotExist:
                    pass

    def clean(self):
        cleaned_data = super().clean()
        needs = cleaned_data.get('needs', [])

        if len(needs) > 5:
            raise ValidationError('Du kannst maximal 5 Bedarfe angeben')

        return cleaned_data


class OnboardingProfileForm(forms.ModelForm):
    """Schritt 5: Profil-Details"""
    class Meta:
        model = ConnectProfile
        fields = ['avatar', 'bio', 'location', 'website', 'linkedin', 'is_public', 'show_online_status',
                  'notify_new_matches', 'notify_messages', 'notify_weekly_digest']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Erzähle kurz über dich... (max. 500 Zeichen)',
                'maxlength': 500
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Berlin, Deutschland'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://deine-website.de'
            }),
            'linkedin': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/in/dein-profil'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'show_online_status': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_new_matches': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_messages': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_weekly_digest': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'bio': 'Über mich',
            'avatar': 'Profilbild',
            'location': 'Standort',
            'website': 'Website',
            'linkedin': 'LinkedIn',
            'is_public': 'Öffentliches Profil (für andere sichtbar)',
            'show_online_status': 'Online-Status anzeigen',
            'notify_new_matches': 'Benachrichtigung bei neuen Matches',
            'notify_messages': 'Benachrichtigung bei neuen Nachrichten',
            'notify_weekly_digest': 'Wöchentliche Zusammenfassung per E-Mail',
        }
        error_messages = {
            'website': {
                'invalid': 'Bitte gib eine gültige URL ein (z.B. https://deine-website.de)',
            },
            'linkedin': {
                'invalid': 'Bitte gib eine gültige LinkedIn-URL ein (z.B. https://linkedin.com/in/dein-profil)',
            },
            'bio': {
                'max_length': 'Die Beschreibung darf maximal 500 Zeichen lang sein.',
            },
            'avatar': {
                'invalid': 'Bitte wähle eine gültige Bilddatei (JPG, PNG oder GIF).',
            },
        }


class ProfileEditForm(forms.ModelForm):
    """Profil bearbeiten"""
    class Meta:
        model = ConnectProfile
        fields = ['avatar', 'bio', 'is_public', 'show_online_status']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Erzähle über dich...'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'show_online_status': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        error_messages = {
            'bio': {
                'max_length': 'Die Beschreibung darf maximal 500 Zeichen lang sein.',
            },
            'avatar': {
                'invalid': 'Bitte wähle eine gültige Bilddatei (JPG, PNG oder GIF).',
            },
        }


class AddSkillForm(forms.Form):
    """Neuen Skill hinzufügen (zu eigenem Profil)"""
    skill = forms.ModelChoiceField(
        queryset=Skill.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select skill-select-2',
            'data-placeholder': 'Skill auswählen...'
        }),
        label='Skill',
        required=False
    )

    # Für Custom Skills
    custom_skill_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Eigener Skill-Name'
        }),
        label='Oder: Eigenen Skill erstellen',
        error_messages={
            'max_length': 'Der Skill-Name darf maximal 100 Zeichen lang sein.',
        }
    )

    custom_skill_category = forms.ModelChoiceField(
        queryset=SkillCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Kategorie'
    )

    level = forms.ChoiceField(
        choices=UserSkill.LEVEL_CHOICES,
        initial='fortgeschritten',
        widget=forms.RadioSelect(attrs={'class': 'level-radio'}),
        label='Dein Level'
    )

    years_experience = forms.IntegerField(
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Jahre'
        }),
        label='Jahre Erfahrung (optional)',
        error_messages={
            'invalid': 'Bitte gib eine gültige Zahl ein.',
            'min_value': 'Die Anzahl der Jahre muss mindestens 0 sein.',
            'max_value': 'Die Anzahl der Jahre darf maximal 50 sein.',
        }
    )

    is_offering = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Ich biete Hilfe bei diesem Skill an'
    )

    description = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Zusätzliche Infos (optional)...'
        }),
        label='Beschreibung',
        error_messages={
            'max_length': 'Die Beschreibung darf maximal 1000 Zeichen lang sein.',
        }
    )

    def clean(self):
        cleaned_data = super().clean()
        skill = cleaned_data.get('skill')
        custom_skill_name = cleaned_data.get('custom_skill_name')
        custom_skill_category = cleaned_data.get('custom_skill_category')

        # Entweder vorhandenen Skill ODER custom
        if not skill and not custom_skill_name:
            raise ValidationError('Bitte wähle einen Skill aus oder erstelle einen eigenen')

        if custom_skill_name and not custom_skill_category:
            raise ValidationError('Bitte wähle eine Kategorie für den eigenen Skill')

        if skill and custom_skill_name:
            raise ValidationError('Bitte wähle entweder einen vorhandenen Skill ODER erstelle einen eigenen')

        return cleaned_data


class EditSkillForm(forms.ModelForm):
    """Eigenen Skill bearbeiten"""
    class Meta:
        model = UserSkill
        fields = ['level', 'years_experience', 'is_offering', 'description']
        widgets = {
            'level': forms.RadioSelect(attrs={'class': 'level-radio'}),
            'years_experience': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Jahre'
            }),
            'is_offering': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
        error_messages = {
            'years_experience': {
                'invalid': 'Bitte gib eine gültige Zahl ein.',
                'min_value': 'Die Anzahl der Jahre muss mindestens 0 sein.',
                'max_value': 'Die Anzahl der Jahre darf maximal 50 sein.',
            },
            'description': {
                'max_length': 'Die Beschreibung darf maximal 1000 Zeichen lang sein.',
            },
        }


class AddNeedForm(forms.Form):
    """Neuen Bedarf hinzufügen"""
    skill = forms.ModelChoiceField(
        queryset=Skill.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select skill-select-2',
            'data-placeholder': 'Skill auswählen...'
        }),
        label='Welchen Skill suchst du?'
    )

    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Beschreibe, wobei du genau Hilfe brauchst...'
        }),
        label='Beschreibung',
        max_length=500,
        error_messages={
            'required': 'Bitte beschreibe, wobei du Hilfe brauchst.',
            'max_length': 'Die Beschreibung darf maximal 500 Zeichen lang sein.',
        }
    )

    urgency = forms.ChoiceField(
        choices=UserNeed.URGENCY_CHOICES,
        initial='mittel',
        widget=forms.RadioSelect(attrs={'class': 'urgency-radio'}),
        label='Dringlichkeit'
    )


class EditNeedForm(forms.ModelForm):
    """Bedarf bearbeiten"""
    class Meta:
        model = UserNeed
        fields = ['description', 'urgency', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'urgency': forms.RadioSelect(attrs={'class': 'urgency-radio'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        error_messages = {
            'description': {
                'required': 'Bitte beschreibe, wobei du Hilfe brauchst.',
                'max_length': 'Die Beschreibung darf maximal 500 Zeichen lang sein.',
            },
        }


class PostCreateForm(forms.ModelForm):
    """Neuen Post erstellen"""
    skills_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'z.B. Python, Django, React (komma-getrennt)',
        }),
        label='Verwandte Skills (optional)',
        help_text='Gib Skills komma-getrennt ein. Neue Skills werden automatisch erstellt.'
    )

    class Meta:
        model = ConnectPost
        fields = ['post_type', 'content', 'image', 'visibility', 'location']
        widgets = {
            'post_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Was möchtest du teilen?',
                'maxlength': 1000
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'visibility': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleLocationField()'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Berlin, München, Hamburg...',
                'id': 'id_location'
            }),
        }
        labels = {
            'post_type': 'Art des Posts',
            'content': 'Inhalt',
            'image': 'Bild (optional)',
            'visibility': 'Sichtbarkeit',
            'location': 'Standort',
        }
        error_messages = {
            'content': {
                'required': 'Bitte gib einen Inhalt für deinen Post ein.',
                'max_length': 'Der Post-Inhalt darf maximal 1000 Zeichen lang sein.',
            },
            'image': {
                'invalid': 'Bitte wähle eine gültige Bilddatei (JPG, PNG oder GIF).',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate skills_input if editing existing post
        if self.instance.pk:
            skills = self.instance.related_skills.all()
            if skills:
                self.initial['skills_input'] = ', '.join([skill.name for skill in skills])

        # Set location from profile if not set and creating new post
        user = kwargs.get('initial', {}).get('user')
        if user and not self.instance.pk:
            try:
                profile = user.connect_profile
                if profile.location and not self.initial.get('location'):
                    self.initial['location'] = profile.location
            except:
                pass


class PostCommentForm(forms.ModelForm):
    """Kommentar zu Post"""
    class Meta:
        model = PostComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Schreibe einen Kommentar...',
                'maxlength': 500
            }),
        }
        labels = {
            'content': '',
        }
        error_messages = {
            'content': {
                'required': 'Bitte gib einen Kommentar ein.',
                'max_length': 'Der Kommentar darf maximal 500 Zeichen lang sein.',
            },
        }


class SendConnectRequestForm(forms.Form):
    """Connect-Anfrage senden"""
    request_type = forms.ChoiceField(
        choices=ConnectRequest.REQUEST_TYPES,
        initial='networking',
        widget=forms.RadioSelect(attrs={'class': 'request-type-radio'}),
        label='Art der Anfrage'
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Schreibe eine persönliche Nachricht...',
            'maxlength': 500
        }),
        label='Nachricht',
        help_text='Stelle dich kurz vor und erkläre, warum du dich vernetzen möchtest',
        error_messages={
            'required': 'Bitte schreibe eine persönliche Nachricht.',
            'max_length': 'Die Nachricht darf maximal 500 Zeichen lang sein.',
        }
    )

    related_skill = forms.ModelChoiceField(
        queryset=Skill.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'data-placeholder': 'Optional: Skill auswählen'
        }),
        label='Bezug zu Skill (optional)'
    )


class StoryCreateForm(forms.ModelForm):
    """Neue Story erstellen"""
    class Meta:
        model = ConnectStory
        fields = ['story_type', 'content', 'image']
        widgets = {
            'story_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Was gibt es Neues?',
                'maxlength': 500
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'story_type': 'Art der Story',
            'content': 'Inhalt',
            'image': 'Bild (optional)',
        }
        error_messages = {
            'content': {
                'max_length': 'Der Story-Inhalt darf maximal 500 Zeichen lang sein.',
            },
            'image': {
                'invalid': 'Bitte wähle eine gültige Bilddatei (JPG, PNG oder GIF).',
            },
        }


class SearchForm(forms.Form):
    """Suche nach Profiles/Skills"""
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Skills, Usern...',
            'autocomplete': 'off'
        }),
        label='',
        error_messages={
            'max_length': 'Die Suchanfrage darf maximal 200 Zeichen lang sein.',
        }
    )

    category = forms.ModelChoiceField(
        queryset=SkillCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Kategorie',
        empty_label='Alle Kategorien'
    )

    availability = forms.ChoiceField(
        choices=[
            ('', 'Alle'),
            ('online', 'Jetzt online'),
            ('active', 'Aktiv in den letzten 7 Tagen'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Verfügbarkeit'
    )

    sort_by = forms.ChoiceField(
        choices=[
            ('relevance', 'Relevanz'),
            ('karma', 'Karma-Score'),
            ('connections', 'Verbindungen'),
            ('recent', 'Neueste zuerst'),
        ],
        initial='relevance',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Sortieren nach'
    )
