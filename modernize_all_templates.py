#!/usr/bin/env python
"""
Script zur vollständigen Modernisierung ALLER Email-Templates
- Kurz, freundlich, bestimmt
- Keine Emojis in Betreffzeilen
- Modernes, einheitliches Design
- Korrekte Variablen
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTemplate, EmailTrigger

# Basis-Style für alle Templates (wiederverwendbar)
BASE_STYLE = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        margin: 0;
        padding: 0;
        background-color: #f5f5f5;
    }
    .container {
        max-width: 600px;
        margin: 40px auto;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        overflow: hidden;
    }
    .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 40px 30px;
        text-align: center;
    }
    .logo {
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .content {
        padding: 40px 30px;
    }
    h1 {
        color: #667eea;
        font-size: 22px;
        margin: 0 0 24px 0;
        font-weight: 600;
    }
    p {
        margin: 0 0 16px 0;
        color: #555;
    }
    .button-container {
        text-align: center;
        margin: 32px 0;
    }
    .button {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        padding: 16px 48px;
        text-decoration: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 16px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .info {
        background: #f8f9ff;
        border-left: 3px solid #667eea;
        padding: 16px;
        margin: 24px 0;
        border-radius: 4px;
        font-size: 14px;
    }
    .footer {
        background: #fafafa;
        padding: 24px 30px;
        text-align: center;
        font-size: 13px;
        color: #888;
    }
    .link {
        color: #667eea;
        word-break: break-all;
    }
"""

def create_template_html(header_title, h1_text, main_content, button_text=None, button_url=None, info_box=None, color_scheme='default'):
    """Erstellt einheitliches Template-HTML"""

    # Farbschemata
    colors = {
        'default': {'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'primary': '#667eea', 'info_bg': '#f8f9ff'},
        'success': {'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 'primary': '#10b981', 'info_bg': '#d1fae5'},
        'warning': {'gradient': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', 'primary': '#f59e0b', 'info_bg': '#fef3c7'},
        'danger': {'gradient': 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)', 'primary': '#ef4444', 'info_bg': '#fee2e2'},
    }

    scheme = colors.get(color_scheme, colors['default'])

    # Style mit angepassten Farben
    style = BASE_STYLE.replace('#667eea', scheme['primary']).replace('linear-gradient(135deg, #667eea 0%, #764ba2 100%)', scheme['gradient']).replace('#f8f9ff', scheme['info_bg'])

    # Button HTML (optional)
    button_html = ''
    if button_text and button_url:
        button_html = f'''
            <div class="button-container">
                <a href="{button_url}" class="button">{button_text}</a>
            </div>
        '''

    # Info Box HTML (optional)
    info_html = ''
    if info_box:
        info_html = f'''
            <div class="info">
                {info_box}
            </div>
        '''

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{style}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🚀 Workloom</div>
            <p style="margin: 0; opacity: 0.9;">{header_title}</p>
        </div>

        <div class="content">
            <h1>{h1_text}</h1>

            {main_content}

            {button_html}

            {info_html}
        </div>

        <div class="footer">
            <strong>Workloom</strong> – Deine moderne Arbeitsplattform
        </div>
    </div>
</body>
</html>'''

# Alle Template-Definitionen
TEMPLATES = {
    'user_registration': {
        'skip': True,  # Bereits modernisiert
        'subject': 'Workloom: E-Mail bestätigen'
    },

    'account_activation': {
        'subject': 'Konto aktiviert - Willkommen bei Workloom',
        'html': create_template_html(
            header_title='Konto aktiviert',
            h1_text='Willkommen {{ user_name }}!',
            main_content='''
                <p><strong>Dein Konto ist jetzt aktiv.</strong></p>
                <p>Du kannst alle Funktionen von Workloom nutzen.</p>
            ''',
            button_text='Zum Dashboard',
            button_url='{{ dashboard_url }}',
            color_scheme='success'
        )
    },

    'chat_message_notification': {
        'subject': 'Neue Nachricht von {{ sender_name }}',
        'html': create_template_html(
            header_title='Neue Nachricht',
            h1_text='Hey {{ user_name }}!',
            main_content='''
                <p><strong>{{ sender_name }}</strong> hat dir eine Nachricht geschickt.</p>
                <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; font-style: italic;">"{{ message_preview }}"</p>
                </div>
            ''',
            button_text='Nachricht ansehen',
            button_url='{{ chat_url }}'
        )
    },

    'subscription_upgrade': {
        'subject': 'Willkommen im {{ plan_name }} Plan',
        'html': create_template_html(
            header_title='Upgrade erfolgreich',
            h1_text='Danke {{ user_name }}!',
            main_content='''
                <p><strong>Dein Upgrade auf {{ plan_name }} war erfolgreich.</strong></p>
                <p>Du hast jetzt Zugriff auf alle Premium-Features.</p>
            ''',
            button_text='Features entdecken',
            button_url='{{ dashboard_url }}',
            info_box='<strong>Neue Features:</strong> {{ features_list }}',
            color_scheme='success'
        )
    },

    'password_reset': {
        'subject': 'Passwort zurücksetzen',
        'html': create_template_html(
            header_title='Passwort zurücksetzen',
            h1_text='Hey {{ user_name }}!',
            main_content='''
                <p><strong>Du hast ein neues Passwort angefordert.</strong></p>
                <p>Klicke auf den Button, um dein Passwort zurückzusetzen.</p>
            ''',
            button_text='Passwort zurücksetzen',
            button_url='{{ reset_url }}',
            info_box='<strong>⏱ Hinweis:</strong> Der Link ist 24 Stunden gültig.',
            color_scheme='warning'
        )
    },

    'storage_warning': {
        'subject': 'Speicherplatz wird knapp',
        'html': create_template_html(
            header_title='Speicherplatz-Warnung',
            h1_text='Hey {{ user_name }}!',
            main_content='''
                <p><strong>Dein Speicherplatz wird knapp.</strong></p>
                <p>Du hast bereits <strong>{{ usage_percentage }}%</strong> genutzt.</p>
            ''',
            button_text='Speicher erweitern',
            button_url='{{ upgrade_url }}',
            info_box='<strong>Aktuell:</strong> {{ used_space }} von {{ total_space }}',
            color_scheme='warning'
        )
    },

    'payment_failed': {
        'subject': 'Zahlungsproblem bei deinem Abonnement',
        'html': create_template_html(
            header_title='Zahlung fehlgeschlagen',
            h1_text='Hey {{ user_name }}!',
            main_content='''
                <p><strong>Bei deiner letzten Zahlung gab es ein Problem.</strong></p>
                <p>Bitte aktualisiere deine Zahlungsmethode, um dein Abo aktiv zu halten.</p>
            ''',
            button_text='Zahlungsmethode aktualisieren',
            button_url='{{ billing_url }}',
            info_box='<strong>Betrag:</strong> {{ amount }}<br><strong>Fehler:</strong> {{ error_message }}',
            color_scheme='danger'
        )
    },

    'account_deletion_warning': {
        'subject': 'Dein Konto wird in {{ days_remaining }} Tagen gelöscht',
        'html': create_template_html(
            header_title='Konto-Löschwarnung',
            h1_text='Hey {{ user_name }}!',
            main_content='''
                <p><strong>Dein Konto wird in {{ days_remaining }} Tagen gelöscht.</strong></p>
                <p>Du hast deine E-Mail-Adresse nicht bestätigt.</p>
                <p>Bestätige jetzt, um dein Konto zu behalten.</p>
            ''',
            button_text='E-Mail bestätigen',
            button_url='{{ verification_url }}',
            color_scheme='danger'
        )
    },

    'loomconnect_new_message': {
        'subject': 'Neue Nachricht von {{ sender_name }}',
        'html': create_template_html(
            header_title='LoomConnect',
            h1_text='Neue Nachricht!',
            main_content='''
                <p><strong>{{ sender_name }}</strong> hat dir geschrieben:</p>
                <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;">"{{ message_preview }}"</p>
                </div>
            ''',
            button_text='Nachricht lesen',
            button_url='{{ message_url }}'
        )
    },

    'loomconnect_new_match': {
        'subject': 'Neues Match: {{ match_name }}',
        'html': create_template_html(
            header_title='LoomConnect',
            h1_text='Neues Match gefunden!',
            main_content='''
                <p><strong>{{ match_name }}</strong> passt perfekt zu deinem Profil.</p>
                <p>{{ match_description }}</p>
            ''',
            button_text='Profil ansehen',
            button_url='{{ profile_url }}',
            info_box='<strong>Match-Score:</strong> {{ match_score }}%',
            color_scheme='success'
        )
    },

    'loomconnect_connection_accepted': {
        'subject': '{{ accepter_name }} hat deine Anfrage akzeptiert',
        'html': create_template_html(
            header_title='LoomConnect',
            h1_text='Neue Verbindung!',
            main_content='''
                <p><strong>{{ accepter_name }}</strong> hat deine Verbindungsanfrage akzeptiert.</p>
                <p>Ihr seid jetzt verbunden!</p>
            ''',
            button_text='Nachricht schreiben',
            button_url='{{ chat_url }}',
            color_scheme='success'
        )
    },

    'loomconnect_weekly_digest': {
        'subject': 'Deine LoomConnect Woche: {{ week_start }} - {{ week_end }}',
        'html': create_template_html(
            header_title='LoomConnect',
            h1_text='Deine Woche auf LoomConnect',
            main_content='''
                <p><strong>Das ist diese Woche passiert:</strong></p>
                <ul style="line-height: 2;">
                    <li>{{ new_connections }} neue Verbindungen</li>
                    <li>{{ new_messages }} neue Nachrichten</li>
                    <li>{{ profile_views }} Profil-Besuche</li>
                </ul>
            ''',
            button_text='Zu LoomConnect',
            button_url='{{ loomconnect_url }}',
            info_box='<strong>Tipp:</strong> Aktualisiere dein Profil für mehr Matches!'
        )
    }
}

def modernize_all_templates():
    """Modernisiert alle Email-Templates"""
    print("=" * 70)
    print("🚀 ALLE EMAIL-TEMPLATES WERDEN MODERNISIERT")
    print("=" * 70)

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    for trigger_key, config in TEMPLATES.items():
        # Finde Trigger
        trigger = EmailTrigger.objects.filter(trigger_key=trigger_key).first()

        if not trigger:
            print(f"⚠️  Trigger '{trigger_key}' nicht gefunden")
            not_found_count += 1
            continue

        # Finde Template
        template = EmailTemplate.objects.filter(trigger=trigger, is_active=True).first()

        if not template:
            print(f"⚠️  Kein aktives Template für '{trigger_key}'")
            not_found_count += 1
            continue

        # Skip wenn gewünscht
        if config.get('skip'):
            print(f"✓ '{template.name}' - bereits modernisiert")
            skipped_count += 1
            continue

        # Update Template
        template.subject = config['subject']
        template.html_content = config['html']
        template.save()

        print(f"✓ '{template.name}' modernisiert")
        print(f"  → Betreff: {config['subject']}")
        updated_count += 1

    print("=" * 70)
    print(f"✅ FERTIG!")
    print(f"   {updated_count} Templates modernisiert")
    print(f"   {skipped_count} übersprungen")
    if not_found_count > 0:
        print(f"   {not_found_count} nicht gefunden")
    print("=" * 70)

if __name__ == '__main__':
    modernize_all_templates()
