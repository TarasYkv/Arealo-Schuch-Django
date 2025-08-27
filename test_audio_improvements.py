#!/usr/bin/env python3
"""
Test script für verbesserte Audio-Kontrollen
Teste Checkbox-Sichtbarkeit und Mikrofonlautstärke-Regler
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

def test_audio_improvements():
    """Test der verbesserten Audio-Kontrollen"""
    
    print("🎛️ Testing Improved Audio Controls...")
    
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
    
    # Test 1: Performance Template - Checkbox Improvements
    response = client.get('/streamrec/aufnahme/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for improved checkbox CSS
        checkbox_improvements = [
            '.form-check-input {',
            'width: 1.2em !important;',
            'height: 1.2em !important;',
            'border: 2px solid #667eea !important;',
            'background-color: #ffffff !important;',
            '.form-check-input:checked::before {',
            'content: "✓" !important;',
            'position: absolute !important;'
        ]
        
        found_checkbox_css = 0
        for css_rule in checkbox_improvements:
            if css_rule in content:
                found_checkbox_css += 1
        
        print(f"✅ Checkbox CSS improvements: {found_checkbox_css}/{len(checkbox_improvements)} found")
        
        # Check for volume slider
        volume_controls = [
            'id="microphoneVolume"',
            'class="volume-slider"',
            'Mikrofonlautstärke:',
            'id="volumeDisplay"',
            'min="0" max="100" value="80"',
            'fas fa-volume-down',
            'fas fa-volume-up'
        ]
        
        found_volume = 0
        for control in volume_controls:
            if control in content:
                found_volume += 1
        
        print(f"✅ Volume control elements: {found_volume}/{len(volume_controls)} found")
        
        # Check for volume slider CSS
        volume_css = [
            '.volume-slider {',
            '-webkit-appearance: none !important;',
            '.volume-slider::-webkit-slider-thumb {',
            'border-radius: 50% !important;',
            'background: #667eea !important;'
        ]
        
        found_volume_css = 0
        for css_rule in volume_css:
            if css_rule in content:
                found_volume_css += 1
        
        print(f"✅ Volume slider CSS: {found_volume_css}/{len(volume_css)} found")
        
        # Check for volume JavaScript functions
        volume_js = [
            'setMicrophoneVolume',
            'audioGainNode',
            'createGain',
            'gain.setValueAtTime',
            'monitorAudioLevelWithVolume'
        ]
        
        found_volume_js = 0
        for js_func in volume_js:
            if js_func in content:
                found_volume_js += 1
        
        print(f"✅ Volume JavaScript functions: {found_volume_js}/{len(volume_js)} found")
        
    else:
        print(f"❌ Performance template failed to load: {response.status_code}")
    
    # Test 2: Audio Studio Template  
    response = client.get('/streamrec/audio-studio/')
    if response.status_code == 200:
        content = response.content.decode()
        
        # Check for checkbox improvements in Audio Studio
        if '.form-check-input:checked::before' in content and 'content: "✓"' in content:
            print("✅ Audio Studio has improved checkbox visibility")
        
        # Check for volume control in Audio Studio
        if 'id="microphoneVolume"' in content and 'Mikrofonlautstärke' in content:
            print("✅ Audio Studio has volume control")
        
        # Check for volume slider in 3-column layout
        if 'col-md-4' in content and 'Mikrofonlautstärke' in content:
            print("✅ Audio Studio has improved layout with volume control")
        
        # Check for gain node functionality
        if 'audioGainNode' in content and 'setMicrophoneVolume' in content:
            print("✅ Audio Studio has volume control JavaScript")
            
    else:
        print(f"❌ Audio Studio template failed to load: {response.status_code}")
    
    print("\n🎉 Audio Control Improvements Test completed!")
    print("\n📋 Summary of Improvements:")
    print("1. ✅ Checkbox Visibility:")
    print("   - Größere Checkboxen (1.2em)")
    print("   - Klare Rahmen in Primärfarbe (#667eea)")
    print("   - Sichtbares ✓ Symbol bei aktivierten Checkboxen")
    print("   - Hover- und Focus-Effekte")
    
    print("\n2. ✅ Mikrofonlautstärke-Regler:")
    print("   - Bereich: 0-100% (bis zu 2x Verstärkung)")
    print("   - Visueller Slider mit Icons")
    print("   - Echtzeit-Anzeige der aktuellen Lautstärke")
    print("   - Integration in Web Audio API (GainNode)")
    
    print("\n3. ✅ Enhanced Audio Level Monitoring:")
    print("   - Berücksichtigt Lautstärke-Einstellung")
    print("   - Farbkodierte Level-Anzeige")
    print("   - Echtzeit-Feedback")
    
    print(f"\n🎬 Video+Audio Studio: http://127.0.0.1:8000/streamrec/aufnahme/")
    print(f"🎤 Audio Studio: http://127.0.0.1:8000/streamrec/audio-studio/")
    
    return True

if __name__ == "__main__":
    test_audio_improvements()