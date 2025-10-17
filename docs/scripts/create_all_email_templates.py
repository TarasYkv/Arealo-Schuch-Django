#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from email_templates.models import EmailTemplate

# All email templates data
templates_data = [
    {
        'name': 'Willkommen & E-Mail Verifizierung',
        'template_type': 'account_activation',
        'subject': 'Willkommen bei {{ site_name }} - E-Mail bestätigen',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Willkommen</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #2563eb;">Willkommen bei {{ site_name }}!</h1><p>Hallo {{ user_name }},</p><p>vielen Dank für Ihre Registrierung. Bitte bestätigen Sie Ihre E-Mail-Adresse:</p><div style="text-align: center; margin: 30px 0;"><a href="{{ activation_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">E-Mail bestätigen</a></div></body></html>''',
        'slug': 'welcome-email-verification',
        'available_variables': 'user_name, activation_url, site_name',
        'is_default': True
    },
    {
        'name': 'Willkommen bei Workloom - E-Mail bestätigen',
        'template_type': 'user_registration',
        'subject': 'Willkommen bei {{ site_name }} - E-Mail bestätigen',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Willkommen</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #2563eb;">Willkommen bei Workloom!</h1><p>Hallo {{ user_name }},</p><p>herzlich willkommen bei Workloom! Bitte bestätigen Sie Ihre E-Mail-Adresse um Ihr Konto zu aktivieren:</p><div style="text-align: center; margin: 30px 0;"><a href="{{ activation_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Konto aktivieren</a></div></body></html>''',
        'slug': 'welcome-workloom',
        'available_variables': 'user_name, activation_url, site_name',
        'is_default': True
    },
    {
        'name': 'E-Mail Verifizierung erneut senden',
        'template_type': 'account_activation',
        'subject': 'E-Mail Verifizierung - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>E-Mail Verifizierung</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #2563eb;">E-Mail Verifizierung</h1><p>Hallo {{ user_name }},</p><p>Sie haben eine neue E-Mail Verifizierung angefordert. Klicken Sie auf den Button um Ihre E-Mail zu bestätigen:</p><div style="text-align: center; margin: 30px 0;"><a href="{{ activation_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">E-Mail bestätigen</a></div></body></html>''',
        'slug': 'email-verification-resend',
        'available_variables': 'user_name, activation_url, site_name',
        'is_default': False
    },
    {
        'name': 'Passwort zurücksetzen',
        'template_type': 'password_reset',
        'subject': 'Passwort zurücksetzen - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Passwort zurücksetzen</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #2563eb;">Passwort zurücksetzen</h1><p>Hallo {{ user_name }},</p><p>Sie haben eine Passwort-Zurücksetzung angefordert. Klicken Sie auf den Button um ein neues Passwort zu erstellen:</p><div style="text-align: center; margin: 30px 0;"><a href="{{ reset_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Neues Passwort erstellen</a></div><p>Falls Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail.</p></body></html>''',
        'slug': 'password-reset',
        'available_variables': 'user_name, reset_url, site_name',
        'is_default': True
    },
    {
        'name': 'Abonnement-Upgrade Bestätigung',
        'template_type': 'custom',
        'subject': 'Abonnement erfolgreich aktualisiert - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Abonnement aktualisiert</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #2563eb;">Abonnement erfolgreich aktualisiert!</h1><p>Hallo {{ user_name }},</p><p>Ihr Abonnement wurde erfolgreich von "{{ old_plan }}" auf "{{ new_plan }}" aktualisiert.</p><p>Die neue Abrechnung beginnt am {{ next_billing_date }}.</p><p>Vielen Dank für Ihr Vertrauen!</p></body></html>''',
        'slug': 'subscription-upgrade',
        'available_variables': 'user_name, old_plan, new_plan, next_billing_date, site_name',
        'is_default': False
    },
    {
        'name': 'Speicherplatz-Warnung',
        'template_type': 'custom',
        'subject': 'Speicherplatz-Warnung - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Speicherplatz-Warnung</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #f59e0b;">Speicherplatz-Warnung</h1><p>Hallo {{ user_name }},</p><p>Ihr Speicherplatz ist zu {{ percentage_used }}% belegt ({{ used_storage }} von {{ total_storage }}).</p><p>Bitte löschen Sie nicht benötigte Dateien oder upgraden Sie Ihren Plan.</p><div style="text-align: center; margin: 30px 0;"><a href="{{ upgrade_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Plan upgraden</a></div></body></html>''',
        'slug': 'storage-warning',
        'available_variables': 'user_name, used_storage, total_storage, percentage_used, upgrade_url, site_name',
        'is_default': False
    },
    {
        'name': 'Zahlung fehlgeschlagen',
        'template_type': 'custom',
        'subject': 'Zahlung fehlgeschlagen - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Zahlung fehlgeschlagen</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #ef4444;">Zahlung fehlgeschlagen</h1><p>Hallo {{ user_name }},</p><p>Ihre Zahlung über {{ amount }} mit {{ payment_method }} ist fehlgeschlagen.</p><p>Bitte überprüfen Sie Ihre Zahlungsmethode und versuchen Sie es erneut.</p><div style="text-align: center; margin: 30px 0;"><a href="{{ retry_url }}" style="background-color: #ef4444; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Zahlung wiederholen</a></div></body></html>''',
        'slug': 'payment-failed',
        'available_variables': 'user_name, amount, payment_method, retry_url, site_name',
        'is_default': False
    },
    {
        'name': 'Konto-Löschwarnung',
        'template_type': 'custom',
        'subject': 'Konto-Löschung geplant - {{ site_name }}',
        'html_content': '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Konto-Löschwarnung</title></head><body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; padding: 30px;"><h1 style="color: #ef4444;">Konto-Löschung geplant</h1><p>Hallo {{ user_name }},</p><p>Ihr Konto wird am {{ deletion_date }} gelöscht, da es längere Zeit inaktiv war.</p><p>Falls Sie Ihr Konto behalten möchten, loggen Sie sich bis zu diesem Datum ein:</p><div style="text-align: center; margin: 30px 0;"><a href="{{ reactivate_url }}" style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">Konto reaktivieren</a></div></body></html>''',
        'slug': 'account-deletion-warning',
        'available_variables': 'user_name, deletion_date, reactivate_url, site_name',
        'is_default': False
    }
]

# Create all templates
created_count = 0
existing_count = 0

for template_data in templates_data:
    template, created = EmailTemplate.objects.get_or_create(
        slug=template_data['slug'],
        defaults={
            'name': template_data['name'],
            'template_type': template_data['template_type'],
            'subject': template_data['subject'],
            'html_content': template_data['html_content'],
            'available_variables': template_data['available_variables'],
            'is_active': True,
            'is_default': template_data.get('is_default', False)
        }
    )

    if created:
        created_count += 1
        print(f'✅ Created template: {template.name}')
    else:
        existing_count += 1
        print(f'ℹ️ Template already exists: {template.name}')

print(f'\n🎉 Summary:')
print(f'- Created {created_count} new templates')
print(f'- Found {existing_count} existing templates')
print(f'- Total templates: {EmailTemplate.objects.count()}')