from django.core.management.base import BaseCommand
from email_templates.models import EmailTemplate, EmailTemplateCategory


class Command(BaseCommand):
    help = 'Create default chat notification email template'

    def handle(self, *args, **options):
        # Get or create category
        category, created = EmailTemplateCategory.objects.get_or_create(
            slug='communication',
            defaults={
                'name': 'Kommunikation',
                'description': 'Templates für Kommunikation und Benachrichtigungen',
                'icon': 'fas fa-comments',
                'order': 5,
                'is_active': True
            }
        )

        # Create chat notification template
        template, created = EmailTemplate.objects.get_or_create(
            template_type='chat_notification',
            defaults={
                'name': 'Chat-Benachrichtigung',
                'slug': 'chat-benachrichtigung',
                'subject': 'Neue Nachricht von {{ sender_name }} - {{ site_name }}',
                'html_content': '''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neue Chat-Nachricht</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
        }
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        .message-preview {
            background: #f8f9fa;
            border-left: 4px solid #007bff;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }
        .sender-info {
            font-weight: bold;
            color: #007bff;
            margin-bottom: 8px;
        }
        .message-text {
            color: #333;
            font-style: italic;
        }
        .action-button {
            display: inline-block;
            background: #007bff;
            color: white;
            text-decoration: none;
            padding: 12px 30px;
            border-radius: 5px;
            font-weight: bold;
            margin: 20px 0;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            font-size: 12px;
            color: #666;
            text-align: center;
        }
        .unsubscribe {
            margin-top: 15px;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">💬 {{ site_name }}</div>
            <h2>Neue Nachricht erhalten!</h2>
        </div>

        <p>Hallo {{ recipient_name }},</p>

        <p>Sie haben eine neue Nachricht in Ihrem Chat erhalten:</p>

        <div class="message-preview">
            <div class="sender-info">📩 Von: {{ sender_name }}</div>
            <div class="message-text">
                {% if message_preview %}
                    "{{ message_preview }}"
                {% else %}
                    Eine neue Nachricht wurde gesendet.
                {% endif %}
            </div>
            {% if unread_count > 1 %}
                <div style="margin-top: 10px; font-size: 12px; color: #666;">
                    + {{ unread_count|add:"-1" }} weitere ungelesene Nachricht{{ unread_count|add:"-1"|pluralize:"en" }}
                </div>
            {% endif %}
        </div>

        <div style="text-align: center;">
            <a href="{{ chat_url }}" class="action-button">
                💬 Nachricht anzeigen
            </a>
        </div>

        <p style="margin-top: 25px; font-size: 14px; color: #666;">
            Sie erhalten diese E-Mail, weil Sie Chat-Benachrichtigungen aktiviert haben.
            Sie können diese in Ihren <a href="{{ profile_url }}">Profileinstellungen</a> deaktivieren.
        </p>

        <div class="footer">
            <p>{{ site_name }} - Ihr Kommunikationssystem</p>
            <div class="unsubscribe">
                <a href="{{ profile_url }}" style="color: #999; text-decoration: none;">
                    Benachrichtigungen verwalten
                </a>
            </div>
        </div>
    </div>
</body>
</html>''',
                'text_content': '''Neue Chat-Nachricht - {{ site_name }}

Hallo {{ recipient_name }},

Sie haben eine neue Nachricht von {{ sender_name }} erhalten:

{% if message_preview %}
"{{ message_preview }}"
{% else %}
Eine neue Nachricht wurde gesendet.
{% endif %}

{% if unread_count > 1 %}
+ {{ unread_count|add:"-1" }} weitere ungelesene Nachricht{{ unread_count|add:"-1"|pluralize:"en" }}
{% endif %}

Antworten Sie hier: {{ chat_url }}

Sie können diese Benachrichtigungen in Ihren Profileinstellungen verwalten: {{ profile_url }}

---
{{ site_name }}
''',
                'category': category,
                'is_active': True,
                'is_default': True,
                'custom_css': '',
                'available_variables': {
                    'recipient_name': 'Name des Empfängers',
                    'sender_name': 'Name des Absenders',
                    'message_preview': 'Vorschau der Nachricht (gekürzt)',
                    'unread_count': 'Anzahl ungelesener Nachrichten',
                    'chat_url': 'Link zum Chat',
                    'profile_url': 'Link zu den Profileinstellungen',
                    'site_name': 'Name der Website'
                },
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Chat-Benachrichtigungs-Template erstellt')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Chat-Benachrichtigungs-Template existiert bereits')
            )