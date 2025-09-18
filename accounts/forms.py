from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import authenticate
from .models import CustomUser, AmpelCategory, CategoryKeyword, AppPermission, FeatureAccess


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        
        # Freundliche deutsche Labels und Hilfetexte
        self.fields['username'].label = 'Benutzername'
        self.fields['username'].help_text = 'Wählen Sie einen einzigartigen Benutzernamen (Buchstaben, Zahlen und @/./+/-/_ erlaubt)'
        self.fields['email'].label = 'E-Mail-Adresse'
        self.fields['password1'].label = 'Passwort'
        self.fields['password1'].help_text = 'Ihr Passwort sollte mindestens 8 Zeichen lang sein und nicht nur aus Zahlen bestehen.'
        self.fields['password2'].label = 'Passwort bestätigen'
        self.fields['password2'].help_text = 'Geben Sie das gleiche Passwort zur Bestätigung noch einmal ein.'
    
    error_messages = {
        'password_mismatch': 'Die beiden Passwörter stimmen nicht überein. Bitte versuchen Sie es noch einmal.',
        'username_exists': 'Dieser Benutzername ist leider schon vergeben. Wie wäre es mit einer kleinen Variation?',
    }


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})
        
        # Freundliche deutsche Labels
        self.fields['username'].label = 'Benutzername'
        self.fields['password'].label = 'Passwort'
    
    error_messages = {
        'invalid_login': (
            "Hoppla! 🤔 Das hat leider nicht geklappt. "
            "Bitte überprüfen Sie Ihren Benutzernamen und Ihr Passwort noch einmal. "
            "Achten Sie dabei auf Groß- und Kleinschreibung - manchmal versteckt sich der Fehler in solchen Details!"
        ),
        'inactive': (
            "Ihr Konto ist momentan deaktiviert. "
            "Bitte kontaktieren Sie uns, wenn Sie Hilfe benötigen."
        ),
    }


class ApiKeyForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['openai_api_key', 'anthropic_api_key']
        widgets = {
            'openai_api_key': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ihr OpenAI API Key'}),
            'anthropic_api_key': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ihr Anthropic API Key'}),
        }


class AmpelCategoryForm(forms.ModelForm):
    class Meta:
        model = AmpelCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CategoryKeywordForm(forms.ModelForm):
    class Meta:
        model = CategoryKeyword
        fields = ['keyword', 'weight']
        widgets = {
            'keyword': forms.TextInput(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
        }


class KeywordBulkForm(forms.Form):
    keywords = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Geben Sie Suchbegriffe ein, getrennt durch Kommas oder neue Zeilen...'
        }),
        help_text="Mehrere Begriffe können durch Kommas oder neue Zeilen getrennt werden."
    )


class CompanyInfoForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['company_info', 'learning_goals']
        widgets = {
            'company_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'Beschreiben Sie Ihr Unternehmen, Ihre Produkte, Zielgruppe, etc.'
            }),
            'learning_goals': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 8,
                'placeholder': 'Was möchten Sie standardmäßig in Schulungen lernen?'
            }),
        }


class UserProfileForm(forms.ModelForm):
    """Formular für Benutzer-Profil bearbeiten"""
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'profile_picture', 'enable_chat_email_notifications']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'enable_chat_email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'enable_chat_email_notifications': 'Chat E-Mail-Benachrichtigungen',
        }
        help_texts = {
            'enable_chat_email_notifications': 'E-Mail erhalten bei ungelesenen Nachrichten nach 5 Minuten',
        }
    
    def clean_profile_picture(self):
        """Validierung für Profilbild"""
        profile_picture = self.cleaned_data.get('profile_picture')
        
        if profile_picture:
            # Dateigröße prüfen (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB in Bytes
            if profile_picture.size > max_size:
                raise forms.ValidationError('Die Datei ist zu groß. Maximale Dateigröße: 5MB.')
            
            # Dateityp prüfen
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            file_name = profile_picture.name.lower()
            if not any(file_name.endswith(ext) for ext in valid_extensions):
                raise forms.ValidationError('Ungültiger Dateityp. Erlaubt sind: JPG, JPEG, PNG, GIF, WEBP.')
            
            # MIME-Type prüfen
            import mimetypes
            mime_type, _ = mimetypes.guess_type(profile_picture.name)
            valid_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if mime_type not in valid_mime_types:
                raise forms.ValidationError('Ungültiger Dateityp. Nur Bilddateien sind erlaubt.')
        
        return profile_picture


class CustomPasswordChangeForm(PasswordChangeForm):
    """Erweiterte Passwort-Änderung mit Bootstrap-Styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})


class SuperUserManagementForm(forms.Form):
    """Formular für Super User Verwaltung"""
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Alle Benutzer außer dem aktuellen
        users = CustomUser.objects.all()
        if current_user:
            users = users.exclude(id=current_user.id)
        
        for user in users:
            self.fields[f'user_{user.id}_superuser'] = forms.BooleanField(
                required=False,
                initial=user.is_bug_chat_superuser,
                label=f"{user.username} - Super User",
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            self.fields[f'user_{user.id}_receive_reports'] = forms.BooleanField(
                required=False,
                initial=user.receive_bug_reports,
                label=f"{user.username} - Bug-Meldungen empfangen",
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            self.fields[f'user_{user.id}_receive_anonymous'] = forms.BooleanField(
                required=False,
                initial=user.receive_anonymous_reports,
                label=f"{user.username} - Anonyme Meldungen empfangen",
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )


class BugChatSettingsForm(forms.ModelForm):
    """Formular für Bug-Chat-Einstellungen des aktuellen Users"""
    
    class Meta:
        model = CustomUser
        fields = ['receive_bug_reports', 'receive_anonymous_reports']
        widgets = {
            'receive_bug_reports': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_anonymous_reports': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'receive_bug_reports': 'Bug-Meldungen empfangen',
            'receive_anonymous_reports': 'Anonyme Meldungen empfangen',
        }
        help_texts = {
            'receive_bug_reports': 'Erhalten Sie Bug-Meldungen von angemeldeten Benutzern',
            'receive_anonymous_reports': 'Erhalten Sie auch Bug-Meldungen von nicht angemeldeten Benutzern',
        }


class AppPermissionForm(forms.Form):
    """Formular für App-Freigabe Verwaltung"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hole alle App-Berechtigungen oder erstelle sie wenn sie nicht existieren
        for app_choice in AppPermission.APP_CHOICES:
            app_name = app_choice[0]
            app_display = app_choice[1]
            
            # Hole oder erstelle die Berechtigung
            permission, created = AppPermission.objects.get_or_create(
                app_name=app_name,
                defaults={'access_level': 'blocked', 'is_active': True}
            )
            
            # Hauptfeld für Zugriffsebene
            self.fields[f'app_{app_name}_access'] = forms.ChoiceField(
                choices=AppPermission.ACCESS_LEVEL_CHOICES,
                initial=permission.access_level,
                label=app_display,
                widget=forms.Select(attrs={
                    'class': 'form-select app-access-select',
                    'data-app': app_name
                })
            )
            
            # Frontend ausblenden Option
            self.fields[f'app_{app_name}_hide_frontend'] = forms.BooleanField(
                initial=permission.hide_in_frontend,
                required=False,
                label="Im Frontend ausblenden",
                widget=forms.CheckboxInput(attrs={
                    'class': 'form-check-input',
                    'data-app': app_name
                })
            )
            
            # Superuser Bypass Option
            self.fields[f'app_{app_name}_superuser_bypass'] = forms.BooleanField(
                initial=permission.superuser_bypass,
                required=False,
                label="Superuser können immer zugreifen",
                widget=forms.CheckboxInput(attrs={
                    'class': 'form-check-input',
                    'data-app': app_name
                })
            )
            
            # Feld für ausgewählte Nutzer (Select2-Style mit Filter)
            self.fields[f'app_{app_name}_users'] = forms.ModelMultipleChoiceField(
                queryset=CustomUser.objects.filter(is_active=True).order_by('username'),
                initial=permission.selected_users.all(),
                required=False,
                widget=forms.SelectMultiple(attrs={
                    'class': 'form-select user-select-multiple',
                    'data-app': app_name,
                    'multiple': 'multiple',
                    'size': '8',
                    'style': 'display: none;'  # Wird nur bei 'selected' angezeigt
                })
            )
    
    def save(self):
        """Speichert die App-Berechtigungen"""
        for app_choice in AppPermission.APP_CHOICES:
            app_name = app_choice[0]
            
            # Hole die Berechtigung
            permission = AppPermission.objects.get(app_name=app_name)
            
            # Update Zugriffsebene
            access_level = self.cleaned_data.get(f'app_{app_name}_access')
            if access_level:
                permission.access_level = access_level
            
            # Update Frontend ausblenden
            hide_frontend = self.cleaned_data.get(f'app_{app_name}_hide_frontend', False)
            permission.hide_in_frontend = hide_frontend
            
            # Update Superuser Bypass
            superuser_bypass = self.cleaned_data.get(f'app_{app_name}_superuser_bypass', True)
            permission.superuser_bypass = superuser_bypass
            
            # Update ausgewählte Nutzer
            selected_users = self.cleaned_data.get(f'app_{app_name}_users')
            if selected_users is not None:
                permission.selected_users.set(selected_users)
            
            permission.save()


class FeatureAccessForm(forms.ModelForm):
    """Form für die Verwaltung der Feature-Zugriffsrechte"""
    
    class Meta:
        model = FeatureAccess
        fields = ['app_name', 'subscription_required', 'description', 'is_active', 
                  'show_upgrade_prompt', 'upgrade_message']
        widgets = {
            'app_name': forms.Select(attrs={
                'class': 'form-select'
            }),
            'subscription_required': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Beschreibung der Funktion/App...'
            }),
            'upgrade_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Benutzerdefinierte Upgrade-Nachricht (optional)...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'show_upgrade_prompt': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'app_name': 'App/Feature',
            'subscription_required': 'Erforderliches Abonnement',
            'description': 'Beschreibung',
            'is_active': 'Aktiv',
            'show_upgrade_prompt': 'Upgrade-Hinweis anzeigen',
            'upgrade_message': 'Benutzerdefinierte Upgrade-Nachricht',
        }
        help_texts = {
            'description': 'Kurze Beschreibung der Funktion oder App',
            'upgrade_message': 'Wird angezeigt wenn ein Benutzer ohne Berechtigung zugreifen möchte (optional)',
            'show_upgrade_prompt': 'Ob ein Upgrade-Hinweis angezeigt werden soll',
        }


class BulkFeatureAccessForm(forms.Form):
    """Form für Bulk-Aktionen auf Feature-Zugriffe"""
    
    BULK_ACTIONS = [
        ('', '--- Aktion auswählen ---'),
        ('activate', 'Aktivieren'),
        ('deactivate', 'Deaktivieren'),
        ('set_free', 'Auf kostenlosen Zugang setzen'),
        ('set_founder_access', 'Auf Founder Access setzen'),
        ('set_any_paid', 'Auf beliebiges bezahltes Abo setzen'),
        ('set_storage_plan', 'Auf Storage-Plan setzen'),
        ('set_blocked', 'Sperren'),
    ]
    
    action = forms.ChoiceField(
        choices=BULK_ACTIONS,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Aktion'
    )
    
    selected_features = forms.ModelMultipleChoiceField(
        queryset=FeatureAccess.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label='Ausgewählte Features',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_features'].queryset = FeatureAccess.objects.all().order_by('app_name')


class FeatureAccessFilterForm(forms.Form):
    """Filter-Form für Feature-Zugriffe"""
    
    SUBSCRIPTION_FILTER_CHOICES = [
        ('', 'Alle Abonnement-Typen'),
        ('free', 'Kostenlos verfügbar'),
        ('founder_access', 'Founder\'s Early Access erforderlich'),
        ('any_paid', 'Beliebiges bezahltes Abo erforderlich'),
        ('storage_plan', 'Storage-Plan erforderlich'),
        ('blocked', 'Komplett gesperrt'),
    ]
    
    STATUS_FILTER_CHOICES = [
        ('', 'Alle Status'),
        ('active', 'Nur aktive'),
        ('inactive', 'Nur inaktive'),
    ]
    
    subscription_required = forms.ChoiceField(
        choices=SUBSCRIPTION_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        }),
        label='Abonnement-Typ'
    )
    
    is_active = forms.ChoiceField(
        choices=STATUS_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        }),
        label='Status'
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Nach App/Feature suchen...'
        }),
        label='Suche'
    )


class CustomPasswordResetForm(PasswordResetForm):
    """Erweiterte Passwort-Zurücksetzen mit Bootstrap-Styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ihre E-Mail-Adresse eingeben'
        })
        self.fields['email'].label = 'E-Mail-Adresse'
        self.fields['email'].help_text = 'Geben Sie die E-Mail-Adresse Ihres Kontos ein. Wir senden Ihnen einen Link zum Zurücksetzen des Passworts.'


class CustomSetPasswordForm(SetPasswordForm):
    """Erweiterte Passwort-Setzen mit Bootstrap-Styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Neues Passwort eingeben'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Neues Passwort bestätigen'
        })
        self.fields['new_password1'].label = 'Neues Passwort'
        self.fields['new_password2'].label = 'Passwort bestätigen'
        self.fields['new_password1'].help_text = 'Ihr Passwort sollte mindestens 8 Zeichen lang sein und nicht nur aus Zahlen bestehen.'
        self.fields['new_password2'].help_text = 'Geben Sie das gleiche Passwort zur Bestätigung noch einmal ein.'
    
    error_messages = {
        'password_mismatch': 'Die beiden Passwörter stimmen nicht überein. Bitte versuchen Sie es noch einmal.',
    }