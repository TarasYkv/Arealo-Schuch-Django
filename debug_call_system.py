#!/usr/bin/env python3
"""
Debug call system issues
"""
import os
import sys
import django
from django.conf import settings
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

User = get_user_model()

def debug_call_system():
    """Debug the call system step by step"""
    
    print("=== DEBUGGING CALL SYSTEM ===\n")
    
    # 1. Check if models are accessible
    print("1. Checking models...")
    try:
        from chat.models import ChatRoom, Call, CallParticipant
        print("✓ Models imported successfully")
    except Exception as e:
        print(f"✗ Error importing models: {e}")
        return False
    
    # 2. Check if users exist
    print("\n2. Checking users...")
    try:
        users = User.objects.all()[:5]
        print(f"✓ Found {User.objects.count()} users")
        for user in users:
            print(f"  - {user.username} (ID: {user.id})")
    except Exception as e:
        print(f"✗ Error accessing users: {e}")
        return False
    
    # 3. Check if chat rooms exist
    print("\n3. Checking chat rooms...")
    try:
        rooms = ChatRoom.objects.all()[:5]
        print(f"✓ Found {ChatRoom.objects.count()} chat rooms")
        for room in rooms:
            print(f"  - Room {room.id}: {room.name or 'Private chat'}")
    except Exception as e:
        print(f"✗ Error accessing chat rooms: {e}")
        return False
    
    # 4. Test call initiation API
    print("\n4. Testing call initiation API...")
    
    # Create a test client
    client = Client()
    
    # Get or create a test user
    test_user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'password': 'testpass123'}
    )
    print(f"✓ Test user: {test_user.username} (created: {created})")
    
    # Login the test user
    client.force_login(test_user)
    print("✓ Test user logged in")
    
    # Get or create a test room
    test_room = ChatRoom.objects.filter(participants=test_user).first()
    if not test_room:
        print("  Creating test room...")
        test_room = ChatRoom.objects.create(
            created_by=test_user,
            is_group_chat=False
        )
        test_room.participants.add(test_user)
        print(f"✓ Created test room: {test_room.id}")
    else:
        print(f"✓ Using existing test room: {test_room.id}")
    
    # 5. Test call initiation endpoint
    print("\n5. Testing call initiation endpoint...")
    try:
        url = reverse('chat:initiate_call', kwargs={'room_id': test_room.id})
        print(f"  URL: {url}")
        
        response = client.post(url, 
            data=json.dumps({'call_type': 'audio'}),
            content_type='application/json'
        )
        
        print(f"  Response status: {response.status_code}")
        print(f"  Response content: {response.content.decode()}")
        
        if response.status_code == 200:
            response_data = json.loads(response.content)
            if response_data.get('success'):
                print("✓ Call initiation API works")
                call_id = response_data.get('call_id')
                print(f"  Call ID: {call_id}")
                
                # Check if call was created in database
                try:
                    call = Call.objects.get(id=call_id)
                    print(f"✓ Call found in database: {call.status}")
                except Call.DoesNotExist:
                    print("✗ Call not found in database")
                    return False
                
            else:
                print(f"✗ Call initiation failed: {response_data.get('error')}")
                return False
        else:
            print(f"✗ Call initiation API failed with status {response.status_code}")
            return False
    
    except Exception as e:
        print(f"✗ Error testing call initiation: {e}")
        return False
    
    # 6. Check WebSocket routing
    print("\n6. Checking WebSocket routing...")
    try:
        from chat.routing import websocket_urlpatterns
        print(f"✓ WebSocket URL patterns loaded: {len(websocket_urlpatterns)} patterns")
        for pattern in websocket_urlpatterns:
            print(f"  - {pattern.pattern}")
    except Exception as e:
        print(f"✗ Error loading WebSocket routing: {e}")
        return False
    
    # 7. Check consumers
    print("\n7. Checking consumers...")
    try:
        from chat.consumers import CallConsumer
        print("✓ CallConsumer imported successfully")
        
        # Check if consumer has required methods
        methods = ['connect', 'receive', 'handle_call_initiate']
        for method in methods:
            if hasattr(CallConsumer, method):
                print(f"  ✓ {method} method exists")
            else:
                print(f"  ✗ {method} method missing")
                return False
                
    except Exception as e:
        print(f"✗ Error checking consumers: {e}")
        return False
    
    # 8. Check settings
    print("\n8. Checking Django settings...")
    try:
        channel_layers = getattr(settings, 'CHANNEL_LAYERS', {})
        if channel_layers:
            print(f"✓ CHANNEL_LAYERS configured: {list(channel_layers.keys())}")
        else:
            print("✗ CHANNEL_LAYERS not configured")
            return False
            
        installed_apps = getattr(settings, 'INSTALLED_APPS', [])
        if 'channels' in installed_apps:
            print("✓ channels app installed")
        else:
            print("✗ channels app not installed")
            return False
            
    except Exception as e:
        print(f"✗ Error checking settings: {e}")
        return False
    
    print("\n=== CALL SYSTEM DEBUG COMPLETE ===")
    print("✓ All basic components are working correctly")
    print("\nPossible issues:")
    print("1. WebSocket authentication - users may not be authenticated properly")
    print("2. Frontend JavaScript errors - check browser console")
    print("3. WebSocket server connection issues - check if daphne is running")
    print("4. Network/firewall issues blocking WebSocket connections")
    
    return True

if __name__ == "__main__":
    debug_call_system()