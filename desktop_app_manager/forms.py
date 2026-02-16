"""
Desktop App Manager Forms
"""

from django import forms
from .models import DesktopApp, AppVersion, AppScreenshot


class DesktopAppForm(forms.ModelForm):
    """Form fuer App-Erstellung"""

    class Meta:
        model = DesktopApp
        fields = ['name', 'app_identifier', 'description', 'icon', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. PDF-Marker'
            }),
            'app_identifier': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. pdf-marker'
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
            'app_identifier': 'App-Identifier',
            'description': 'Beschreibung',
            'icon': 'App-Icon (optional)',
            'is_public': 'Oeffentlich (fuer alle downloadbar)',
        }
        help_texts = {
            'app_identifier': 'Eindeutiger Bezeichner, z.B. pdf-marker',
            'is_public': 'Wenn aktiviert, kann jeder die App herunterladen',
        }


class AppVersionForm(forms.ModelForm):
    """Form fuer Version-Upload"""

    class Meta:
        model = AppVersion
        fields = [
            'app', 'version_name', 'version_code', 'exe_file',
            'release_notes', 'channel', 'min_windows_version',
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
            'exe_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.exe'
            }),
            'release_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Was ist neu in dieser Version?'
            }),
            'channel': forms.Select(attrs={
                'class': 'form-select'
            }),
            'min_windows_version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. 10'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_current_for_channel': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'app': 'App auswaehlen',
            'version_name': 'Version Name',
            'version_code': 'Version Code (Build Number)',
            'exe_file': 'EXE-Datei',
            'release_notes': 'Release Notes',
            'channel': 'Release Channel',
            'min_windows_version': 'Minimale Windows Version',
            'is_active': 'Version aktiv',
            'is_current_for_channel': 'Als aktuelle Version fuer diesen Channel markieren',
        }
        help_texts = {
            'version_code': 'Muss hoeher sein als die vorherige Version! (Integer)',
            'channel': 'Production = Stabil, Beta = Test, Alpha = Experimental',
            'is_active': 'Inaktive Versionen werden nicht angezeigt',
            'is_current_for_channel': 'Wird automatisch bei Update-Checks zurueckgegeben',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['app'].queryset = DesktopApp.objects.filter(created_by=user)

        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['channel'].initial = 'production'


class MultipleFileInput(forms.FileInput):
    """Custom FileInput widget that allows multiple file selection"""
    allow_multiple_selected = True


class MultipleScreenshotForm(forms.Form):
    """Form fuer Mehrfach-Upload von Screenshots"""

    screenshots = forms.FileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
        }),
        label='Screenshots hochladen',
        help_text='Waehle bis zu 10 Bilder aus (PNG, JPG, WebP)',
        required=False
    )

    def __init__(self, *args, app=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app

        if app:
            remaining = 10 - AppScreenshot.objects.filter(app=app).count()
            self.fields['screenshots'].help_text = f'Noch {remaining} Screenshots moeglich (max. 10)'
