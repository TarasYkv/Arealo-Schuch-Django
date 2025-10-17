#!/usr/bin/env python
"""
Script zum Aktualisieren der Text-Versionen aller Email-Templates
Macht Text-Versionen konsistent mit HTML-Versionen
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTemplate, EmailTrigger

# Text-Versionen für alle Templates
TEXT_VERSIONS = {
    'user_registration': '''Workloom - E-Mail bestätigen

Hey {{ user_name }}!

Fast geschafft. Bitte bestätige deine E-Mail-Adresse, um dein Konto zu aktivieren.

Bestätigungslink:
{{ activation_url }}

Hinweis: Der Link ist 24 Stunden gültig.

Falls der Link nicht funktioniert, kopiere ihn in deinen Browser.

---
Workloom – Deine moderne Arbeitsplattform
Du hast dich nicht registriert? Ignoriere diese E-Mail einfach.
''',

    'account_activation': '''Konto aktiviert - Willkommen bei Workloom

Willkommen {{ user_name }}!

Dein Konto ist jetzt aktiv.
Du kannst alle Funktionen von Workloom nutzen.

Zum Dashboard:
{{ dashboard_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'chat_message_notification': '''Neue Nachricht von {{ sender_name }}

Hey {{ user_name }}!

{{ sender_name }} hat dir eine Nachricht geschickt.

"{{ message_preview }}"

Nachricht ansehen:
{{ chat_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'subscription_upgrade': '''Willkommen im {{ plan_name }} Plan

Danke {{ user_name }}!

Dein Upgrade auf {{ plan_name }} war erfolgreich.
Du hast jetzt Zugriff auf alle Premium-Features.

Features entdecken:
{{ dashboard_url }}

Neue Features: {{ features_list }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'password_reset': '''Passwort zurücksetzen

Hey {{ user_name }}!

Du hast ein neues Passwort angefordert.
Klicke auf den Link, um dein Passwort zurückzusetzen.

Passwort zurücksetzen:
{{ reset_url }}

Hinweis: Der Link ist 24 Stunden gültig.

---
Workloom – Deine moderne Arbeitsplattform
''',

    'storage_warning': '''Speicherplatz wird knapp

Hey {{ user_name }}!

Dein Speicherplatz wird knapp.
Du hast bereits {{ usage_percentage }}% genutzt.

Aktuell: {{ used_space }} von {{ total_space }}

Speicher erweitern:
{{ upgrade_url }}

Du kannst auch alte Dateien löschen oder archivieren.

---
Workloom – Deine moderne Arbeitsplattform
''',

    'payment_failed': '''Zahlungsproblem bei deinem Abonnement

Hey {{ user_name }}!

Bei deiner letzten Zahlung gab es ein Problem.
Bitte aktualisiere deine Zahlungsmethode, um dein Abo aktiv zu halten.

Betrag: {{ amount }}
Fehler: {{ error_message }}

Zahlungsmethode aktualisieren:
{{ billing_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'account_deletion_warning': '''Dein Konto wird in {{ days_remaining }} Tagen gelöscht

Hey {{ user_name }}!

Dein Konto wird in {{ days_remaining }} Tagen gelöscht.
Du hast deine E-Mail-Adresse nicht bestätigt.

Bestätige jetzt, um dein Konto zu behalten.

E-Mail bestätigen:
{{ verification_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'loomconnect_new_message': '''Neue Nachricht von {{ sender_name }}

Neue Nachricht!

{{ sender_name }} hat dir geschrieben:

"{{ message_preview }}"

Nachricht lesen:
{{ message_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'loomconnect_new_match': '''Neues Match: {{ match_name }}

Neues Match gefunden!

{{ match_name }} passt perfekt zu deinem Profil.
{{ match_description }}

Match-Score: {{ match_score }}%

Profil ansehen:
{{ profile_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'loomconnect_connection_accepted': '''{{ accepter_name }} hat deine Anfrage akzeptiert

Neue Verbindung!

{{ accepter_name }} hat deine Verbindungsanfrage akzeptiert.
Ihr seid jetzt verbunden!

Nachricht schreiben:
{{ chat_url }}

---
Workloom – Deine moderne Arbeitsplattform
''',

    'loomconnect_weekly_digest': '''Deine LoomConnect Woche: {{ week_start }} - {{ week_end }}

Deine Woche auf LoomConnect

Das ist diese Woche passiert:

- {{ new_connections }} neue Verbindungen
- {{ new_messages }} neue Nachrichten
- {{ profile_views }} Profil-Besuche

Tipp: Aktualisiere dein Profil für mehr Matches!

Zu LoomConnect:
{{ loomconnect_url }}

---
Workloom – Deine moderne Arbeitsplattform
'''
}

def update_text_versions():
    """Aktualisiert Text-Versionen aller Templates"""
    print("=" * 70)
    print("📝 TEXT-VERSIONEN WERDEN AKTUALISIERT")
    print("=" * 70)

    updated_count = 0
    skipped_count = 0

    for trigger_key, text_content in TEXT_VERSIONS.items():
        # Finde Trigger
        trigger = EmailTrigger.objects.filter(trigger_key=trigger_key).first()

        if not trigger:
            print(f"⚠️  Trigger '{trigger_key}' nicht gefunden")
            continue

        # Finde Template
        template = EmailTemplate.objects.filter(trigger=trigger, is_active=True).first()

        if not template:
            print(f"⚠️  Kein aktives Template für '{trigger_key}'")
            continue

        # Update Text-Version
        template.text_content = text_content.strip()
        template.save()

        print(f"✓ '{template.name}' - Text-Version aktualisiert")
        updated_count += 1

    print("=" * 70)
    print(f"✅ FERTIG! {updated_count} Text-Versionen aktualisiert")
    print("=" * 70)

if __name__ == '__main__':
    update_text_versions()
