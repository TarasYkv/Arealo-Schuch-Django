#!/usr/bin/env python
"""
Setup Script für Bug-Chat Superuser auf dem Server
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from accounts.models import CustomUser

def setup_bug_superuser():
    """Setzt den ersten Admin-User als Bug-Chat Superuser"""
    
    print("🐛 Bug-Chat Superuser Setup")
    print("=" * 40)
    
    # Finde Admin/Staff User
    admin_users = CustomUser.objects.filter(is_staff=True)
    
    if not admin_users.exists():
        print("❌ Keine Admin-User gefunden!")
        print("Erstellen Sie zuerst einen Admin-User mit:")
        print("  python manage.py createsuperuser")
        return
    
    print(f"Gefundene Admin-User: {admin_users.count()}")
    
    # Aktiviere Bug-Chat für alle Admins
    updated_count = 0
    for admin in admin_users:
        if not admin.is_bug_chat_superuser:
            admin.is_bug_chat_superuser = True
            admin.receive_bug_reports = True
            admin.receive_anonymous_reports = True
            admin.save()
            updated_count += 1
            print(f"✅ {admin.username} - Bug-Chat Superuser aktiviert")
        else:
            print(f"ℹ️  {admin.username} - Bereits Bug-Chat Superuser")
    
    if updated_count > 0:
        print(f"\n✅ {updated_count} User zu Bug-Chat Superuser gemacht!")
    else:
        print("\nℹ️  Alle Admin-User sind bereits Bug-Chat Superuser")
    
    # Zeige aktuellen Status
    print("\n📊 Aktueller Status:")
    bug_superusers = CustomUser.objects.filter(is_bug_chat_superuser=True)
    for user in bug_superusers:
        print(f"• {user.username}: Bug-Reports={user.receive_bug_reports}, "
              f"Anonyme={user.receive_anonymous_reports}")

if __name__ == '__main__':
    setup_bug_superuser()