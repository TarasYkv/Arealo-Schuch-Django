from django import forms
from .models import BugReport, BugReportAttachment


class BugReportForm(forms.ModelForm):
    """Formular für Bug-Meldungen"""
    
    class Meta:
        model = BugReport
        fields = ['subject', 'message', 'sender_name', 'sender_email']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kurze Beschreibung des Problems'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Detaillierte Beschreibung des Problems...'
            }),
            'sender_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ihr Name'
            }),
            'sender_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'ihre.email@example.com'
            })
        }
        labels = {
            'subject': 'Betreff',
            'message': 'Nachricht',
            'sender_name': 'Name',
            'sender_email': 'E-Mail-Adresse'
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Wenn User angemeldet ist, verstecke anonyme Felder
        if user and user.is_authenticated:
            self.fields['sender_name'].widget = forms.HiddenInput()
            self.fields['sender_email'].widget = forms.HiddenInput()
        else:
            # Für anonyme User sind Name und E-Mail erforderlich
            self.fields['sender_name'].required = True
            self.fields['sender_email'].required = True


class BugReportAttachmentForm(forms.ModelForm):
    """Formular für Datei-Anhänge"""
    
    class Meta:
        model = BugReportAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.zip'
            })
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Überprüfe Dateigröße (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Datei ist zu groß. Maximum: 10MB')
            
            # Überprüfe erlaubte Dateitypen
            allowed_types = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf', 'text/plain',
                'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/zip', 'application/x-zip-compressed'
            ]
            
            if file.content_type not in allowed_types:
                raise forms.ValidationError('Dateityp nicht erlaubt.')
        
        return file