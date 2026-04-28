"""Forms für Magvis-Wizard."""
from django import forms

from .models import MagvisProject, MagvisReportConfig, MagvisSettings, MagvisTopicQueue


class ProjectStartForm(forms.ModelForm):
    keywords_text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Komma-getrennt'}),
        required=False, label='Keywords (kommagetrennt)',
    )
    use_queue = forms.BooleanField(
        required=False, label='Aus Themen-Queue ziehen',
        help_text='Wenn aktiv: Topic + Keywords werden aus dem nächsten pending Queue-Eintrag übernommen.',
    )

    class Meta:
        model = MagvisProject
        fields = ['title', 'topic', 'target_audience', 'scheduled_at', 'auto_advance']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'z.B. "Geschenk Erzieherin Kindergarten-Abschied"'}),
            'target_audience': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'auto_advance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('keywords_text'):
            cleaned['keywords'] = [k.strip() for k in cleaned['keywords_text'].split(',') if k.strip()]
        else:
            cleaned['keywords'] = []
        return cleaned


class MagvisSettingsForm(forms.ModelForm):
    fixed_cdn_image_urls_text = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                     'placeholder': 'Eine URL pro Zeile (3 fixe CDN-Bilder)'}),
        required=False, label='Fixe CDN-Bild-URLs',
    )
    default_image_platforms_text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'z.B. pinterest,instagram,facebook'}),
        required=False, label='Default-Plattformen für Bilder (kommagetrennt)',
    )

    class Meta:
        model = MagvisSettings
        exclude = ['user', 'fixed_cdn_image_urls', 'default_image_platforms', 'created_at', 'updated_at']
        widgets = {
            'glm_model': forms.TextInput(attrs={'class': 'form-control'}),
            'glm_base_url': forms.URLInput(attrs={'class': 'form-control'}),
            'gemini_image_model': forms.TextInput(attrs={'class': 'form-control'}),
            'default_video_template': forms.TextInput(attrs={'class': 'form-control'}),
            'default_video_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_voice': forms.TextInput(attrs={'class': 'form-control'}),
            'default_quiz_questions': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_faq_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'naturmacher_brand_voice': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'default_ploom_settings': forms.Select(attrs={'class': 'form-select'}),
            'upload_post_user': forms.TextInput(attrs={'class': 'form-control'}),
            'auto_run_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_run_schedule': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0 6 * * *'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['fixed_cdn_image_urls_text'].initial = '\n'.join(
                self.instance.fixed_cdn_image_urls or []
            )
            self.fields['default_image_platforms_text'].initial = ','.join(
                self.instance.default_image_platforms or []
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        text_urls = self.cleaned_data.get('fixed_cdn_image_urls_text', '')
        instance.fixed_cdn_image_urls = [u.strip() for u in text_urls.splitlines() if u.strip()]
        text_plats = self.cleaned_data.get('default_image_platforms_text', '')
        instance.default_image_platforms = [p.strip() for p in text_plats.split(',') if p.strip()]
        if commit:
            instance.save()
        return instance


class ReportConfigForm(forms.ModelForm):
    cc_emails_text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'optional, kommagetrennt'}),
        required=False, label='CC-Empfänger',
    )

    class Meta:
        model = MagvisReportConfig
        exclude = ['user', 'cc_emails', 'created_at', 'updated_at']
        widgets = {
            'report_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'subject_template': forms.TextInput(attrs={'class': 'form-control'}),
        }
        for fld in ['include_video_link', 'include_youtube_link', 'include_product_links',
                    'include_product_thumbnails', 'include_blog_link', 'include_blog_excerpt',
                    'include_diagram_image', 'include_brainstorm_image',
                    'include_image_post_summary', 'include_costs']:
            widgets[fld] = forms.CheckboxInput(attrs={'class': 'form-check-input'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['cc_emails_text'].initial = ','.join(self.instance.cc_emails or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        text_cc = self.cleaned_data.get('cc_emails_text', '')
        instance.cc_emails = [c.strip() for c in text_cc.split(',') if c.strip()]
        if commit:
            instance.save()
        return instance


class TopicQueueForm(forms.ModelForm):
    keywords_text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'kommagetrennt'}),
        required=False, label='Keywords',
    )

    class Meta:
        model = MagvisTopicQueue
        fields = ['topic', 'target_audience', 'priority', 'notes', 'status']
        widgets = {
            'topic': forms.TextInput(attrs={'class': 'form-control'}),
            'target_audience': forms.TextInput(attrs={'class': 'form-control'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['keywords_text'].initial = ','.join(self.instance.keywords or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        text = self.cleaned_data.get('keywords_text', '')
        instance.keywords = [k.strip() for k in text.split(',') if k.strip()]
        if commit:
            instance.save()
        return instance
