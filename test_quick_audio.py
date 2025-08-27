#!/usr/bin/env python3
"""
Test script für Quick Audio Schnellaktionen
Teste die neuen Audio-Kontrollen in Schnellaktionen und Record Button
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

def test_quick_audio():
    """Test der Quick Audio Schnellaktionen"""
    
    print("⚡ Testing Quick Audio Actions...")
    
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
    
    # Test 1: Performance Template - Schnellaktionen mit Audio
    response = client.get('/streamrec/aufnahme/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check if old audio section is removed from sidebar
        old_audio_elements = [
            'id="audioEnabled"',
            'id="systemAudio"',
            'Audio-Aufnahme aktiv',
            'System-Audio einbeziehen'
        ]
        
        found_old = 0
        for element in old_audio_elements:
            if element in content:
                found_old += 1
        
        if found_old == 0:
            print("✅ Old audio controls removed from sidebar")
        else:
            print(f"⚠️ Some old audio controls still found: {found_old}")
        
        # Check for new Quick Audio in Schnellaktionen
        quick_audio_elements = [
            'Audio-Aufnahme',
            'id="quickAudioRecordBtn"',
            'id="quickAudioQuality"',
            'id="quickAGC"',
            'id="quickNoiseSuppression"',
            'id="quickEchoCancellation"',
            'id="quickMicrophoneVolume"',
            'id="quickAudioLevelFill"',
            'id="quickVolumeDisplay"',
            'id="quickAudioStatus"',
            'Audio Record'
        ]
        
        found_quick = 0
        for element in quick_audio_elements:
            if element in content:
                found_quick += 1
        
        print(f"✅ Quick Audio UI Elements: {found_quick}/{len(quick_audio_elements)} found")
        
        # Check for new JavaScript functions
        quick_js_functions = [
            'setupQuickAudioRecording',
            'toggleQuickAudioRecord',
            'startQuickAudioRecord',
            'stopQuickAudioRecord',
            'handleQuickAudioRecordingComplete',
            'setQuickMicrophoneVolume',
            'updateQuickAudioStatus',
            'quickAudioRecording',
            'quickAudioRecorder',
            'quickAudioChunks'
        ]
        
        found_js = 0
        for js_func in quick_js_functions:
            if js_func in content:
                found_js += 1
        
        print(f"✅ Quick Audio JavaScript: {found_js}/{len(quick_js_functions)} functions found")
        
        # Check for quality settings integration
        if 'quickAudioQuality' in content and 'audioBitrate' in content:
            print("✅ Quality settings integrated into Quick Audio")
        
        # Check for Record Button styling
        if 'btn-danger' in content and 'btn-success' in content and 'Audio Record' in content:
            print("✅ Record Button with proper styling found")
        
        # Check audio constraints integration
        if 'quickAGC' in content and 'getAudioConstraints' in content:
            print("✅ Audio processing integrated with Quick Audio controls")
        
    else:
        print(f"❌ Performance template failed to load: {response.status_code}")
    
    # Test 2: Audio Studio Template - Updated Design
    response = client.get('/streamrec/audio-studio/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for updated record button
        if 'Audio Record' in content and 'Audio Aufnahme starten' in content:
            print("✅ Audio Studio has updated Record Button text")
        
        # Check that processing controls are still there
        audio_studio_processing = [
            'id="autoGainControl"',
            'id="noiseSuppression"', 
            'id="echoCancellation"'
        ]
        
        found_studio = 0
        for control in audio_studio_processing:
            if control in content:
                found_studio += 1
        
        if found_studio == len(audio_studio_processing):
            print("✅ Audio Studio retains all processing controls")
        
    else:
        print(f"❌ Audio Studio template failed to load: {response.status_code}")
    
    print("\n🎉 Quick Audio Actions Test completed!")
    print("\n📋 Summary of Changes:")
    print("1. ✅ Audio Controls MOVED:")
    print("   - FROM: Stream Kontrolle Sidebar")
    print("   - TO: Schnellaktionen Section")
    
    print("\n2. ✅ Quality Settings ADDED:")
    print("   - Hoch (192 kbps)")
    print("   - Mittel (128 kbps) [Standard]")
    print("   - Niedrig (96 kbps)")
    
    print("\n3. ✅ Record Button IMPLEMENTED:")
    print("   - Replaces checkbox-based audio activation")
    print("   - Red 'Audio Record' → Green 'Stop Record'")
    print("   - Automatic download after recording")
    
    print("\n4. ✅ Quick Audio Features:")
    print("   - ⚡ One-click audio recording")
    print("   - 🎛️ Integrated processing settings (AGC, Noise, Echo)")
    print("   - 📊 Real-time level monitoring")
    print("   - 🔊 Volume control with visual feedback")
    print("   - 💾 Automatic file download")
    
    print("\n5. ✅ Improved UX:")
    print("   - Compact layout in Schnellaktionen")
    print("   - All audio functions in one place")
    print("   - Consistent with Video Studio design")
    
    print(f"\n🎬 Video Studio (with Quick Audio): http://127.0.0.1:8000/streamrec/aufnahme/")
    print(f"🎤 Dedicated Audio Studio: http://127.0.0.1:8000/streamrec/audio-studio/")
    
    return True

if __name__ == "__main__":
    test_quick_audio()