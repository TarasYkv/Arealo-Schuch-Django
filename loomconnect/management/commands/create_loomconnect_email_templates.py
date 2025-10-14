"""
Management Command: Create LoomConnect Email Templates
Erstellt Email-Templates für alle LoomConnect-Trigger
"""

from django.core.management.base import BaseCommand
from email_templates.models import EmailTrigger, EmailTemplate, EmailTemplateCategory
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Erstellt Email-Templates für LoomConnect-Trigger'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle LoomConnect Email-Templates...\n')

        # Kategorie erstellen oder holen
        category, created = EmailTemplateCategory.objects.get_or_create(
            slug='loomconnect',
            defaults={
                'name': 'LoomConnect',
                'description': 'Email-Templates für LoomConnect Skill-Matching und Networking',
                'icon': 'bi-people',
                'order': 100,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✓ Kategorie "LoomConnect" erstellt'))
        else:
            self.stdout.write('  → Kategorie "LoomConnect" existiert bereits')

        templates_data = [
            {
                'trigger_key': 'loomconnect_connection_accepted',
                'name': 'LoomConnect: Verbindung akzeptiert',
                'subject': '🎉 {{accepter_name}} hat deine Verbindungsanfrage akzeptiert!',
                'html_content': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }
        .profile { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #667eea; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Neue Verbindung!</h1>
        </div>
        <div class="content">
            <p>Hi {{user_name}},</p>

            <p><strong>{{accepter_name}}</strong> hat deine Verbindungsanfrage akzeptiert!</p>

            <div class="profile">
                <h3>{{accepter_name}} (@{{accepter_username}})</h3>
                <p>{{accepter_bio}}</p>
            </div>

            <p>Ihr könnt jetzt direkt miteinander chatten und euch vernetzen.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{{chat_url}}" class="button">💬 Chat öffnen</a>
                <a href="{{profile_url}}" class="button">👤 Profil ansehen</a>
            </div>

            <p>Viel Erfolg beim Vernetzen! 🚀</p>

            <p>Dein LoomConnect Team</p>
        </div>
        <div class="footer">
            <p>Diese E-Mail wurde automatisch von LoomConnect gesendet.<br>
            <a href="{{site_url}}/connect/settings/">Benachrichtigungseinstellungen ändern</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hi {{user_name}},

🎉 Neue Verbindung!

{{accepter_name}} (@{{accepter_username}}) hat deine Verbindungsanfrage akzeptiert!

{{accepter_bio}}

Ihr könnt jetzt direkt miteinander chatten und euch vernetzen.

Chat öffnen: {{chat_url}}
Profil ansehen: {{profile_url}}

Viel Erfolg beim Vernetzen! 🚀

Dein LoomConnect Team

---
Benachrichtigungseinstellungen ändern: {{site_url}}/connect/settings/'''
            },
            {
                'trigger_key': 'loomconnect_new_message',
                'name': 'LoomConnect: Neue Nachricht',
                'subject': '💬 Neue Nachricht von {{sender_name}}',
                'html_content': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }
        .message-preview { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #667eea; font-style: italic; }
        .badge { background: #e74c3c; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💬 Neue Nachricht</h1>
        </div>
        <div class="content">
            <p>Hi {{user_name}},</p>

            <p><strong>{{sender_name}}</strong> (@{{sender_username}}) hat dir eine Nachricht geschickt:</p>

            <div class="message-preview">
                "{{message_preview}}"
            </div>

            <p>Du hast <span class="badge">{{unread_count}}</span> ungelesene Nachricht(en) in diesem Chat.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{{chat_url}}" class="button">💬 Jetzt antworten</a>
            </div>

            <p>Beste Grüße,<br>
            Dein LoomConnect Team</p>
        </div>
        <div class="footer">
            <p>Diese E-Mail wurde automatisch von LoomConnect gesendet.<br>
            <a href="{{site_url}}/connect/settings/">Benachrichtigungseinstellungen ändern</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hi {{user_name}},

💬 Neue Nachricht von {{sender_name}} (@{{sender_username}}):

"{{message_preview}}"

Du hast {{unread_count}} ungelesene Nachricht(en) in diesem Chat.

Jetzt antworten: {{chat_url}}

Beste Grüße,
Dein LoomConnect Team

---
Benachrichtigungseinstellungen ändern: {{site_url}}/connect/settings/'''
            },
            {
                'trigger_key': 'loomconnect_new_match',
                'name': 'LoomConnect: Neues Match',
                'subject': '✨ Neues Match gefunden: {{match_name}}!',
                'html_content': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }
        .profile { background: white; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #667eea; }
        .match-score { text-align: center; font-size: 48px; font-weight: bold; color: #667eea; margin: 20px 0; }
        .skills { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
        .skill-tag { background: #667eea; color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✨ Neues Match!</h1>
        </div>
        <div class="content">
            <p>Hi {{user_name}},</p>

            <p>Wir haben jemanden gefunden, der perfekt zu deinen Skills passt!</p>

            <div class="match-score">{{match_score}}% Match</div>

            <div class="profile">
                <h3>{{match_name}} (@{{match_username}})</h3>
                <p>{{match_bio}}</p>

                <h4>Skills:</h4>
                <p>{{match_skills}}</p>

                <h4>Gemeinsame Interessen:</h4>
                <p>{{common_skills}}</p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{{match_profile_url}}" class="button">👤 Profil ansehen & Vernetzen</a>
            </div>

            <p>Verpasse nicht die Chance, dich zu vernetzen! 🚀</p>

            <p>Beste Grüße,<br>
            Dein LoomConnect Team</p>
        </div>
        <div class="footer">
            <p>Diese E-Mail wurde automatisch von LoomConnect gesendet.<br>
            <a href="{{site_url}}/connect/settings/">Benachrichtigungseinstellungen ändern</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hi {{user_name}},

✨ Neues Match gefunden!

Wir haben jemanden gefunden, der perfekt zu deinen Skills passt!

Match-Score: {{match_score}}%

{{match_name}} (@{{match_username}})
{{match_bio}}

Skills: {{match_skills}}
Gemeinsame Interessen: {{common_skills}}

Profil ansehen: {{match_profile_url}}

Verpasse nicht die Chance, dich zu vernetzen! 🚀

Beste Grüße,
Dein LoomConnect Team

---
Benachrichtigungseinstellungen ändern: {{site_url}}/connect/settings/'''
            },
            {
                'trigger_key': 'loomconnect_weekly_digest',
                'name': 'LoomConnect: Wöchentliche Zusammenfassung',
                'subject': '📊 Deine LoomConnect Woche: {{week_start}} - {{week_end}}',
                'html_content': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
        .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }
        .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
        .stat-box { background: white; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #667eea; }
        .stat-number { font-size: 36px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 14px; color: #666; margin-top: 5px; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Deine Woche bei LoomConnect</h1>
            <p>{{week_start}} - {{week_end}}</p>
        </div>
        <div class="content">
            <p>Hi {{user_name}},</p>

            <p>Hier ist deine wöchentliche Zusammenfassung:</p>

            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{{new_matches_count}}</div>
                    <div class="stat-label">Neue Matches</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{new_messages_count}}</div>
                    <div class="stat-label">Neue Nachrichten</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{profile_views_count}}</div>
                    <div class="stat-label">Profil-Aufrufe</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{new_connections_count}}</div>
                    <div class="stat-label">Neue Verbindungen</div>
                </div>
            </div>

            <h3>🔥 Top Matches dieser Woche:</h3>
            <p>{{top_matches}}</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{{dashboard_url}}" class="button">📊 Dashboard öffnen</a>
            </div>

            <p>Bleib aktiv und vernetze dich weiter! 🚀</p>

            <p>Beste Grüße,<br>
            Dein LoomConnect Team</p>
        </div>
        <div class="footer">
            <p>Diese E-Mail wurde automatisch von LoomConnect gesendet.<br>
            <a href="{{site_url}}/connect/settings/">Benachrichtigungseinstellungen ändern</a></p>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Hi {{user_name}},

📊 Deine Woche bei LoomConnect
{{week_start}} - {{week_end}}

Deine wöchentliche Zusammenfassung:

• {{new_matches_count}} Neue Matches
• {{new_messages_count}} Neue Nachrichten
• {{profile_views_count}} Profil-Aufrufe
• {{new_connections_count}} Neue Verbindungen

🔥 Top Matches dieser Woche:
{{top_matches}}

Dashboard öffnen: {{dashboard_url}}

Bleib aktiv und vernetze dich weiter! 🚀

Beste Grüße,
Dein LoomConnect Team

---
Benachrichtigungseinstellungen ändern: {{site_url}}/connect/settings/'''
            }
        ]

        created_count = 0
        for template_data in templates_data:
            # Trigger holen
            try:
                trigger = EmailTrigger.objects.get(trigger_key=template_data['trigger_key'])
            except EmailTrigger.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'  ✗ Trigger "{template_data["trigger_key"]}" nicht gefunden!'))
                continue

            # Template erstellen oder aktualisieren
            template, created = EmailTemplate.objects.update_or_create(
                slug=slugify(template_data['name']),
                defaults={
                    'name': template_data['name'],
                    'category': category,
                    'trigger': trigger,
                    'template_type': 'notification',
                    'subject': template_data['subject'],
                    'html_content': template_data['html_content'],
                    'text_content': template_data['text_content'],
                    'is_active': True,
                    'is_auto_send': True,
                    'send_delay_minutes': 0
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Template erstellt: {template_data["name"]}'))
                created_count += 1
            else:
                self.stdout.write(f'  → Template aktualisiert: {template_data["name"]}')

        self.stdout.write(self.style.SUCCESS(f'\n✅ {created_count} neue Email-Templates erstellt!'))
        self.stdout.write('\n📧 Alle Templates sind aktiviert und werden automatisch versendet.')
