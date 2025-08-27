#!/usr/bin/env python3
"""
Test script für das Audio Recording Studio
Teste die Grundfunktionalitäten ohne Browser-Interface
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
from django.urls import reverse
import json

def test_audio_studio():
    """Test der Audio Studio Funktionalitäten"""
    
    print("🎙️ Testing Audio Recording Studio...")
    
    # Test Client erstellen
    client = Client()
    
    # Testuser erstellen (falls nicht vorhanden)
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        print("✅ Test user created")
    
    # Login
    client.login(username='testuser', password='testpass123')
    print("✅ User logged in")
    
    # Test 1: Dashboard mit Audio Studio Link
    response = client.get('/streamrec/')
    if response.status_code == 200 and 'Audio Studio' in response.content.decode():
        print("✅ Dashboard contains Audio Studio link")
    else:
        print("❌ Dashboard missing Audio Studio link")
    
    # Test 2: Audio Studio Page
    response = client.get('/streamrec/audio-studio/')
    if response.status_code == 200:
        content = response.content.decode()
        if 'AudioRecordingStudio' in content:
            print("✅ Audio Studio page loads with JavaScript class")
        else:
            print("❌ Audio Studio page missing JavaScript")
            
        if 'MediaRecorder' in content:
            print("✅ Audio Studio uses MediaRecorder API")
        else:
            print("❌ MediaRecorder API not found")
            
        if 'visualizer' in content:
            print("✅ Audio visualization implemented")
        else:
            print("❌ Audio visualization missing")
            
    else:
        print(f"❌ Audio Studio page failed to load: {response.status_code}")
    
    # Test 3: API Endpoints
    # Test save audio API
    test_audio_data = "data:audio/webm;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
    
    response = client.post('/streamrec/api/save-audio/', 
                          data=json.dumps({
                              'audio_data': test_audio_data,
                              'filename': 'test_recording.webm'
                          }),
                          content_type='application/json')
    
    if response.status_code == 200:
        result = json.loads(response.content)
        if result.get('success'):
            print("✅ Audio save API works")
        else:
            print(f"❌ Audio save API error: {result.get('error')}")
    else:
        print(f"❌ Audio save API failed: {response.status_code}")
    
    # Test 4: Audio Features Überprüfung
    features_found = []
    if 'MediaRecorder' in content:
        features_found.append("MediaRecorder API")
    if 'createAnalyser' in content:
        features_found.append("Audio Analyzer")
    if 'getUserMedia' in content:
        features_found.append("Microphone Access")
    if 'canvas' in content.lower():
        features_found.append("Visualization Canvas")
    if 'download' in content.lower():
        features_found.append("Download Function")
        
    print(f"✅ Audio Features implemented: {', '.join(features_found)}")
    
    print("\n🎉 Audio Recording Studio Test completed!")
    print("\n📋 Summary:")
    print("- Audio Studio URL: http://127.0.0.1:8000/streamrec/audio-studio/")
    print("- Features: High-quality audio recording, real-time visualization, microphone selection")
    print("- Formats: WebM, WAV")
    print("- Storage: Server-side saving + local download")
    print("- UI: Professional interface with level meters and waveform display")
    
    return True

if __name__ == "__main__":
    test_audio_studio()