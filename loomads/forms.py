from django import forms
from django.utils import timezone
from .models import Campaign, Advertisement, AdZone, AdTargeting, ZoneIntegration, AppCampaign, AppAdvertisement, SimpleAd


class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns"""

    class Meta:
        model = Campaign
        fields = ['name', 'description', 'status', 'start_date', 'end_date',
                  'daily_impression_limit', 'total_impression_limit',
                  'daily_click_limit', 'total_click_limit']
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
                'type': 'datetime-local',
                'placeholder': 'Leer lassen für "Ab sofort"'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'Leer lassen für "Unbegrenzt"'
            }),
            'daily_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'total_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'daily_click_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'total_click_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
        }
        labels = {
            'name': 'Kampagnenname',
            'description': 'Beschreibung',
            'status': 'Status',
            'start_date': 'Startdatum (optional)',
            'end_date': 'Enddatum (optional)',
            'daily_impression_limit': 'Tägliches Impression-Limit',
            'total_impression_limit': 'Gesamt Impression-Limit',
            'daily_click_limit': 'Tägliches Klick-Limit',
            'total_click_limit': 'Gesamt Klick-Limit',
        }
        help_texts = {
            'start_date': 'Leer lassen für "Ab sofort"',
            'end_date': 'Leer lassen für "Unbegrenzt"',
            'daily_impression_limit': 'Maximale Anzahl der Impressions pro Tag',
            'total_impression_limit': 'Maximale Anzahl der Impressions insgesamt',
            'daily_click_limit': 'Maximale Anzahl der Klicks pro Tag',
            'total_click_limit': 'Maximale Anzahl der Klicks insgesamt',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Felder optional machen
        self.fields['start_date'].required = False
        self.fields['end_date'].required = False
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


class ZoneIntegrationForm(forms.ModelForm):
    """Form for creating and editing zone integrations"""
    
    class Meta:
        model = ZoneIntegration
        fields = ['zone_code', 'template_path', 'visibility', 'status', 'description']
        widgets = {
            'zone_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. header_main'
            }),
            'template_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. base.html oder accounts/dashboard.html'
            }),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Zusätzliche Informationen zur Integration'
            }),
        }
        labels = {
            'zone_code': 'Zone Code',
            'template_path': 'Template-Pfad',
            'visibility': 'Sichtbar für',
            'status': 'Status',
            'description': 'Beschreibung',
        }
        help_texts = {
            'zone_code': 'Der Code der Zone, die in diesem Template integriert ist',
            'template_path': 'Pfad zum Template relativ zum templates/ Ordner',
            'visibility': 'Für welche Benutzergruppen ist die Zone sichtbar',
            'status': 'Aktueller Status der Integration',
        }


class AppCampaignForm(forms.ModelForm):
    """Form for creating and editing app campaigns"""

    class Meta:
        model = AppCampaign
        fields = ['name', 'description', 'app_target', 'status', 'priority',
                  'start_date', 'end_date', 'auto_include_new_zones', 'exclude_zone_types',
                  'weight_multiplier', 'daily_impression_limit', 'total_impression_limit',
                  'daily_click_limit', 'total_click_limit']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'App-Kampagnenname eingeben'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der App-Kampagne'
            }),
            'app_target': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'Leer lassen für "Ab sofort"'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'Leer lassen für "Unbegrenzt"'
            }),
            'auto_include_new_zones': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exclude_zone_types': forms.CheckboxSelectMultiple(),
            'weight_multiplier': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0.1,
                'max': 5.0,
                'step': 0.1,
                'value': 1.0
            }),
            'daily_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'total_impression_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'daily_click_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
            'total_click_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leer lassen für unbegrenzt'
            }),
        }
        labels = {
            'name': 'Kampagnenname',
            'description': 'Beschreibung',
            'app_target': 'Ziel-App',
            'status': 'Status',
            'priority': 'Priorität',
            'start_date': 'Startdatum (optional)',
            'end_date': 'Enddatum (optional)',
            'auto_include_new_zones': 'Neue Zonen automatisch einbeziehen',
            'exclude_zone_types': 'Ausgeschlossene Zone-Typen',
            'weight_multiplier': 'Gewichtungs-Multiplikator',
            'daily_impression_limit': 'Tägliches Impression-Limit (pro App)',
            'total_impression_limit': 'Gesamt Impression-Limit (pro App)',
            'daily_click_limit': 'Tägliches Klick-Limit (pro App)',
            'total_click_limit': 'Gesamt Klick-Limit (pro App)',
        }
        help_texts = {
            'app_target': 'App für die diese Kampagne geschaltet wird',
            'priority': 'Höhere Priorität = häufigere Anzeige in App-Zonen',
            'start_date': 'Leer lassen für "Ab sofort"',
            'end_date': 'Leer lassen für "Unbegrenzt"',
            'auto_include_new_zones': 'Neue Zonen der App automatisch zu dieser Kampagne hinzufügen',
            'exclude_zone_types': 'Zone-Typen die von dieser App-Kampagne ausgeschlossen werden sollen',
            'weight_multiplier': 'Multiplikator für die Anzeigengewichtung in App-Zonen (0.1 - 5.0)',
            'daily_impression_limit': 'Maximale Anzahl der Impressions pro Tag für alle App-Zonen',
            'total_impression_limit': 'Maximale Anzahl der Impressions insgesamt für alle App-Zonen',
            'daily_click_limit': 'Maximale Anzahl der Klicks pro Tag für alle App-Zonen',
            'total_click_limit': 'Maximale Anzahl der Klicks insgesamt für alle App-Zonen',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Felder optional machen
        self.fields['start_date'].required = False
        self.fields['end_date'].required = False
        # Format datetime fields for HTML5 datetime-local input
        if self.instance.pk:
            if self.instance.start_date:
                self.fields['start_date'].initial = self.instance.start_date.strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_date:
                self.fields['end_date'].initial = self.instance.end_date.strftime('%Y-%m-%dT%H:%M')


class AppAdvertisementForm(forms.ModelForm):
    """Form for creating and editing app advertisements"""

    class Meta:
        model = AppAdvertisement
        fields = ['name', 'description', 'ad_type', 'title', 'description_text', 'html_content',
                  'image', 'video_url', 'link_url', 'link_text', 'weight', 'device_targeting', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name der App-Anzeige eingeben'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der App-Anzeige'
            }),
            'ad_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anzeigentitel'
            }),
            'description_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Beschreibungstext der Anzeige'
            }),
            'html_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'HTML-Code für die Anzeige',
                'style': 'font-family: monospace;'
            }),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/video.mp4'
            }),
            'link_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/landing-page'
            }),
            'link_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Link-Text (optional)'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'value': 5
            }),
            'device_targeting': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Anzeigenname',
            'description': 'Beschreibung',
            'ad_type': 'Anzeigentyp',
            'title': 'Titel',
            'description_text': 'Beschreibungstext',
            'html_content': 'HTML Inhalt',
            'image': 'Bild',
            'video_url': 'Video URL',
            'link_url': 'Ziel-URL',
            'link_text': 'Link-Text',
            'weight': 'Gewichtung',
            'device_targeting': 'Geräte-Targeting',
            'is_active': 'Aktiv',
        }
        help_texts = {
            'weight': 'Anzeigengewichtung (1-10) - wird mit App-Kampagne Multiplikator kombiniert',
            'device_targeting': 'Für welche Geräte soll die Anzeige angezeigt werden',
            'html_content': 'HTML-Code für Rich Content Anzeigen',
            'link_text': 'Optionaler Text für den Link (falls leer wird der Titel verwendet)',
        }


class SimpleAdForm(forms.ModelForm):
    """
    Einfaches Formular für globale Anzeigen.
    Übersichtlich und benutzerfreundlich.
    """

    class Meta:
        model = SimpleAd
        fields = [
            # Content
            'title', 'description', 'image', 'icon', 'video_url',
            'button_text', 'target_url', 'open_in_new_tab',
            # Styling
            'template_style', 'color_scheme', 'custom_color', 'animation',
            # Badge
            'badge', 'badge_custom_text',
            # Zeitplanung
            'start_date', 'end_date', 'countdown_enabled', 'countdown_text',
            # Targeting
            'target_audience', 'app_filter', 'exclude_apps',
            # A/B Testing
            'variant_name', 'ab_test_group',
            # Display
            'is_active', 'weight'
        ]
        widgets = {
            # Content
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'z.B. "Jetzt 20% Rabatt sichern!"',
                'maxlength': 100
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optionale kurze Beschreibung (max. 300 Zeichen)',
                'maxlength': 300
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'icon': forms.Select(attrs={
                'class': 'form-select'
            }),
            'video_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/video.mp4'
            }),
            'button_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mehr erfahren',
                'maxlength': 30
            }),
            'target_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/landing-page'
            }),
            'open_in_new_tab': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            # Styling
            'template_style': forms.Select(attrs={
                'class': 'form-select'
            }),
            'color_scheme': forms.Select(attrs={
                'class': 'form-select'
            }),
            'custom_color': forms.TextInput(attrs={
                'class': 'form-control form-control-color',
                'type': 'color',
                'style': 'width: 60px; height: 38px;'
            }),
            'animation': forms.Select(attrs={
                'class': 'form-select'
            }),
            # Badge
            'badge': forms.Select(attrs={
                'class': 'form-select'
            }),
            'badge_custom_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Eigener Badge-Text',
                'maxlength': 20
            }),
            # Zeitplanung
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'countdown_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'countdown_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nur noch:'
            }),
            # Targeting
            'target_audience': forms.Select(attrs={
                'class': 'form-select'
            }),
            'app_filter': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 4
            }),
            'exclude_apps': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 4
            }),
            # A/B Testing
            'variant_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Variante A'
            }),
            'ab_test_group': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Homepage-Banner-Test'
            }),
            # Display
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'style': 'width: 80px;'
            }),
        }
        labels = {
            'title': 'Titel',
            'description': 'Beschreibung (optional)',
            'image': 'Bild (optional)',
            'icon': 'Icon (optional)',
            'video_url': 'Video-Hintergrund (optional)',
            'button_text': 'Button-Text',
            'target_url': 'Ziel-URL',
            'open_in_new_tab': 'In neuem Tab öffnen',
            'template_style': 'Design-Vorlage',
            'color_scheme': 'Farbschema',
            'custom_color': 'Eigene Farbe',
            'animation': 'Animation',
            'badge': 'Badge/Label',
            'badge_custom_text': 'Eigener Badge-Text',
            'start_date': 'Startdatum',
            'end_date': 'Enddatum',
            'countdown_enabled': 'Countdown anzeigen',
            'countdown_text': 'Countdown-Text',
            'target_audience': 'Zielgruppe',
            'app_filter': 'Nur in diesen Apps',
            'exclude_apps': 'Nicht in diesen Apps',
            'variant_name': 'Varianten-Name',
            'ab_test_group': 'A/B-Test Gruppe',
            'is_active': 'Aktiv',
            'weight': 'Gewichtung',
        }
        help_texts = {
            'title': 'Kurzer, aussagekräftiger Titel (max. 100 Zeichen)',
            'description': 'Optionale Beschreibung die unter dem Titel angezeigt wird',
            'image': 'Optionales Bild - wird automatisch an das Format angepasst',
            'icon': 'Bootstrap Icon (Alternative zu Bild)',
            'video_url': 'URL zu einem kurzen Loop-Video (MP4)',
            'button_text': 'Text auf dem Aktions-Button',
            'target_url': 'Wohin soll die Anzeige verlinken?',
            'template_style': 'Wähle einen Design-Stil für die Anzeige',
            'color_scheme': 'Wähle ein Farbschema',
            'custom_color': 'Nur bei "Eigene Farbe" aktiv',
            'animation': 'Animations-Effekt beim Laden oder Hover',
            'badge': 'Auffälliges Label in der Ecke',
            'badge_custom_text': 'Nur bei "Eigener Text"',
            'start_date': 'Ab wann soll die Anzeige erscheinen?',
            'end_date': 'Bis wann soll die Anzeige erscheinen?',
            'countdown_enabled': 'Zeigt einen Countdown bis zum Enddatum',
            'countdown_text': 'Text der vor dem Countdown angezeigt wird',
            'target_audience': 'Für welche Nutzer soll die Anzeige sichtbar sein?',
            'app_filter': 'Leer = alle Apps',
            'exclude_apps': 'In diesen Apps nicht anzeigen',
            'variant_name': 'Name für A/B-Tests',
            'ab_test_group': 'Anzeigen mit gleichem Gruppennamen werden getestet',
            'weight': '1-10: Höhere Werte = häufigere Anzeige',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Format datetime fields für HTML5 datetime-local input
        if self.instance.pk:
            if self.instance.start_date:
                self.fields['start_date'].initial = self.instance.start_date.strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_date:
                self.fields['end_date'].initial = self.instance.end_date.strftime('%Y-%m-%dT%H:%M')