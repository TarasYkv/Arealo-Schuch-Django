#!/usr/bin/env python
"""
Script zur Modernisierung aller Email-Templates
Macht Templates kurz, freundlich und klar
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTemplate, EmailTrigger

# Template-Verbesserungen basierend auf Trigger-Key
IMPROVED_TEMPLATES = {
    # Bereits verbessert
    'user_registration': {
        'skip': True  # Bereits modernisiert
    },

    # Storage & Speicher
    'storage_warning': {
        'subject': 'Workloom: Speicherplatz wird knapp',
        'content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
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
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }
        .content {
            padding: 40px 30px;
        }
        h1 {
            color: #f59e0b;
            font-size: 22px;
            margin: 0 0 24px 0;
            font-weight: 600;
        }
        .button-container {
            text-align: center;
            margin: 32px 0;
        }
        .button {
            display: inline-block;
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white !important;
            padding: 16px 48px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
        }
        .info {
            background: #fef3c7;
            border-left: 3px solid #f59e0b;
            padding: 16px;
            margin: 24px 0;
            border-radius: 4px;
        }
        .footer {
            background: #fafafa;
            padding: 24px 30px;
            text-align: center;
            font-size: 13px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="font-size: 28px; font-weight: 700;">Workloom</div>
            <p style="margin: 0; opacity: 0.9;">Speicherplatz-Warnung</p>
        </div>

        <div class="content">
            <h1>Hey {{ user_name }}!</h1>

            <p><strong>Dein Speicherplatz wird knapp.</strong></p>

            <p>Du hast bereits <strong>{{ usage_percentage }}%</strong> deines verf\u00fcgbaren Speicherplatzes genutzt.</p>

            <div class="info">
                <strong>Aktueller Status:</strong><br>
                {{ used_space }} von {{ total_space }} belegt
            </div>

            <div class="button-container">
                <a href="{{ upgrade_url }}" class="button">Speicher erweitern</a>
            </div>

            <p style="font-size: 13px; color: #888;">Du kannst auch alte Dateien l\u00f6schen oder archivieren.</p>
        </div>

        <div class="footer">
            <strong>Workloom</strong> \u2013 Deine moderne Arbeitsplattform
        </div>
    </div>
</body>
</html>'''
    },

    # Payments
    'payment_successful': {
        'subject': 'Zahlung best\u00e4tigt',
        'content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: system-ui; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 40px auto; background: white; border-radius: 12px; overflow: hidden; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 40px 30px; text-align: center; }
        .content { padding: 40px 30px; }
        h1 { color: #10b981; font-size: 22px; margin: 0 0 24px 0; }
        .info { background: #d1fae5; border-left: 3px solid #10b981; padding: 16px; margin: 24px 0; border-radius: 4px; }
        .footer { background: #fafafa; padding: 24px; text-align: center; font-size: 13px; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="font-size: 28px; font-weight: 700;">Workloom</div>
            <p style="margin: 0; opacity: 0.9;">Zahlung erfolgreich</p>
        </div>
        <div class="content">
            <h1>Danke {{ user_name }}!</h1>
            <p><strong>Deine Zahlung war erfolgreich.</strong></p>
            <div class="info">
                <strong>Betrag:</strong> {{ amount }}<br>
                <strong>Datum:</strong> {{ payment_date }}<br>
                <strong>Transaktion:</strong> {{ transaction_id }}
            </div>
            <p style="font-size: 13px; color: #888;">Eine Rechnung senden wir dir per E-Mail.</p>
        </div>
        <div class="footer">
            <strong>Workloom</strong> \u2013 Deine moderne Arbeitsplattform
        </div>
    </div>
</body>
</html>'''
    }
}

def modernize_templates():
    """Modernisiert alle Email-Templates"""
    print("=" * 60)
    print("Email-Templates werden modernisiert...")
    print("=" * 60)

    templates = EmailTemplate.objects.all()
    updated_count = 0
    skipped_count = 0

    for template in templates:
        trigger_key = template.trigger.trigger_key if template.trigger else None

        # Überspringe Registrierungs-Template (bereits modernisiert)
        if trigger_key == 'user_registration':
            print(f"\u2713 '{template.name}' - bereits modernisiert")
            skipped_count += 1
            continue

        # Prüfe ob Template-Verbesserung verfügbar
        if trigger_key and trigger_key in IMPROVED_TEMPLATES:
            improvement = IMPROVED_TEMPLATES[trigger_key]

            if improvement.get('skip'):
                print(f"\u2713 '{template.name}' - \u00fcbersprungen")
                skipped_count += 1
                continue

            # Aktualisiere Template
            template.subject = improvement['subject']
            template.html_content = improvement['content']
            template.save()

            print(f"\u2713 '{template.name}' modernisiert")
            updated_count += 1
        else:
            print(f"- '{template.name}' - keine Verbesserung verf\u00fcgbar (Trigger: {trigger_key})")
            skipped_count += 1

    print("=" * 60)
    print(f"\u2713 Fertig! {updated_count} Templates modernisiert, {skipped_count} \u00fcbersprungen")
    print("=" * 60)

if __name__ == '__main__':
    modernize_templates()
