"""
Android APK Manager Forms
"""

from django import forms
from .models import AndroidApp, AppVersion, AppScreenshot


class AndroidAppForm(forms.ModelForm):
    """Form für App-Erstellung"""

    class Meta:
        model = AndroidApp
        fields = ['name', 'package_name', 'description', 'icon', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Kiosk Video App'
            }),
            'package_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. com.example.app'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Beschreibung der App...'
            }),
            'icon': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'name': 'App-Name',
            'package_name': 'Package Name',
            'description': 'Beschreibung',
            'icon': 'App-Icon (optional)',
            'is_public': 'Öffentlich (für alle downloadbar)',
        }
        help_texts = {
            'package_name': 'Muss mit dem Package-Namen in der APK übereinstimmen',
            'is_public': 'Wenn aktiviert, kann jeder die App herunterladen',
        }


class AppVersionForm(forms.ModelForm):
    """Form für Version-Upload"""

    class Meta:
        model = AppVersion
        fields = [
            'app', 'version_name', 'version_code', 'apk_file',
            'release_notes', 'channel', 'min_android_version',
            'is_active', 'is_current_for_channel'
        ]
        widgets = {
            'app': forms.Select(attrs={
                'class': 'form-select'
            }),
            'version_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. 1.0.1'
            }),
            'version_code': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. 2'
            }),
            'apk_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.apk'
            }),
            'release_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Was ist neu in dieser Version?'
            }),
            'channel': forms.Select(attrs={
                'class': 'form-select'
            }),
            'min_android_version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. 5.0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_current_for_channel': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'app': 'App auswählen',
            'version_name': 'Version Name',
            'version_code': 'Version Code (Build Number)',
            'apk_file': 'APK-Datei',
            'release_notes': 'Release Notes',
            'channel': 'Release Channel',
            'min_android_version': 'Minimale Android Version',
            'is_active': 'Version aktiv',
            'is_current_for_channel': 'Als aktuelle Version für diesen Channel markieren',
        }
        help_texts = {
            'version_code': 'Muss höher sein als die vorherige Version! (Integer)',
            'channel': 'Production = Stabil, Beta = Test, Alpha = Experimental',
            'is_active': 'Inaktive Versionen werden nicht angezeigt',
            'is_current_for_channel': 'Wird automatisch bei Update-Checks zurückgegeben',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Nur eigene Apps anzeigen
        if user:
            self.fields['app'].queryset = AndroidApp.objects.filter(created_by=user)

        # Default-Werte setzen
        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['channel'].initial = 'production'


class AppScreenshotForm(forms.ModelForm):
    """Form für Screenshot-Upload"""

    class Meta:
        model = AppScreenshot
        fields = ['image', 'caption']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optionale Beschreibung...'
            }),
        }
        labels = {
            'image': 'Screenshot',
            'caption': 'Bildunterschrift (optional)',
        }


class MultipleFileInput(forms.FileInput):
    """Custom FileInput widget that allows multiple file selection"""
    allow_multiple_selected = True


class MultipleScreenshotForm(forms.Form):
    """Form für Mehrfach-Upload von Screenshots"""

    screenshots = forms.FileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
        }),
        label='Screenshots hochladen',
        help_text='Wähle bis zu 10 Bilder aus (PNG, JPG, WebP)',
        required=False
    )

    def __init__(self, *args, app=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

        if app:
            remaining = 10 - AppScreenshot.objects.filter(app=app).count()
            self.fields['screenshots'].help_text = f'Noch {remaining} Screenshots möglich (max. 10)'
