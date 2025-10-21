#!/usr/bin/env python
"""
Setup-Script für MyPrompter App-Permission
Registriert MyPrompter in der Datenbank für die App-Freigabe-Verwaltung
"""

import os
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from accounts.models import AppPermission

def setup_myprompter_permission():
    """Erstellt oder aktualisiert die AppPermission für MyPrompter"""

    app_name = 'myprompter'

    permission, created = AppPermission.objects.update_or_create(
        app_name=app_name,
        defaults={
            'access_level': 'authenticated',  # Alle angemeldeten User
            'is_active': True,
            'hide_in_frontend': False,  # Sichtbar auf Startseite
        }
    )

    if created:
        print(f"✓ AppPermission für 'MyPrompter' wurde erstellt")
    else:
        print(f"✓ AppPermission für 'MyPrompter' wurde aktualisiert")

    print(f"  - App Name: {app_name}")
    print(f"  - Display Name: {permission.get_app_name_display()}")
    print(f"  - Access Level: {permission.get_access_level_display()}")
    print(f"  - Aktiv: {permission.is_active}")
    print(f"  - Sichtbar: {not permission.hide_in_frontend}")

if __name__ == '__main__':
    print("=" * 60)
    print("MyPrompter App-Permission Setup")
    print("=" * 60)

    try:
        setup_myprompter_permission()
        print("\n✓ Setup erfolgreich abgeschlossen!")
    except Exception as e:
        print(f"\n✗ Fehler beim Setup: {e}")
        import traceback
        traceback.print_exc()
