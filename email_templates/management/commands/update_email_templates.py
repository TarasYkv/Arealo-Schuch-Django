from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate


class Command(BaseCommand):
    help = 'Update email templates with corrected content'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Updating email templates...'))

        # 1. Update Registration Email
        try:
            reg_template = EmailTemplate.objects.get(template_type='user_registration', is_default=True)

            # Setze Slug falls leer
            if not reg_template.slug:
                from django.utils.text import slugify
                reg_template.slug = slugify(reg_template.name)
                self.stdout.write(self.style.WARNING(f'Set slug: {reg_template.slug}'))
            reg_template.subject = 'Willkommen bei Workloom - E-Mail bestätigen ERFORDERLICH'
            reg_template.html_content = '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Mail-Bestätigung erforderlich - Workloom</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }
        .container {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #4a90e2;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #4a90e2;
            margin-bottom: 10px;
        }
        .welcome-title {
            color: #2c3e50;
            font-size: 24px;
            margin: 20px 0;
            text-align: center;
        }
        .important-notice {
            background-color: #fff3cd;
            border: 2px solid #ffc107;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }
        .important-notice h3 {
            color: #856404;
            margin: 0 0 15px 0;
            font-size: 18px;
        }
        .important-notice p {
            color: #856404;
            margin: 10px 0;
            font-weight: bold;
        }
        .highlight {
            background-color: #e8f4fd;
            padding: 20px;
            border-left: 4px solid #4a90e2;
            margin: 20px 0;
            border-radius: 5px;
        }
        .btn {
            display: inline-block;
            background-color: #28a745;
            color: white;
            padding: 18px 40px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            text-align: center;
            border: none;
        }
        .btn:hover {
            background-color: #218838;
        }
        .features {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .features h3 {
            color: #4a90e2;
            margin-bottom: 15px;
        }
        .features ul {
            list-style-type: none;
            padding: 0;
        }
        .features li {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .features li:before {
            content: "✓ ";
            color: #28a745;
            font-weight: bold;
            margin-right: 10px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 14px;
        }
        .social-links {
            margin: 20px 0;
        }
        .social-links a {
            color: #4a90e2;
            text-decoration: none;
            margin: 0 10px;
        }
        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }
            .welcome-title {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🔐 Workloom</div>
            <p>E-Mail-Bestätigung erforderlich</p>
        </div>

        <h1 class="welcome-title">Willkommen bei Workloom, {{ user_name }}!</h1>

        <div class="important-notice">
            <h3>⚠️ WICHTIG: E-Mail-Bestätigung erforderlich</h3>
            <p>Sie MÜSSEN Ihre E-Mail-Adresse bestätigen, um Ihr Konto zu aktivieren!</p>
            <p>Ohne Bestätigung können Sie sich nicht anmelden und haben keinen Zugriff auf Workloom.</p>
        </div>

        <div class="highlight">
            <p><strong>Vielen Dank für Ihre Registrierung!</strong></p>
            <p>Ihre Registrierung bei Workloom war erfolgreich, aber Ihr Konto ist noch <strong>nicht aktiviert</strong>.</p>
            <p>Um die Aktivierung abzuschließen, müssen Sie unbedingt auf den Bestätigungs-Button klicken:</p>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ activation_url }}" class="btn">✅ E-MAIL JETZT BESTÄTIGEN</a>
        </div>

        <div class="important-notice">
            <p>❗ Dieser Link ist nur begrenzt gültig - bestätigen Sie Ihre E-Mail bitte umgehend!</p>
        </div>

        <div class="features">
            <h3>🚀 Was Sie nach der Bestätigung erwartet:</h3>
            <ul>
                <li><strong>Chat-System:</strong> Direkte Kommunikation mit Kollegen und Kunden</li>
                <li><strong>Shopify-Integration:</strong> Nahtlose E-Commerce-Lösungen</li>
                <li><strong>PDF-Suche & KI:</strong> Intelligente Dokumentenanalyse und Zusammenfassungen</li>
                <li><strong>Video-Hosting:</strong> Professionelle Präsentation Ihrer Projekte</li>
                <li><strong>Organisationstools:</strong> Notizen, Boards und Terminplanung</li>
                <li><strong>Amortisationsrechner:</strong> Finanzanalysen und Kalkulationen</li>
                <li><strong>Statistiken & Analytics:</strong> Datengetriebene Entscheidungen</li>
                <li><strong>Sichere Dateifreigabe:</strong> Verschlüsselter Transfer und Sharing</li>
            </ul>
        </div>

        <div class="highlight">
            <h3>🎯 Probleme beim Bestätigen?</h3>
            <p>Falls der Button nicht funktioniert, kopieren Sie bitte diesen Link in Ihren Browser:</p>
            <p style="word-break: break-all; background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace;">{{ activation_url }}</p>
        </div>

        <div class="footer">
            <p><strong>{{ site_name }} Team</strong></p>
            <p>Ihre moderne Arbeitsplattform für effiziente Zusammenarbeit</p>

            <div class="social-links">
                <a href="mailto:kontakt@workloom.de">Support kontaktieren</a>
            </div>

            <p style="font-size: 12px; color: #999; margin-top: 20px;">
                Diese E-Mail wurde automatisch generiert. Falls Sie sich nicht bei Workloom registriert haben, ignorieren Sie diese E-Mail.<br>
                © {{ current_year }} {{ site_name }}. Alle Rechte vorbehalten.
            </p>
        </div>
    </div>
</body>
</html>'''
            # Update auch den Text-Inhalt
            reg_template.text_content = '''Willkommen bei {{ site_name }}, {{ user_name }}!

WICHTIG: E-Mail-Bestätigung erforderlich.

Du musst deine E-Mail-Adresse bestätigen, um dein Konto zu aktivieren.
Ohne Bestätigung kannst du dich nicht anmelden und hast keinen Zugriff auf Workloom.

Vielen Dank für deine Registrierung!
Deine Anmeldung war erfolgreich, aber dein Konto ist noch nicht aktiviert.

Bestätige deine E-Mail über diesen Link:
{{ activation_url }}

Der Link ist nur begrenzt gültig. Bitte bestätige deine Adresse zeitnah.

Was dich nach der Bestätigung erwartet:
- Chat-System: Direkte Kommunikation mit Kollegen und Kunden
- Shopify-Integration: Nahtlose E-Commerce-Lösungen
- PDF-Suche und KI: Intelligente Dokumentenanalyse und Zusammenfassungen
- Video-Hosting: Professionelle Präsentation deiner Projekte
- Organisationstools: Notizen, Boards und Terminplanung
- Amortisationsrechner: Finanzanalysen und Kalkulationen
- Statistiken und Analytics: Datengetriebene Entscheidungen
- Sichere Dateifreigabe: Verschlüsselter Transfer und Sharing

Probleme beim Bestätigen? Kopiere den Link in deinen Browser:
{{ activation_url }}

{{ site_name }} Team
Support: kontakt@workloom.de
© {{ current_year }} {{ site_name }}. Alle Rechte vorbehalten.'''

            
            reg_template.available_variables = {
                'user_name': 'Name des Benutzers',
                'activation_url': 'Aktivierungslink zur Bestätigung',
                'site_name': 'Name der Plattform',
                'current_year': 'Aktuelles Jahr'
            }
            reg_template.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Updated registration email (HTML + Text): {reg_template.name}'))
        except EmailTemplate.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Registration email template not found'))

        # 2. Create or update Welcome Email
        welcome_template, created = EmailTemplate.objects.get_or_create(
            slug='welcome-account-activated',
            defaults={
                'name': 'Willkommen im Dashboard - Konto aktiviert',
                'template_type': 'welcome',
                'subject': '🎉 Konto aktiviert - Willkommen bei {{ site_name }}!',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Willkommen bei Workloom - Ihr Konto ist aktiviert!</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }
        .container {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #28a745;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #28a745;
            margin-bottom: 10px;
        }
        .success-title {
            color: #28a745;
            font-size: 24px;
            margin: 20px 0;
            text-align: center;
        }
        .success-notice {
            background-color: #d4edda;
            border: 2px solid #28a745;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }
        .success-notice h3 {
            color: #155724;
            margin: 0 0 15px 0;
            font-size: 18px;
        }
        .success-notice p {
            color: #155724;
            margin: 10px 0;
            font-weight: bold;
        }
        .btn {
            display: inline-block;
            background-color: #4a90e2;
            color: white;
            padding: 18px 40px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            text-align: center;
        }
        .quick-start {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin: 25px 0;
            text-align: center;
        }
        .quick-start h3 {
            margin: 0 0 15px 0;
            font-size: 20px;
        }
        .quick-start .btn {
            background-color: white;
            color: #667eea;
            font-weight: bold;
        }
        .features {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .features h3 {
            color: #4a90e2;
            margin-bottom: 15px;
        }
        .features ul {
            list-style-type: none;
            padding: 0;
        }
        .features li {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        .features li:before {
            content: "✓ ";
            color: #28a745;
            font-weight: bold;
            margin-right: 10px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 14px;
        }
        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }
            .success-title {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🎉 Workloom</div>
            <p>Ihr Konto ist aktiviert!</p>
        </div>

        <h1 class="success-title">Perfekt, {{ user_name }}!</h1>

        <div class="success-notice">
            <h3>✅ Ihr Konto wurde erfolgreich aktiviert!</h3>
            <p>Ihre E-Mail-Adresse ist bestätigt und Sie können nun alle Funktionen von Workloom nutzen.</p>
        </div>

        <div class="quick-start">
            <h3>🚀 Starten Sie jetzt durch!</h3>
            <p>Ihr persönliches Dashboard wartet auf Sie - entdecken Sie alle Möglichkeiten von Workloom.</p>
            <a href="{{ dashboard_url }}" class="btn">Zum Dashboard</a>
        </div>

        <div class="features">
            <h3>🎯 Ihre ersten Schritte:</h3>
            <ul>
                <li><strong>Dashboard erkunden:</strong> Verschaffen Sie sich einen Überblick über alle verfügbaren Tools</li>
                <li><strong>Profil vervollständigen:</strong> Fügen Sie weitere Informationen zu Ihrem Profil hinzu</li>
                <li><strong>Chat-System nutzen:</strong> Beginnen Sie die Kommunikation mit Kollegen und Kunden</li>
                <li><strong>Erstes Projekt anlegen:</strong> Nutzen Sie unsere Organisationstools für Ihre Projekte</li>
                <li><strong>Dateien hochladen:</strong> Teilen Sie Dokumente sicher mit Ihrem Team</li>
                <li><strong>Video-Hosting testen:</strong> Präsentieren Sie Ihre Ideen professionell</li>
                <li><strong>KI-Tools entdecken:</strong> Nutzen Sie unsere intelligenten Analysefunktionen</li>
                <li><strong>Einstellungen anpassen:</strong> Personalisieren Sie Workloom nach Ihren Bedürfnissen</li>
            </ul>
        </div>

        <div class="footer">
            <p><strong>{{ site_name }} Team</strong></p>
            <p>Ihre moderne Arbeitsplattform für effiziente Zusammenarbeit</p>
            <p style="font-size: 12px; color: #999; margin-top: 20px;">
                © {{ current_year }} {{ site_name }}. Alle Rechte vorbehalten.
            </p>
        </div>
    </div>
</body>
</html>''',
                'available_variables': 'user_name, dashboard_url, profile_url, site_name, current_year',
                'is_active': True,
                'is_default': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created welcome email: {welcome_template.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'ℹ️ Welcome email already exists: {welcome_template.name}'))


        text_updates = {
            'resend-verification': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "du hast eine neue E-Mail-Bestätigung für dein Workloom Konto angefordert.",
                    "Bitte bestätige deine Adresse, damit dein Zugang aktiv bleibt.",
                    "",
                    "Bestätigungslink:",
                    "{{ verification_url }}",
                    "",
                    "Der Link bleibt 24 Stunden gültig. Danach musst du eine neue Bestätigung anfordern.",
                    "",
                    "Wenn du diese Anfrage nicht gestellt hast, melde dich sofort beim Support unter kontakt@workloom.de.",
                    "",
                    "Bis gleich bei Workloom!",
                ]),
            },
            'password-reset': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "für dein Workloom Konto wurde eine Passwort-Zurücksetzung angefordert.",
                    "Lege jetzt ein neues Passwort fest:",
                    "",
                    "{{ reset_url }}",
                    "",
                    "Der Link läuft nach 60 Minuten ab.",
                    "",
                    "Warst du das nicht? Ignoriere diese Nachricht oder kontaktiere uns unter kontakt@workloom.de.",
                    "",
                    "Sicherheitstipps für dein Konto:",
                    "- Verwende ein starkes, einzigartiges Passwort.",
                    "- Teile deine Zugangsdaten niemals mit anderen.",
                    "- Aktiviere zusätzliche Sicherheitsfunktionen in deinem Profil.",
                    "",
                    "Dein Workloom Team",
                ]),
            },
            'subscription-upgrade': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "herzlichen Glückwunsch zum Upgrade auf den {{ plan_name }} Plan bei Workloom!",
                    "",
                    "Das ist jetzt neu für dich:",
                    "{{ features_list_text }}",
                    "",
                    "Deine Abonnementdaten:",
                    "- Startdatum: {{ start_date }}",
                    "- Preis: {{ price }} / {{ billing_period }}",
                    "- Nächste Abrechnung: {{ next_billing_date }}",
                    "",
                    "Wichtige Links:",
                    "- Dashboard: {{ dashboard_url }}",
                    "- Abonnement verwalten: {{ manage_subscription_url }}",
                    "- Rechnung herunterladen: {{ invoice_url }}",
                    "- Hilfe und Antworten: {{ help_url }}",
                    "",
                    "Viel Erfolg mit Workloom!",
                ]),
            },
            'storage-warning': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "dein Workloom Speicher ist fast voll. Du nutzt aktuell {{ storage_used_percent }} Prozent deines verfügbaren Speicherplatzes.",
                    "",
                    "Speicherübersicht:",
                    "- Verwendet: {{ storage_used }}",
                    "- Verfügbar: {{ storage_total }}",
                    "- Frei: {{ storage_remaining }}",
                    "- Warnschwelle: {{ warning_threshold }} Prozent",
                    "",
                    "So schaffst du wieder Platz:",
                    "1. Speicher verwalten: {{ manage_storage_url }}",
                    "2. Direkt auf einen größeren Plan upgraden: {{ upgrade_url }}",
                    "",
                    "Räume am besten heute noch auf, damit deine Workflows nicht unterbrochen werden.",
                    "",
                    "Viele Grüße",
                    "Workloom Support",
                ]),
            },
            'payment-failed': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "wir konnten deine Zahlung für den {{ plan_name }} Plan leider nicht verarbeiten.",
                    "",
                    "Details:",
                    "- Betrag: {{ amount }}",
                    "- Zahlungsmethode: {{ payment_method }}",
                    "- Fehlversuch am: {{ failed_date }}",
                    "",
                    "Wir versuchen die Abbuchung automatisch in {{ retry_days }} Tagen erneut. Danach beginnt eine Nachfrist von {{ grace_period_days }} Tagen, bevor dein Zugang eingeschränkt wird.",
                    "",
                    "Bitte aktualisiere deine Zahlungsdaten hier:",
                    "{{ update_payment_url }}",
                    "",
                    "Weitere Links:",
                    "- Abonnement verwalten: {{ subscription_url }}",
                    "- Hilfe und Support: {{ help_url }}",
                    "",
                    "Melde dich bei Fragen jederzeit.",
                ]),
            },
            'account-deletion-warning': {
                'text_content': "\n".join([
                    "Hallo {{ user.username }},",
                    "",
                    "dein Workloom Konto ist seit {{ inactive_days }} Tagen inaktiv.",
                    "Ohne Reaktion wird es in {{ days_remaining }} Tagen gelöscht (gesamt {{ total_inactive_days }} Tage Inaktivität).",
                    "",
                    "So behältst du deinen Zugang:",
                    "1. Melde dich wieder bei Workloom an oder folge diesem Link: {{ reactivate_url }}",
                    "2. Sichere deine Daten vorab: {{ export_url }}",
                    "",
                    "Wir würden uns freuen, dich bald wiederzusehen.",
                ]),
            },
            'chat-benachrichtigung': {
                'text_content': "\n".join([
                    "Hallo {{ recipient_name }},",
                    "",
                    "du hast eine neue Nachricht von {{ sender_name }} erhalten.",
                    "",
                    "{% if message_preview %}",
                    "Nachrichten-Vorschau:",
                    '"{{ message_preview }}"',
                    "{% endif %}",
                    "",
                    "Du hast aktuell {{ unread_count }} ungelesene Nachrichten.",
                    "",
                    "Zum Chat: {{ chat_url }}",
                    "Profileinstellungen: {{ profile_url }}",
                    "",
                    "Bis gleich im Chat!",
                    "{{ site_name }} Team",
                ]),
            },
            'willkommen-bei-workloom-e-mail-bestatigen': {
                'text_content': "\n".join([
                    "Willkommen bei {{ site_name }}, {{ user_name }}!",
                    "",
                    "WICHTIG: E-Mail-Bestätigung erforderlich.",
                    "",
                    "Du musst deine E-Mail-Adresse bestätigen, um dein Konto zu aktivieren.",
                    "Ohne Bestätigung kannst du dich nicht anmelden und hast keinen Zugriff auf Workloom.",
                    "",
                    "Vielen Dank für deine Registrierung!",
                    "Deine Anmeldung war erfolgreich, aber dein Konto ist noch nicht aktiviert.",
                    "",
                    "Bestätige deine E-Mail über diesen Link:",
                    "{{ activation_url }}",
                    "",
                    "Der Link ist nur begrenzt gültig. Bitte bestätige deine Adresse zeitnah.",
                    "",
                    "Was dich nach der Bestätigung erwartet:",
                    "- Chat-System: Direkte Kommunikation mit Kollegen und Kunden",
                    "- Shopify-Integration: Nahtlose E-Commerce-Lösungen",
                    "- PDF-Suche und KI: Intelligente Dokumentenanalyse und Zusammenfassungen",
                    "- Video-Hosting: Professionelle Präsentation deiner Projekte",
                    "- Organisationstools: Notizen, Boards und Terminplanung",
                    "- Amortisationsrechner: Finanzanalysen und Kalkulationen",
                    "- Statistiken und Analytics: Datengetriebene Entscheidungen",
                    "- Sichere Dateifreigabe: Verschlüsselter Transfer und Sharing",
                    "",
                    "Probleme beim Bestätigen? Kopiere den Link in deinen Browser:",
                    "{{ activation_url }}",
                    "",
                    "{{ site_name }} Team",
                    "Support: kontakt@workloom.de",
                    "© {{ current_year }} {{ site_name }}. Alle Rechte vorbehalten.",
                ]),
                'available_variables': {
                    'user_name': 'Name des Benutzers',
                    'activation_url': 'Aktivierungslink zur Bestätigung',
                    'site_name': 'Name der Plattform',
                    'current_year': 'Aktuelles Jahr',
                },
            },
            'welcome-account-activated': {
                'text_content': "\n".join([
                    "Hallo {{ user_name }},",
                    "",
                    "deine E-Mail-Adresse ist bestätigt und dein {{ site_name }} Konto ist jetzt aktiv.",
                    "",
                    "Starte direkt hier:",
                    "Dashboard: {{ dashboard_url }}",
                    "Profil und Einstellungen: {{ profile_url }}",
                    "",
                    "Wir wünschen dir viel Erfolg mit {{ site_name }}.",
                    "{{ site_name }} Team",
                    "© {{ current_year }} {{ site_name }}. Alle Rechte vorbehalten.",
                ]),
                'available_variables': {
                    'user_name': 'Name des Benutzers',
                    'dashboard_url': 'Link zum Dashboard',
                    'profile_url': 'Link zu den Profileinstellungen',
                    'site_name': 'Name der Plattform',
                    'current_year': 'Aktuelles Jahr',
                },
            },
        }

        for slug, data in text_updates.items():
            try:
                template = EmailTemplate.objects.get(slug=slug)
            except EmailTemplate.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'⚠️ Template nicht gefunden: {slug}'))
                continue

            if 'text_content' in data:
                template.text_content = data['text_content']
            if 'available_variables' in data:
                template.available_variables = data['available_variables']

            template.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Inhalt aktualisiert: {template.name}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Email template update completed!'))
