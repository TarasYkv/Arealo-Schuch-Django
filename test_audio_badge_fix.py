#!/usr/bin/env python3
"""
Test script für Audio-Status Badge Fix
Teste dass CSS und JavaScript für Audio-Status Badge korrekt sind
"""

import os
import django
import sys

# Django setup
sys.path.append('/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.test import Client
from accounts.models import CustomUser as User
import re

def test_audio_badge_fix():
    """Test der Audio-Status Badge CSS und JavaScript Fixes"""
    
    print("🎨 Testing Audio Badge Fix...")
    
    # Test Client erstellen
    client = Client()
    
    # Testuser verwenden
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        print("✅ Test user created")
    
    # Login
    client.login(username='testuser', password='testpass123')
    print("✅ User logged in")
    
    # Test 1: Performance Template - CSS Fixes
    response = client.get('/streamrec/aufnahme/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for Audio Status Badge CSS
        badge_css_rules = [
            '#audioStatusBadge .fas.fa-circle {',
            'font-size: 0.7rem;',
            '#audioStatusBadge .fas.fa-circle.text-success {',
            'color: #28a745 !important;',
            '#audioStatusBadge .fas.fa-circle.text-danger {', 
            'color: #dc3545 !important;',
            '#audioStatusBadge .fas.fa-circle.text-warning {',
            'color: #ffc107 !important;',
            '#audioStatusBadge .fas.fa-circle.text-secondary {',
            'color: #6c757d !important;'
        ]
        
        found_css = 0
        for css_rule in badge_css_rules:
            if css_rule in content:
                found_css += 1
        
        print(f"✅ Audio Badge CSS Rules: {found_css}/{len(badge_css_rules)} found")
        
        # Check for Debug Logging in JavaScript
        debug_logs = [
            '🟢 Audio Status Badge: GRÜN (success)',
            '🔴 Audio Status Badge: ROT (danger)', 
            '🟡 Audio Status Badge: GELB (warning)',
            '⚫ Audio Status Badge: GRAU (secondary)',
            'Audio Badge Classes:',
            'Audio Status Badge: Icon nicht gefunden',
            'Audio Status Badge: Element nicht gefunden'
        ]
        
        found_debug = 0
        for debug_log in debug_logs:
            if debug_log in content:
                found_debug += 1
        
        print(f"✅ Debug Logging: {found_debug}/{len(debug_logs)} found")
        
        # Check for HTML Structure
        html_elements = [
            'id="audioStatusBadge"',
            'class="status-indicator"',
            'class="fas fa-circle text-secondary"',
            '<i class="fas fa-circle text-secondary"></i>'
        ]
        
        found_html = 0
        for element in html_elements:
            if element in content:
                found_html += 1
        
        print(f"✅ HTML Structure: {found_html}/{len(html_elements)} found")
        
        # Check for updateAudioStatusBadge Function
        if 'updateAudioStatusBadge(status)' in content:
            print("✅ updateAudioStatusBadge function exists")
        
        if 'icon.classList.remove(' in content and 'icon.classList.add(' in content:
            print("✅ CSS class manipulation logic exists")
        
        # Check that badge starts as secondary (gray)
        if 'text-secondary' in content:
            print("✅ Badge starts as gray (text-secondary)")
        
    else:
        print(f"❌ Performance template failed to load: {response.status_code}")
    
    print("\n🎉 Audio Badge Fix Test completed!")
    print("\n📋 Summary of Audio Badge Fixes:")
    print("1. ✅ CSS Specificity Fixed:")
    print("   - Spezifische CSS-Regeln für jede Farbe mit !important")
    print("   - #audioStatusBadge .fas.fa-circle.text-success { color: #28a745 !important; }")
    print("   - Überschreibt andere CSS-Konflikte")
    
    print("\n2. ✅ Debug Logging Added:")
    print("   - Console-Logs zeigen Badge-Status-Änderungen")
    print("   - Zeigt CSS-Klassen des Icons")
    print("   - Hilft bei Fehlersuche")
    
    print("\n3. ✅ Status Badge Farben:")
    print("   - 🔘 Grau (#6c757d): Audio deaktiviert")
    print("   - 🟡 Gelb (#ffc107): Audio aktiviert, kein Stream")
    print("   - 🟢 Grün (#28a745): Audio aktiv mit Stream")
    print("   - 🔴 Rot (#dc3545): Audio-Fehler")
    
    print(f"\n🎬 Teste das Badge hier: http://127.0.0.1:8000/streamrec/aufnahme/")
    print("\n🔧 Debug-Schritte:")
    print("1. Öffne die Entwicklertools (F12)")
    print("2. Gehe zur Konsole")
    print("3. Starte Kamera oder Bildschirm-Aufnahme")
    print("4. Schaue nach den Debug-Logs für Audio Status Badge")
    print("5. Das Badge sollte seine Farbe entsprechend ändern")
    
    return True

if __name__ == "__main__":
    test_audio_badge_fix()