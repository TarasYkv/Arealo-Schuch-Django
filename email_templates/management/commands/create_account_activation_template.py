from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate, EmailTemplateCategory


class Command(BaseCommand):
    help = 'Create account activation email template'

    def handle(self, *args, **options):
        # Create or get category
        category, created = EmailTemplateCategory.objects.get_or_create(
            slug='authentication',
            defaults={
                'name': 'Authentifizierung',
                'description': 'E-Mail-Vorlagen für Benutzer-Authentifizierung',
                'icon': 'fas fa-user-lock',
                'order': 1
            }
        )
        
        # Create the template
        template, created = EmailTemplate.objects.get_or_create(
            template_type='account_activation',
            defaults={
                'name': 'Account-Aktivierung',
                'slug': 'account-activation-default',
                'category': category,
                'subject': 'Willkommen bei Workloom - E-Mail-Adresse bestätigen',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Mail-Adresse bestätigen - Workloom</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f8fafc; }
        .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; }
        .header h1 { color: #ffffff; margin: 0; font-size: 28px; font-weight: bold; }
        .content { padding: 40px 30px; }
        .welcome { font-size: 24px; color: #1a202c; margin-bottom: 20px; font-weight: 600; }
        .text { font-size: 16px; color: #4a5568; line-height: 1.6; margin-bottom: 30px; }
        .button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: 600; margin: 20px 0; }
        .button:hover { opacity: 0.9; }
        .features { background-color: #f7fafc; padding: 20px; border-radius: 8px; margin: 30px 0; }
        .features h3 { color: #2d3748; margin-top: 0; }
        .features ul { color: #4a5568; margin: 0; padding-left: 20px; }
        .features li { margin-bottom: 8px; }
        .footer { background-color: #edf2f7; padding: 30px; text-align: center; color: #718096; font-size: 14px; }
        .alternative-link { background-color: #f7fafc; padding: 20px; border-radius: 8px; margin-top: 30px; }
        .alternative-link p { margin: 0; font-size: 14px; color: #718096; }
        .alternative-link a { color: #667eea; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Workloom</h1>
        </div>
        
        <div class="content">
            <h2 class="welcome">Hallo {{user_name}}!</h2>
            
            <p class="text">
                Vielen Dank für Ihre Registrierung bei Workloom! Um Ihr Konto zu aktivieren und loszulegen, 
                bestätigen Sie bitte Ihre E-Mail-Adresse durch einen Klick auf den Button unten.
            </p>
            
            <div style="text-align: center;">
                <a href="{{verification_url}}" class="button">
                    ✅ E-Mail-Adresse bestätigen
                </a>
            </div>
            
            <div class="features">
                <h3>🎯 Was Sie mit Workloom erwartet:</h3>
                <ul>
                    <li><strong>E-Mail-Management:</strong> Professionelle E-Mail-Verwaltung und -Templates</li>
                    <li><strong>Organisation:</strong> Notizen, Ideenboards und Terminplanung</li>
                    <li><strong>Shopify-Integration:</strong> Nahtlose E-Commerce-Verwaltung</li>
                    <li><strong>Video-Hosting:</strong> Sichere Videoplattform für Ihr Business</li>
                    <li><strong>Team-Collaboration:</strong> Chat und gemeinsame Projektarbeit</li>
                </ul>
            </div>
            
            <p class="text">
                <strong>Wichtig:</strong> Dieser Bestätigungslink ist aus Sicherheitsgründen nur 24 Stunden gültig. 
                Falls Sie sich nicht bei Workloom registriert haben, können Sie diese E-Mail ignorieren.
            </p>
            
            <div class="alternative-link">
                <p>
                    Falls der Button nicht funktioniert, kopieren Sie diesen Link in Ihren Browser:<br>
                    <a href="{{verification_url}}">{{verification_url}}</a>
                </p>
            </div>
        </div>
        
        <div class="footer">
            <p>
                <strong>Workloom</strong> - Ihre All-in-One Business-Plattform<br>
                {{domain}} | Diese E-Mail wurde automatisch generiert.
            </p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hallo {{user_name}}!

Vielen Dank für Ihre Registrierung bei Workloom!

Um Ihr Konto zu aktivieren, bestätigen Sie bitte Ihre E-Mail-Adresse durch einen Klick auf den folgenden Link:

{{verification_url}}

Was Sie mit Workloom erwartet:
• E-Mail-Management: Professionelle E-Mail-Verwaltung und -Templates
• Organisation: Notizen, Ideenboards und Terminplanung  
• Shopify-Integration: Nahtlose E-Commerce-Verwaltung
• Video-Hosting: Sichere Videoplattform für Ihr Business
• Team-Collaboration: Chat und gemeinsame Projektarbeit

WICHTIG: Dieser Bestätigungslink ist aus Sicherheitsgründen nur 24 Stunden gültig.

Falls Sie sich nicht bei Workloom registriert haben, können Sie diese E-Mail ignorieren.

---
Workloom - Ihre All-in-One Business-Plattform
{{domain}}

Diese E-Mail wurde automatisch generiert.''',
                'available_variables': {
                    'user_name': 'Name des Benutzers',
                    'verification_url': 'Link zur E-Mail-Bestätigung',
                    'domain': 'Domain der Website'
                },
                'is_active': True,
                'is_default': True,
                'use_base_template': False  # Template hat bereits eigenes Design
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Account-Aktivierung Template erfolgreich erstellt: {template.name}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Account-Aktivierung Template existiert bereits: {template.name}'
                )
            )