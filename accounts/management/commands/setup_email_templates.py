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
        self.stdout.write(self.style.WARNING(
            '\n⚠️  WICHTIG: Vergessen Sie nicht, die E-Mail-Konfiguration '
            'auf PythonAnywhere einzurichten (EMAIL_HOST_PASSWORD, etc.)'
        ))