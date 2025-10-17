#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTrigger, EmailTemplate

# Create email triggers
triggers_data = [
    {
        'trigger_key': 'user_registration',
        'name': 'Benutzer-Registrierung',
        'description': 'Ausgelöst wenn sich ein neuer Benutzer registriert',
        'category': 'authentication',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'email': 'E-Mail-Adresse',
            'activation_url': 'Aktivierungs-URL',
            'site_name': 'Name der Webseite'
        }
    },
    {
        'trigger_key': 'account_activation',
        'name': 'Account-Aktivierung',
        'description': 'Ausgelöst bei Account-Aktivierung oder E-Mail-Verifikation',
        'category': 'authentication',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'email': 'E-Mail-Adresse',
            'activation_url': 'Aktivierungs-URL',
            'site_name': 'Name der Webseite'
        }
    },
    {
        'trigger_key': 'password_reset',
        'name': 'Passwort zurücksetzen',
        'description': 'Ausgelöst wenn ein Benutzer sein Passwort zurücksetzen möchte',
        'category': 'authentication',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'reset_url': 'Passwort-Reset-URL',
            'site_name': 'Name der Webseite'
        }
    },
    {
        'trigger_key': 'chat_message_notification',
        'name': 'Chat-Nachrichten Benachrichtigung',
        'description': 'Ausgelöst wenn ungelesene Chat-Nachrichten vorliegen',
        'category': 'system',
        'available_variables': {
            'recipient_name': 'Name des Empfängers',
            'sender_name': 'Name des Absenders',
            'message_preview': 'Vorschau der Nachricht',
            'unread_count': 'Anzahl ungelesener Nachrichten',
            'chat_url': 'Link zum Chat',
            'profile_url': 'Link zum Profil',
            'site_name': 'Name der Webseite'
        }
    },
    {
        'trigger_key': 'payment_failed',
        'name': 'Zahlung fehlgeschlagen',
        'description': 'Ausgelöst wenn eine Zahlung fehlschlägt',
        'category': 'payments',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'amount': 'Zahlungsbetrag',
            'payment_method': 'Zahlungsmethode',
            'retry_url': 'URL zur Zahlung wiederholen'
        }
    },
    {
        'trigger_key': 'storage_warning',
        'name': 'Speicherplatz-Warnung',
        'description': 'Ausgelöst bei Speicherplatz-Warnungen',
        'category': 'storage',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'used_storage': 'Genutzter Speicherplatz',
            'total_storage': 'Gesamtspeicherplatz',
            'percentage_used': 'Prozentual genutzter Speicher',
            'upgrade_url': 'URL zum Upgrade'
        }
    },
    {
        'trigger_key': 'subscription_upgrade',
        'name': 'Abonnement-Upgrade',
        'description': 'Ausgelöst bei Abonnement-Upgrade',
        'category': 'payments',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'old_plan': 'Alter Plan',
            'new_plan': 'Neuer Plan',
            'next_billing_date': 'Nächstes Abrechnungsdatum'
        }
    },
    {
        'trigger_key': 'account_deletion_warning',
        'name': 'Konto-Löschwarnung',
        'description': 'Ausgelöst vor geplanter Account-Löschung',
        'category': 'system',
        'available_variables': {
            'user_name': 'Name des Benutzers',
            'deletion_date': 'Geplantes Löschdatum',
            'reactivate_url': 'URL zur Reaktivierung'
        }
    }
]

# Create triggers
for trigger_data in triggers_data:
    trigger, created = EmailTrigger.objects.get_or_create(
        trigger_key=trigger_data['trigger_key'],
        defaults={
            'name': trigger_data['name'],
            'description': trigger_data['description'],
            'category': trigger_data['category'],
            'available_variables': trigger_data['available_variables'],
            'is_active': True,
            'is_system_trigger': True
        }
    )
    if created:
        print(f'✅ Trigger created: {trigger.name}')
    else:
        print(f'ℹ️ Trigger already exists: {trigger.name}')

# Assign triggers to existing templates
template_trigger_mapping = {
    'user_registration': 'user_registration',
    'account_activation': 'account_activation',
    'password_reset': 'password_reset',
    'chat_notification': 'chat_message_notification',
    'custom': None  # Custom templates don't get automatic triggers
}

updated_count = 0
for template in EmailTemplate.objects.all():
    trigger_key = template_trigger_mapping.get(template.template_type)
    if trigger_key:
        try:
            trigger = EmailTrigger.objects.get(trigger_key=trigger_key)
            if not template.trigger:
                template.trigger = trigger
                template.save()
                updated_count += 1
                print(f'✅ Assigned trigger "{trigger.name}" to template "{template.name}"')
        except EmailTrigger.DoesNotExist:
            print(f'⚠️ Trigger "{trigger_key}" not found for template "{template.name}"')

print(f'\n🎉 Summary:')
print(f'- Created/verified {len(triggers_data)} triggers')
print(f'- Updated {updated_count} templates with triggers')
print(f'- Total templates: {EmailTemplate.objects.count()}')
print(f'- Total triggers: {EmailTrigger.objects.count()}')