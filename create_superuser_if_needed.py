#!/usr/bin/env python
"""
Script um automatisch einen Superuser zu erstellen falls keiner existiert.
Kann in Deployment-Scripts verwendet werden.
"""

import os
import sys
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_superuser_if_needed():
    """Erstellt einen Superuser falls noch keiner existiert"""
    
    # Prüfe ob bereits ein Superuser existiert
    if User.objects.filter(is_superuser=True).exists():
        print("✅ Superuser existiert bereits!")
        return
    
    # Environment Variables
    username = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
    email = os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_ADMIN_PASSWORD')
    
    if not password:
        print("❌ DJANGO_ADMIN_PASSWORD Environment Variable nicht gesetzt!")
        print("Setzen Sie: export DJANGO_ADMIN_PASSWORD='your-secure-password'")
        return
    
    try:
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"✅ Superuser '{username}' erfolgreich erstellt!")
        
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Superusers: {e}")

if __name__ == '__main__':
    create_superuser_if_needed()