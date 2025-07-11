"""
Deutsche Übersetzungen für Django Auth Fehlermeldungen
"""

# Diese können in settings.py importiert werden
DJANGO_AUTH_ERROR_MESSAGES = {
    'invalid_login': {
        'en': 'Please enter a correct username and password. Note that both fields may be case-sensitive.',
        'de': 'Hoppla! 🤔 Das hat leider nicht geklappt. Bitte überprüfen Sie Ihren Benutzernamen und Ihr Passwort noch einmal. Achten Sie dabei auf Groß- und Kleinschreibung - manchmal versteckt sich der Fehler in solchen Details!'
    },
    'inactive': {
        'en': 'This account is inactive.',
        'de': 'Ihr Konto ist momentan deaktiviert. Bitte kontaktieren Sie uns, wenn Sie Hilfe benötigen.'
    },
    'password_mismatch': {
        'en': "The two password fields didn't match.",
        'de': 'Die beiden Passwörter stimmen nicht überein. Bitte versuchen Sie es noch einmal.'
    },
    'password_too_short': {
        'en': 'This password is too short. It must contain at least 8 characters.',
        'de': 'Das Passwort ist zu kurz. Es sollte mindestens 8 Zeichen enthalten.'
    },
    'password_too_common': {
        'en': 'This password is too common.',
        'de': 'Dieses Passwort ist zu häufig. Bitte wählen Sie ein sichereres Passwort.'
    },
    'password_entirely_numeric': {
        'en': "This password is entirely numeric.",
        'de': 'Das Passwort besteht nur aus Zahlen. Bitte verwenden Sie auch Buchstaben für mehr Sicherheit.'
    },
    'username_exists': {
        'en': 'A user with that username already exists.',
        'de': 'Dieser Benutzername ist leider schon vergeben. Wie wäre es mit einer kleinen Variation?'
    }
}

# Freundliche Willkommensnachrichten
WELCOME_MESSAGES = {
    'login_success': 'Willkommen zurück! 😊 Schön, dass Sie wieder da sind.',
    'logout_success': 'Sie wurden erfolgreich abgemeldet. Bis zum nächsten Mal! 👋',
    'register_success': 'Herzlich willkommen! 🎉 Ihr Konto wurde erfolgreich erstellt.',
    'password_changed': 'Super! Ihr Passwort wurde erfolgreich geändert. 🔐',
    'profile_updated': 'Ihre Profildaten wurden erfolgreich aktualisiert. ✅'
}