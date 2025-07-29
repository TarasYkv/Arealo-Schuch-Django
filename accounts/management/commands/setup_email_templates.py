from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate, EmailTemplateCategory
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Erstellt die Standard E-Mail-Templates für die Registrierung und Verifizierung'

    def handle(self, *args, **options):
        # Erstelle Kategorie falls nicht vorhanden
        category, created = EmailTemplateCategory.objects.get_or_create(
            name="System",
            defaults={
                'description': 'System E-Mail Templates',
                'order': 1
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ System-Kategorie erstellt'))
        
        # Erstelle Welcome/Verification Template
        welcome_template, created = EmailTemplate.objects.get_or_create(
            slug='welcome-verification',
            defaults={
                'name': 'Willkommen & E-Mail Verifizierung',
                'category': category,
                'template_type': 'account_activation',
                'subject': 'Willkommen bei Workloom - Bitte bestätigen Sie Ihre E-Mail',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Willkommen bei Workloom - E-Mail bestätigen</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .logo {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .header-subtitle {
            font-size: 1.1em;
            opacity: 0.9;
        }
        .content {
            padding: 40px 30px;
        }
        .welcome-message {
            font-size: 1.2em;
            color: #333;
            margin-bottom: 20px;
        }
        .verification-button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 20px 0;
            transition: transform 0.2s ease;
        }
        .verification-button:hover {
            transform: translateY(-2px);
        }
        .alternative-link {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            word-break: break-all;
            font-family: monospace;
            font-size: 0.9em;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
        .features {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .features h3 {
            color: #495057;
            margin-bottom: 15px;
        }
        .feature-list {
            list-style: none;
            padding: 0;
        }
        .feature-list li {
            padding: 5px 0;
            color: #6c757d;
        }
        .feature-list li:before {
            content: "✓";
            color: #28a745;
            font-weight: bold;
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🚀 Workloom</div>
            <div class="header-subtitle">Ihre All-in-One Arbeitsplattform</div>
        </div>
        
        <div class="content">
            <h2>Willkommen, {{ user.username }}! 🎉</h2>
            
            <div class="welcome-message">
                Schön, dass Sie sich für Workloom entschieden haben! Um Ihr Konto zu aktivieren und alle Features nutzen zu können, bestätigen Sie bitte Ihre E-Mail-Adresse.
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ verification_url }}" class="verification-button">
                    E-Mail-Adresse bestätigen
                </a>
            </div>
            
            <div class="features">
                <h3>Was Sie mit Workloom alles machen können:</h3>
                <ul class="feature-list">
                    <li>Chat-System für direkte Kommunikation</li>
                    <li>Shopify-Integration für E-Commerce</li>
                    <li>PDF-Suche und KI-Zusammenfassungen</li>
                    <li>Video-Hosting für Ihre Projekte</li>
                    <li>Organisationstools: Notizen, Boards, Termine</li>
                    <li>Bildbearbeitung und vieles mehr</li>
                </ul>
            </div>
            
            <p><strong>Wichtig:</strong> Dieser Bestätigungslink ist 24 Stunden gültig. Falls der Button nicht funktioniert, kopieren Sie den folgenden Link in Ihren Browser:</p>
            
            <div class="alternative-link">
                {{ verification_url }}
            </div>
            
            <p>Falls Sie diese E-Mail irrtümlich erhalten haben, können Sie sie einfach ignorieren.</p>
        </div>
        
        <div class="footer">
            <p>© 2025 Workloom - Ihre All-in-One Arbeitsplattform</p>
            <p>Bei Fragen erreichen Sie uns unter: <a href="mailto:kontakt@workloom.de">kontakt@workloom.de</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Willkommen bei Workloom, {{ user.username }}!

Schön, dass Sie sich für Workloom entschieden haben! Um Ihr Konto zu aktivieren und alle Features nutzen zu können, bestätigen Sie bitte Ihre E-Mail-Adresse.

Bestätigungslink:
{{ verification_url }}

Was Sie mit Workloom alles machen können:
- Chat-System für direkte Kommunikation
- Shopify-Integration für E-Commerce
- PDF-Suche und KI-Zusammenfassungen
- Video-Hosting für Ihre Projekte
- Organisationstools: Notizen, Boards, Termine
- Bildbearbeitung und vieles mehr

Wichtig: Dieser Bestätigungslink ist 24 Stunden gültig.

Falls Sie diese E-Mail irrtümlich erhalten haben, können Sie sie einfach ignorieren.

© 2025 Workloom - Ihre All-in-One Arbeitsplattform
Bei Fragen erreichen Sie uns unter: kontakt@workloom.de''',
                'available_variables': {
                    'user': 'User object',
                    'verification_url': 'URL zur E-Mail-Verifizierung'
                },
                'is_active': True,
                'is_default': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Welcome/Verification E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Welcome/Verification Template existiert bereits'))
        
        # Erstelle Resend Verification Template
        resend_template, created = EmailTemplate.objects.get_or_create(
            slug='resend-verification',
            defaults={
                'name': 'E-Mail Verifizierung erneut senden',
                'category': category,
                'template_type': 'account_activation',
                'subject': 'E-Mail-Adresse bestätigen - Workloom',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Mail bestätigen</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .verification-button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 20px 0;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>E-Mail-Adresse bestätigen</h1>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <p>Sie haben eine neue E-Mail-Bestätigung angefordert. Bitte klicken Sie auf den folgenden Link, um Ihre E-Mail-Adresse zu bestätigen:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ verification_url }}" class="verification-button">
                    E-Mail-Adresse bestätigen
                </a>
            </div>
            
            <p>Oder kopieren Sie diesen Link in Ihren Browser:</p>
            <p style="word-break: break-all; background: #f8f9fa; padding: 10px; border-radius: 5px;">
                {{ verification_url }}
            </p>
            
            <p><strong>Hinweis:</strong> Dieser Link ist 24 Stunden gültig.</p>
        </div>
        
        <div class="footer">
            <p>© 2025 Workloom</p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Sie haben eine neue E-Mail-Bestätigung angefordert. Bitte klicken Sie auf den folgenden Link, um Ihre E-Mail-Adresse zu bestätigen:

{{ verification_url }}

Hinweis: Dieser Link ist 24 Stunden gültig.

© 2025 Workloom''',
                'available_variables': {
                    'user': 'User object',
                    'verification_url': 'URL zur E-Mail-Verifizierung'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Resend Verification E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Resend Verification Template existiert bereits'))
        
        # Zeige Zusammenfassung
        total_templates = EmailTemplate.objects.count()
        active_templates = EmailTemplate.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\n📊 E-Mail Templates Status:')
        self.stdout.write(f'Gesamt: {total_templates}')
        self.stdout.write(f'Aktiv: {active_templates}')
        self.stdout.write(f'\n✅ E-Mail Templates sind bereit!')
        # Erstelle Passwort Reset Template
        password_reset_template, created = EmailTemplate.objects.get_or_create(
            slug='password-reset',
            defaults={
                'name': 'Passwort zurücksetzen',
                'category': category,
                'template_type': 'password_reset',
                'subject': 'Passwort zurücksetzen - Workloom',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Passwort zurücksetzen</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .reset-button {
            display: inline-block;
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 20px 0;
        }
        .warning-box {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            color: #856404;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Passwort zurücksetzen</h1>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <p>Sie haben angefordert, Ihr Passwort bei Workloom zurückzusetzen. Klicken Sie auf den folgenden Button, um ein neues Passwort zu erstellen:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ reset_url }}" class="reset-button">
                    Neues Passwort erstellen
                </a>
            </div>
            
            <div class="warning-box">
                <strong>⚠️ Sicherheitshinweis:</strong><br>
                Dieser Link ist aus Sicherheitsgründen nur 24 Stunden gültig. Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail bitte.
            </div>
            
            <p>Falls der Button nicht funktioniert, kopieren Sie den folgenden Link in Ihren Browser:</p>
            <p style="word-break: break-all; background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.9em;">
                {{ reset_url }}
            </p>
        </div>
        
        <div class="footer">
            <p>© 2025 Workloom - Ihre Sicherheit ist uns wichtig</p>
            <p>Bei Fragen erreichen Sie uns unter: <a href="mailto:kontakt@workloom.de">kontakt@workloom.de</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Sie haben angefordert, Ihr Passwort bei Workloom zurückzusetzen.

Klicken Sie auf den folgenden Link, um ein neues Passwort zu erstellen:
{{ reset_url }}

Sicherheitshinweis: Dieser Link ist aus Sicherheitsgründen nur 24 Stunden gültig.
Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail bitte.

© 2025 Workloom
Bei Fragen: kontakt@workloom.de''',
                'available_variables': {
                    'user': 'User object',
                    'reset_url': 'URL zum Passwort zurücksetzen'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Password Reset E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Password Reset Template existiert bereits'))
        
        # Erstelle Subscription Upgrade Template
        subscription_template, created = EmailTemplate.objects.get_or_create(
            slug='subscription-upgrade',
            defaults={
                'name': 'Abonnement-Upgrade Bestätigung',
                'category': category,
                'template_type': 'custom',
                'subject': '🎉 Willkommen im {{ plan_name }} Plan - Workloom',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Abonnement-Upgrade</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .feature-box {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .feature-list {
            list-style: none;
            padding: 0;
        }
        .feature-list li {
            padding: 8px 0;
            color: #495057;
        }
        .feature-list li:before {
            content: "✨";
            margin-right: 10px;
        }
        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 20px 0;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Herzlichen Glückwunsch!</h1>
            <p style="font-size: 1.2em; margin-top: 10px;">Sie sind jetzt {{ plan_name }} Mitglied</p>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <p>Vielen Dank für Ihr Upgrade auf den <strong>{{ plan_name }}</strong> Plan! Sie haben jetzt Zugriff auf alle Premium-Features von Workloom.</p>
            
            <div class="feature-box">
                <h3>Ihre neuen Features:</h3>
                <ul class="feature-list">
                    {{ features_list|safe }}
                </ul>
            </div>
            
            <p><strong>Abonnement-Details:</strong></p>
            <ul style="list-style: none; padding-left: 0;">
                <li>📅 Start: {{ start_date }}</li>
                <li>💳 Preis: {{ price }} pro {{ billing_period }}</li>
                <li>🔄 Nächste Abrechnung: {{ next_billing_date }}</li>
            </ul>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ dashboard_url }}" class="cta-button">
                    Jetzt Premium-Features nutzen
                </a>
            </div>
            
            <p style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 4px solid #4caf50;">
                💡 <strong>Tipp:</strong> Besuchen Sie unser <a href="{{ help_url }}">Hilfecenter</a>, um das Beste aus Ihrem {{ plan_name }} Plan herauszuholen.
            </p>
        </div>
        
        <div class="footer">
            <p>Vielen Dank für Ihr Vertrauen in Workloom!</p>
            <p>Bei Fragen zu Ihrem Abonnement: <a href="mailto:billing@workloom.de">billing@workloom.de</a></p>
            <p><a href="{{ manage_subscription_url }}">Abonnement verwalten</a> | <a href="{{ invoice_url }}">Rechnung herunterladen</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Herzlichen Glückwunsch! Sie sind jetzt {{ plan_name }} Mitglied.

Vielen Dank für Ihr Upgrade! Sie haben jetzt Zugriff auf alle Premium-Features von Workloom.

Ihre neuen Features:
{{ features_list_text }}

Abonnement-Details:
- Start: {{ start_date }}
- Preis: {{ price }} pro {{ billing_period }}
- Nächste Abrechnung: {{ next_billing_date }}

Nutzen Sie jetzt Ihre Premium-Features: {{ dashboard_url }}

Tipp: Besuchen Sie unser Hilfecenter, um das Beste aus Ihrem {{ plan_name }} Plan herauszuholen.

Vielen Dank für Ihr Vertrauen in Workloom!
Bei Fragen zu Ihrem Abonnement: billing@workloom.de

Abonnement verwalten: {{ manage_subscription_url }}
Rechnung herunterladen: {{ invoice_url }}''',
                'available_variables': {
                    'user': 'User object',
                    'plan_name': 'Name des Abonnements',
                    'features_list': 'HTML-Liste der Features',
                    'features_list_text': 'Text-Liste der Features',
                    'start_date': 'Startdatum des Abonnements',
                    'price': 'Preis',
                    'billing_period': 'Monat/Jahr',
                    'next_billing_date': 'Nächstes Abrechnungsdatum',
                    'dashboard_url': 'URL zum Dashboard',
                    'help_url': 'URL zum Hilfecenter',
                    'manage_subscription_url': 'URL zur Abonnement-Verwaltung',
                    'invoice_url': 'URL zur Rechnung'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Subscription Upgrade E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Subscription Upgrade Template existiert bereits'))
        
        # Erstelle Storage Warning Template
        storage_warning_template, created = EmailTemplate.objects.get_or_create(
            slug='storage-warning',
            defaults={
                'name': 'Speicherplatz-Warnung',
                'category': category,
                'template_type': 'custom',
                'subject': '⚠️ Speicherplatz fast voll - Workloom',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speicherplatz-Warnung</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #fa8231 0%, #fd4849 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .storage-bar {
            background-color: #e9ecef;
            border-radius: 10px;
            height: 30px;
            margin: 20px 0;
            overflow: hidden;
            position: relative;
        }
        .storage-fill {
            background: linear-gradient(135deg, #fa8231 0%, #fd4849 100%);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        .action-button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 12px 25px;
            border-radius: 25px;
            font-weight: bold;
            margin: 10px 5px;
        }
        .tips-box {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Speicherplatz-Warnung</h1>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <p>Ihr Speicherplatz bei Workloom ist fast aufgebraucht. Sie nutzen derzeit <strong>{{ storage_used_percent }}%</strong> Ihres verfügbaren Speicherplatzes.</p>
            
            <div class="storage-bar">
                <div class="storage-fill" style="width: {{ storage_used_percent }}%;">
                    {{ storage_used_percent }}%
                </div>
            </div>
            
            <p><strong>Speicherplatz-Details:</strong></p>
            <ul>
                <li>Verwendet: {{ storage_used }} von {{ storage_total }}</li>
                <li>Verfügbar: {{ storage_remaining }}</li>
            </ul>
            
            <div class="tips-box">
                <h3>💡 Was können Sie tun?</h3>
                <ul style="list-style: none; padding-left: 0;">
                    <li>🗑️ Löschen Sie nicht mehr benötigte Dateien</li>
                    <li>📦 Archivieren Sie alte Projekte</li>
                    <li>🚀 Upgraden Sie auf mehr Speicherplatz</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ manage_storage_url }}" class="action-button">
                    Speicherplatz verwalten
                </a>
                <a href="{{ upgrade_url }}" class="action-button" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                    Mehr Speicherplatz
                </a>
            </div>
            
            <p style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                <strong>Hinweis:</strong> Bei {{ warning_threshold }}% werden neue Uploads eingeschränkt, um Datenverlust zu vermeiden.
            </p>
        </div>
        
        <div class="footer">
            <p>© 2025 Workloom - Ihr digitaler Arbeitsplatz</p>
            <p>Speicherplatz-Support: <a href="mailto:support@workloom.de">support@workloom.de</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Ihr Speicherplatz bei Workloom ist fast aufgebraucht.
Sie nutzen derzeit {{ storage_used_percent }}% Ihres verfügbaren Speicherplatzes.

Speicherplatz-Details:
- Verwendet: {{ storage_used }} von {{ storage_total }}
- Verfügbar: {{ storage_remaining }}

Was können Sie tun?
- Löschen Sie nicht mehr benötigte Dateien
- Archivieren Sie alte Projekte
- Upgraden Sie auf mehr Speicherplatz

Speicherplatz verwalten: {{ manage_storage_url }}
Mehr Speicherplatz: {{ upgrade_url }}

Hinweis: Bei {{ warning_threshold }}% werden neue Uploads eingeschränkt.

© 2025 Workloom
Support: support@workloom.de''',
                'available_variables': {
                    'user': 'User object',
                    'storage_used': 'Genutzter Speicherplatz',
                    'storage_total': 'Gesamter Speicherplatz',
                    'storage_remaining': 'Verbleibender Speicherplatz',
                    'storage_used_percent': 'Genutzter Speicherplatz in Prozent',
                    'warning_threshold': 'Warnschwelle in Prozent',
                    'manage_storage_url': 'URL zur Speicherverwaltung',
                    'upgrade_url': 'URL zum Upgrade'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Storage Warning E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Storage Warning Template existiert bereits'))
        
        # Erstelle Payment Failed Template
        payment_failed_template, created = EmailTemplate.objects.get_or_create(
            slug='payment-failed',
            defaults={
                'name': 'Zahlung fehlgeschlagen',
                'category': category,
                'template_type': 'custom',
                'subject': '❗ Zahlungsproblem bei Ihrem Workloom-Abonnement',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zahlung fehlgeschlagen</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: linear-gradient(135deg, #ee5a6f 0%, #f47068 100%);
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .alert-box {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            color: #721c24;
        }
        .action-button {
            display: inline-block;
            background: #28a745;
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.1em;
            margin: 20px 0;
        }
        .info-box {
            background-color: #cfe2ff;
            border: 1px solid #b6d4fe;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            color: #084298;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>❗ Zahlungsproblem</h1>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <div class="alert-box">
                <strong>Wichtig:</strong> Die Zahlung für Ihr Workloom-Abonnement konnte nicht verarbeitet werden.
            </div>
            
            <p><strong>Details:</strong></p>
            <ul>
                <li>Abonnement: {{ plan_name }}</li>
                <li>Betrag: {{ amount }}</li>
                <li>Zahlungsmethode: {{ payment_method }}</li>
                <li>Fehlgeschlagen am: {{ failed_date }}</li>
            </ul>
            
            <p>Um eine Unterbrechung Ihres Services zu vermeiden, aktualisieren Sie bitte Ihre Zahlungsinformationen innerhalb der nächsten <strong>{{ grace_period_days }} Tage</strong>.</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ update_payment_url }}" class="action-button">
                    Zahlungsmethode aktualisieren
                </a>
            </div>
            
            <div class="info-box">
                <strong>Was passiert als nächstes?</strong><br>
                Wir werden in {{ retry_days }} Tagen erneut versuchen, die Zahlung zu verarbeiten. Falls die Zahlung weiterhin fehlschlägt, wird Ihr Abonnement pausiert.
            </div>
            
            <p>Häufige Gründe für fehlgeschlagene Zahlungen:</p>
            <ul>
                <li>Unzureichende Deckung</li>
                <li>Abgelaufene Kreditkarte</li>
                <li>Geänderte Kartennummer</li>
                <li>Zahlungslimit erreicht</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>Bei Fragen zur Abrechnung: <a href="mailto:billing@workloom.de">billing@workloom.de</a></p>
            <p><a href="{{ subscription_url }}">Abonnement verwalten</a> | <a href="{{ help_url }}">Hilfe</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Wichtig: Die Zahlung für Ihr Workloom-Abonnement konnte nicht verarbeitet werden.

Details:
- Abonnement: {{ plan_name }}
- Betrag: {{ amount }}
- Zahlungsmethode: {{ payment_method }}
- Fehlgeschlagen am: {{ failed_date }}

Um eine Unterbrechung Ihres Services zu vermeiden, aktualisieren Sie bitte Ihre Zahlungsinformationen innerhalb der nächsten {{ grace_period_days }} Tage.

Zahlungsmethode aktualisieren: {{ update_payment_url }}

Was passiert als nächstes?
Wir werden in {{ retry_days }} Tagen erneut versuchen, die Zahlung zu verarbeiten.

Häufige Gründe für fehlgeschlagene Zahlungen:
- Unzureichende Deckung
- Abgelaufene Kreditkarte
- Geänderte Kartennummer
- Zahlungslimit erreicht

Bei Fragen: billing@workloom.de
Abonnement verwalten: {{ subscription_url }}''',
                'available_variables': {
                    'user': 'User object',
                    'plan_name': 'Name des Abonnements',
                    'amount': 'Zahlungsbetrag',
                    'payment_method': 'Zahlungsmethode',
                    'failed_date': 'Datum der fehlgeschlagenen Zahlung',
                    'grace_period_days': 'Tage bis zur Pausierung',
                    'retry_days': 'Tage bis zum nächsten Versuch',
                    'update_payment_url': 'URL zur Zahlungsaktualisierung',
                    'subscription_url': 'URL zur Abonnement-Verwaltung',
                    'help_url': 'URL zum Hilfecenter'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Payment Failed E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Payment Failed Template existiert bereits'))
        
        # Erstelle Account Deletion Warning Template
        deletion_warning_template, created = EmailTemplate.objects.get_or_create(
            slug='account-deletion-warning',
            defaults={
                'name': 'Konto-Löschwarnung',
                'category': category,
                'template_type': 'custom',
                'subject': '⚠️ Ihr Workloom-Konto wird in {{ days_remaining }} Tagen gelöscht',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Konto-Löschwarnung</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }
        .header {
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 40px 20px;
        }
        .content {
            padding: 40px 30px;
        }
        .warning-box {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 20px;
            margin: 20px 0;
            color: #856404;
            text-align: center;
        }
        .countdown {
            font-size: 2.5em;
            font-weight: bold;
            color: #e74c3c;
            margin: 10px 0;
        }
        .reactivate-button {
            display: inline-block;
            background: #27ae60;
            color: white;
            text-decoration: none;
            padding: 15px 40px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 1.2em;
            margin: 20px 0;
        }
        .data-box {
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .footer {
            background-color: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            font-size: 0.9em;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Wichtige Mitteilung zu Ihrem Konto</h1>
        </div>
        
        <div class="content">
            <p>Hallo {{ user.username }},</p>
            
            <div class="warning-box">
                <p style="margin: 0;">Ihr Workloom-Konto ist seit {{ inactive_days }} Tagen inaktiv.</p>
                <div class="countdown">{{ days_remaining }}</div>
                <p style="margin: 0;">Tage bis zur automatischen Löschung</p>
            </div>
            
            <p>Gemäß unseren Nutzungsbedingungen werden inaktive Konten nach {{ total_inactive_days }} Tagen automatisch gelöscht, um die Sicherheit und Privatsphäre unserer Nutzer zu gewährleisten.</p>
            
            <div class="data-box">
                <h3>Was wird gelöscht?</h3>
                <ul>
                    <li>Alle Ihre hochgeladenen Dateien und Videos</li>
                    <li>Ihre Projekte und Notizen</li>
                    <li>Chat-Verläufe und Nachrichten</li>
                    <li>Persönliche Einstellungen und Konfigurationen</li>
                    <li>Alle anderen mit Ihrem Konto verbundenen Daten</li>
                </ul>
            </div>
            
            <p style="text-align: center; font-size: 1.1em;"><strong>Möchten Sie Ihr Konto behalten?</strong></p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ reactivate_url }}" class="reactivate-button">
                    Konto reaktivieren
                </a>
            </div>
            
            <p style="text-align: center; color: #7f8c8d;">Ein einfacher Login genügt, um Ihr Konto zu reaktivieren.</p>
            
            <div style="background-color: #e8f8f5; padding: 15px; border-radius: 5px; border-left: 4px solid #27ae60; margin-top: 30px;">
                <strong>💡 Tipp:</strong> Sie können Ihre Daten vor der Löschung <a href="{{ export_url }}">exportieren</a>.
            </div>
        </div>
        
        <div class="footer">
            <p>Wir hoffen, Sie bald wieder bei Workloom begrüßen zu dürfen!</p>
            <p>Bei Fragen: <a href="mailto:support@workloom.de">support@workloom.de</a></p>
            <p><small>Diese E-Mail wurde automatisch generiert. Sie erhalten diese Nachricht, weil Sie ein Konto bei Workloom haben.</small></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{ user.username }},

Wichtige Mitteilung zu Ihrem Konto:

Ihr Workloom-Konto ist seit {{ inactive_days }} Tagen inaktiv.
Es wird in {{ days_remaining }} Tagen automatisch gelöscht.

Gemäß unseren Nutzungsbedingungen werden inaktive Konten nach {{ total_inactive_days }} Tagen automatisch gelöscht.

Was wird gelöscht?
- Alle Ihre hochgeladenen Dateien und Videos
- Ihre Projekte und Notizen
- Chat-Verläufe und Nachrichten
- Persönliche Einstellungen
- Alle anderen Kontodaten

Möchten Sie Ihr Konto behalten?
Konto reaktivieren: {{ reactivate_url }}

Ein einfacher Login genügt zur Reaktivierung.

Tipp: Sie können Ihre Daten exportieren: {{ export_url }}

Wir hoffen, Sie bald wieder bei Workloom begrüßen zu dürfen!
Bei Fragen: support@workloom.de''',
                'available_variables': {
                    'user': 'User object',
                    'inactive_days': 'Tage seit letzter Aktivität',
                    'days_remaining': 'Verbleibende Tage',
                    'total_inactive_days': 'Gesamte Inaktivitätsperiode',
                    'reactivate_url': 'URL zur Reaktivierung',
                    'export_url': 'URL zum Datenexport'
                },
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Account Deletion Warning E-Mail Template erstellt'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Account Deletion Warning Template existiert bereits'))
        
        # Zeige finale Zusammenfassung
        total_templates = EmailTemplate.objects.count()
        active_templates = EmailTemplate.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\n📊 E-Mail Templates Status:')
        self.stdout.write(f'Gesamt: {total_templates}')
        self.stdout.write(f'Aktiv: {active_templates}')
        self.stdout.write(f'\n✅ Alle E-Mail Templates wurden erfolgreich erstellt!')
        
        self.stdout.write(self.style.SUCCESS('\n📧 Folgende E-Mail-Templates sind jetzt verfügbar:'))
        self.stdout.write('- Willkommen & E-Mail Verifizierung')
        self.stdout.write('- E-Mail Verifizierung erneut senden')
        self.stdout.write('- Passwort zurücksetzen')
        self.stdout.write('- Abonnement-Upgrade Bestätigung')
        self.stdout.write('- Speicherplatz-Warnung')
        self.stdout.write('- Zahlung fehlgeschlagen')
        self.stdout.write('- Konto-Löschwarnung')
        
        self.stdout.write(self.style.WARNING(
            '\n⚠️  WICHTIG: Vergessen Sie nicht, die E-Mail-Konfiguration '
            'auf PythonAnywhere einzurichten (EMAIL_HOST_PASSWORD, etc.)'
        ))