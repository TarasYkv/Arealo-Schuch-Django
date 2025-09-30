from django.db import migrations


def update_default_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('email_templates', 'EmailTemplate')

    template_updates = {
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

    for slug, payload in template_updates.items():
        try:
            template = EmailTemplate.objects.get(slug=slug)
        except EmailTemplate.DoesNotExist:
            continue

        for field, value in payload.items():
            setattr(template, field, value)
        template.save()


def reverse_update_default_templates(apps, schema_editor):
    # No rollback necessary
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('email_templates', '0004_alter_emailtemplate_slug'),
    ]

    operations = [
        migrations.RunPython(update_default_templates, reverse_update_default_templates),
    ]
