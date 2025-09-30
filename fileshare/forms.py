from django import forms
from django.core.validators import validate_email
from .models import Transfer

class TransferForm(forms.ModelForm):
    recipients = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'E-Mail-Adressen durch Kommas getrennt eingeben'
        }),
        help_text='E-Mail-Adressen durch Kommas getrennt eingeben'
    )

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Optionaler Passwort-Schutz'
        }),
        help_text='Passwort festlegen um den Download zu schützen'
    )

    expiry_days = forms.IntegerField(
        initial=7,
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text='Anzahl der Tage bis der Transfer abläuft'
    )

    class Meta:
        model = Transfer
        fields = ['title', 'message', 'transfer_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optionaler Transfer-Titel'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optionale Nachricht für Empfänger'
            }),
            'transfer_type': forms.RadioSelect()
        }

    def clean_recipients(self):
        recipients = self.cleaned_data.get('recipients', '')
        if not recipients and self.cleaned_data.get('transfer_type') == 'email':
            raise forms.ValidationError('Recipients are required for email transfers')

        # Validate email addresses
        if recipients:
            emails = [email.strip() for email in recipients.split(',')]
            for email in emails:
                if email:
                    try:
                        validate_email(email)
                    except forms.ValidationError:
                        raise forms.ValidationError(f'Invalid email address: {email}')

        return recipients