from django import forms
from django.utils import timezone
from .models import Campaign, Advertisement, AdZone, AdTargeting


class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns"""
    
    class Meta:
        model = Campaign
        fields = ['name', 'description', 'status', 'start_date', 'end_date', 
                  'daily_impression_limit', 'total_impression_limit']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kampagnenname eingeben'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der Kampagne'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'daily_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'total_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
        }
        labels = {
            'name': 'Kampagnenname',
            'description': 'Beschreibung',
            'status': 'Status',
            'start_date': 'Startdatum',
            'end_date': 'Enddatum',
            'daily_impression_limit': 'Tägliches Impression-Limit',
            'total_impression_limit': 'Gesamt Impression-Limit',
        }
        help_texts = {
            'daily_impression_limit': 'Maximale Anzahl der Impressions pro Tag',
            'total_impression_limit': 'Maximale Anzahl der Impressions insgesamt',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Format datetime fields for HTML5 datetime-local input
        if self.instance.pk:
            if self.instance.start_date:
                self.fields['start_date'].initial = self.instance.start_date.strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_date:
                self.fields['end_date'].initial = self.instance.end_date.strftime('%Y-%m-%dT%H:%M')


class AdvertisementForm(forms.ModelForm):
    """Form for creating and editing advertisements"""
    
    class Meta:
        model = Advertisement
        fields = ['campaign', 'name', 'ad_type', 'image', 'video_url', 'video_with_audio', 'title', 
                  'description', 'html_content', 'target_url', 'target_type', 
                  'weight', 'is_active', 'zones']
        widgets = {
            'campaign': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anzeigenname eingeben'
            }),
            'ad_type': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/video.mp4'
            }),
            'video_with_audio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anzeigentitel'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der Anzeige'
            }),
            'html_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'HTML-Code für die Anzeige',
                'style': 'font-family: monospace;'
            }),
            'target_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/landing-page'
            }),
            'target_type': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'zones': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'campaign': 'Kampagne',
            'name': 'Anzeigenname',
            'ad_type': 'Anzeigentyp',
            'image': 'Bild',
            'video_url': 'Video URL',
            'video_with_audio': 'Video mit Ton',
            'title': 'Titel',
            'description': 'Beschreibung',
            'html_content': 'HTML Inhalt',
            'target_url': 'Ziel-URL',
            'target_type': 'Link öffnen in',
            'weight': 'Gewichtung',
            'is_active': 'Aktiv',
            'zones': 'Werbezonen',
        }
        help_texts = {
            'weight': 'Höhere Gewichtung = häufigere Anzeige (1-10)',
            'video_with_audio': 'Soll das Video mit oder ohne Ton abgespielt werden?',
            'zones': 'Wählen Sie die Zonen aus, in denen diese Anzeige erscheinen soll',
        }


class AdZoneForm(forms.ModelForm):
    """Form for creating and editing ad zones"""
    
    class Meta:
        model = AdZone
        fields = ['code', 'name', 'description', 'zone_type', 'width', 'height', 
                  'max_ads', 'popup_delay', 'is_active', 'app_restriction']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'zone_code',
                'pattern': '[a-z0-9_]+',
                'title': 'Nur Kleinbuchstaben, Zahlen und Unterstriche'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Zone Name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der Zone'
            }),
            'zone_type': forms.Select(attrs={'class': 'form-select'}),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Breite in Pixel'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Höhe in Pixel'
            }),
            'max_ads': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'popup_delay': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 60,
                'value': 5,
                'placeholder': 'Verzögerung in Sekunden'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'app_restriction': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für überall'
            }),
        }
        labels = {
            'code': 'Zone Code',
            'name': 'Zone Name',
            'description': 'Beschreibung',
            'zone_type': 'Zone Typ',
            'width': 'Breite (px)',
            'height': 'Höhe (px)',
            'max_ads': 'Maximale Anzahl Anzeigen',
            'popup_delay': 'Popup Verzögerung (Sek.)',
            'is_active': 'Aktiv',
            'app_restriction': 'App-Beschränkung',
        }
        help_texts = {
            'code': 'Eindeutiger Code für die Zone (z.B. header_main)',
            'max_ads': 'Wie viele Anzeigen können gleichzeitig in dieser Zone angezeigt werden',
            'popup_delay': 'Nach wie vielen Sekunden soll das Video-Popup erscheinen? (nur für video_popup Zonen)',
            'app_restriction': 'Nur in dieser App anzeigen (leer = überall)',
        }