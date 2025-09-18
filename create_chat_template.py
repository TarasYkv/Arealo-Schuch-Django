#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTemplate

# Chat notification template erstellen
template, created = EmailTemplate.objects.get_or_create(
    template_type='chat_notification',
    defaults={
        'name': 'Chat-Benachrichtigung',
        'subject': '{{ site_name }} - Neue Nachricht von {{ sender_name }}',
        'html_content': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ site_name }} - Neue Nachricht</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="background-color: #2563eb; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">{{ site_name }}</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Neue Nachricht erhalten</p>
        </div>

        <div style="padding: 30px;">
            <h2 style="color: #1f2937; margin: 0 0 20px 0;">Hallo {{ recipient_name }}!</h2>

            <p style="color: #4b5563; line-height: 1.6; margin: 0 0 20px 0;">
                Du hast eine neue Nachricht von <strong>{{ sender_name }}</strong> erhalten:
            </p>

            <div style="background-color: #f9fafb; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0; border-radius: 4px;">
                <p style="margin: 0; color: #374151; font-style: italic;">"{{ message_preview }}"</p>
            </div>

            {% if unread_count > 1 %}
            <p style="color: #6b7280; margin: 15px 0;">
                Du hast insgesamt <strong>{{ unread_count }} ungelesene Nachrichten</strong> in diesem Chat.
            </p>
            {% endif %}

            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ chat_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    Chat öffnen
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #9ca3af; font-size: 14px; margin: 0 0 10px 0;">
                Du erhältst diese E-Mail, weil du Chat-Benachrichtigungen aktiviert hast.
            </p>
            <p style="color: #9ca3af; font-size: 14px; margin: 0;">
                <a href="{{ profile_url }}" style="color: #2563eb; text-decoration: none;">Benachrichtigungseinstellungen ändern</a>
            </p>
        </div>
    </div>
</body>
</html>''',
        'text_content': '''Hallo {{ recipient_name }}!

Du hast eine neue Nachricht von {{ sender_name }} auf {{ site_name }} erhalten:

"{{ message_preview }}"

{% if unread_count > 1 %}Du hast insgesamt {{ unread_count }} ungelesene Nachrichten in diesem Chat.{% endif %}

Chat öffnen: {{ chat_url }}

---
Du erhältst diese E-Mail, weil du Chat-Benachrichtigungen aktiviert hast.
Benachrichtigungseinstellungen ändern: {{ profile_url }}''',
        'slug': 'chat-notification',
        'available_variables': 'recipient_name, sender_name, message_preview, unread_count, chat_url, profile_url, site_name',
        'is_active': True,
        'is_default': True
    }
)

if created:
    print('✅ Chat notification template created successfully')
else:
    print('ℹ️ Chat notification template already exists')

print(f'Template ID: {template.id}')
print(f'Template active: {template.is_active}')