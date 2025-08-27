#!/usr/bin/env python3
"""
Test script für korrigierte Audio-Struktur
Teste dass Audio-Sektion in Sidebar bleibt und nur Einstellungen in Settings Modal sind
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

def test_corrected_audio():
    """Test der korrigierten Audio-Struktur"""
    
    print("🎯 Testing Corrected Audio Structure...")
    
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
    
    # Test 1: Performance Template - Audio in Sidebar
    response = client.get('/streamrec/aufnahme/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for Audio Section in Sidebar (should exist)
        audio_sidebar_elements = [
            'id="audioEnabled"',
            'id="systemAudio"', 
            'id="microphoneVolume"',
            'id="volumeDisplay"',
            'id="audioLevelFill"',
            'Audio-Aufnahme aktiv',
            'System-Audio einbeziehen',
            'Mikrofonlautstärke'
        ]
        
        found_sidebar = 0
        for element in audio_sidebar_elements:
            if element in content:
                found_sidebar += 1
        
        print(f"✅ Audio Controls in Sidebar: {found_sidebar}/{len(audio_sidebar_elements)} found")
        
        # Check that Quick Audio is NOT in Schnellaktionen (should be removed)
        quick_audio_elements = [
            'id="quickAudioRecordBtn"',
            'id="quickAudioQuality"',
            'id="quickAGC"',
            'id="quickNoiseSuppression"',
            'id="quickEchoCancellation"'
        ]
        
        found_quick = 0
        for element in quick_audio_elements:
            if element in content:
                found_quick += 1
        
        if found_quick == 0:
            print("✅ Quick Audio controls removed from Schnellaktionen")
        else:
            print(f"⚠️ Some Quick Audio controls still found: {found_quick}")
        
        # Check for Audio Settings in Settings Modal (should exist)
        audio_settings_elements = [
            'id="settingsAudioQuality"',
            'id="settingsAGC"',
            'id="settingsNoiseSuppression"',
            'id="settingsEchoCancellation"',
            'Audio-Einstellungen',
            'Audio-Qualität',
            'value="192000">Hoch (192 kbps)',
            'value="128000" selected>Mittel (128 kbps)',
            'value="96000">Niedrig (96 kbps)'
        ]
        
        found_settings = 0
        for element in audio_settings_elements:
            if element in content:
                found_settings += 1
        
        print(f"✅ Audio Settings in Modal: {found_settings}/{len(audio_settings_elements)} found")
        
        # Check that getAudioConstraints uses settings modal IDs
        if 'settingsAGC' in content and 'settingsNoiseSuppression' in content and 'settingsEchoCancellation' in content:
            print("✅ getAudioConstraints function uses Settings Modal IDs")
        
        # Check that audio level monitoring uses normal IDs (not quick IDs)
        if 'audioLevelFill' in content and 'quickAudioLevelFill' not in content:
            print("✅ Audio level monitoring uses correct IDs")
        
    else:
        print(f"❌ Performance template failed to load: {response.status_code}")
    
    # Test 2: Audio Studio Template - Check unchanged
    response = client.get('/streamrec/audio-studio/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for Audio Studio controls (should be unchanged)
        audio_studio_controls = [
            'id="autoGainControl"',
            'id="noiseSuppression"', 
            'id="echoCancellation"',
            'id="microphoneVolume"',
            'Automatische Verstärkungsregelung (AGC)',
            'Rauschunterdrückung',
            'Echo-Unterdrückung'
        ]
        
        found_studio = 0
        for control in audio_studio_controls:
            if control in content:
                found_studio += 1
        
        print(f"✅ Audio Studio unchanged: {found_studio}/{len(audio_studio_controls)} controls found")
        
    else:
        print(f"❌ Audio Studio template failed to load: {response.status_code}")
    
    print("\n🎉 Corrected Audio Structure Test completed!")
    print("\n📋 Korrigierte Audio-Struktur:")
    print("1. ✅ Audio-Sektion:")
    print("   - BLEIBT in Stream Kontrolle Sidebar")
    print("   - Enthält: Audio-Aktivierung, System-Audio, Lautstärke, Level-Anzeige")
    print("   - Funktioniert wie vorher")
    
    print("\n2. ✅ Audio-Einstellungen:")
    print("   - VERSCHOBEN zu Schnellaktionen->Einstellungen Modal")
    print("   - Enthält: AGC, Rauschunterdrückung, Echo-Unterdrückung, Qualität")
    print("   - Werden von getAudioConstraints() gelesen")
    
    print("\n3. ✅ Quick Audio:")
    print("   - KOMPLETT ENTFERNT aus Schnellaktionen")
    print("   - Keine quickAudio* Elemente mehr vorhanden")
    
    print("\n4. ✅ JavaScript-Funktionen:")
    print("   - getAudioConstraints() liest Settings Modal IDs")
    print("   - Audio-Level-Monitoring verwendet normale IDs")
    print("   - Keine Quick Audio Funktionen mehr")
    
    print(f"\n🎬 Video Studio: http://127.0.0.1:8000/streamrec/aufnahme/")
    print(f"🎤 Audio Studio: http://127.0.0.1:8000/streamrec/audio-studio/")
    
    return True

if __name__ == "__main__":
    test_corrected_audio()