"""
Custom Allauth Adapter für WorkLoom
Ermöglicht die Integration von Google Sign-In mit dem CustomUser Model
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom Account Adapter für django-allauth.
    Passt die Standard-Logik an unser CustomUser Model an.
    """

    def save_user(self, request, user, form, commit=True):
        """
        Speichert einen neuen User. Wird bei Registrierung aufgerufen.
        """
        user = super().save_user(request, user, form, commit=False)

        # Optional: Zusätzliche Felder setzen
        # user.some_field = form.cleaned_data.get('some_field', '')

        if commit:
            user.save()
        return user

    def get_login_redirect_url(self, request):
        """
        URL nach erfolgreichem Login.
        """
        return '/accounts/dashboard/'

    def get_signup_redirect_url(self, request):
        """
        URL nach erfolgreicher Registrierung.
        """
        return '/accounts/dashboard/'


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom Social Account Adapter für Google Sign-In.
    Verknüpft Social Accounts mit unserem CustomUser Model.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Wird vor dem Social Login aufgerufen.
        Ermöglicht die Verknüpfung mit bestehenden Accounts basierend auf Email.
        """
        # Wenn User bereits eingeloggt ist, nichts tun
        if sociallogin.is_existing:
            return

        # Email aus Social Account holen
        email = None
        if sociallogin.account.extra_data:
            email = sociallogin.account.extra_data.get('email')

        if not email:
            # Keine Email im Social Account
            return

        # Prüfen ob User mit dieser Email bereits existiert
        try:
            existing_user = User.objects.get(email__iexact=email)
            # Verknüpfe Social Account mit bestehendem User
            sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            # Kein bestehender User - neuer Account wird erstellt
            pass

    def populate_user(self, request, sociallogin, data):
        """
        Befüllt User-Daten aus dem Social Account.
        """
        user = super().populate_user(request, sociallogin, data)

        # Optional: Zusätzliche Felder aus Google-Daten setzen
        extra_data = sociallogin.account.extra_data

        # Beispiel: Vorname und Nachname setzen
        if extra_data:
            user.first_name = extra_data.get('given_name', user.first_name or '')
            user.last_name = extra_data.get('family_name', user.last_name or '')

        return user

    def get_signup_form_initial_data(self, sociallogin):
        """
        Initiale Formular-Daten für Social Signup.
        """
        initial = super().get_signup_form_initial_data(sociallogin)

        # Username aus Email ableiten falls nicht vorhanden
        if not initial.get('username') and initial.get('email'):
            email = initial['email']
            username_base = email.split('@')[0]
            username = username_base

            # Sicherstellen dass Username einzigartig ist
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1

            initial['username'] = username

        return initial
