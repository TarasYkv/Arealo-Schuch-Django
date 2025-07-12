#!/usr/bin/env python3
"""
WebSocket Test Script für PythonAnywhere Deployment
Testet alle WebSocket Endpoints
"""

import asyncio
import websockets
import json
import sys

async def test_websocket_endpoint(uri, test_name):
    """Test ein WebSocket Endpoint"""
    print(f"\n🔌 Testing {test_name}: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ {test_name}: Connection successful")
            
            # Test message senden
            test_message = {
                "type": "test",
                "message": "Hello from test script"
            }
            
            await websocket.send(json.dumps(test_message))
            print(f"📤 {test_name}: Test message sent")
            
            # Warten auf Response (mit Timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 {test_name}: Received response")
            except asyncio.TimeoutError:
                print(f"⏰ {test_name}: No response received (timeout)")
            
            return True
            
    except Exception as e:
        print(f"❌ {test_name}: Connection failed - {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting WebSocket Tests for PythonAnywhere")
    print("=" * 50)
    
    # Test URLs
    base_ws = "ws://127.0.0.1:8001"
    base_wss = "wss://workloom.de"
    
    test_room_id = "1"
    
    endpoints = [
        (f"{base_ws}/ws/call/{test_room_id}/", "Call WebSocket (Local)"),
        (f"{base_ws}/ws/chat/{test_room_id}/", "Chat WebSocket (Local)"),
        (f"{base_ws}/ws/notifications/", "Notifications WebSocket (Local)"),
        # Production URLs (für später)
        # (f"{base_wss}/ws/call/{test_room_id}/", "Call WebSocket (Production)"),
        # (f"{base_wss}/ws/chat/{test_room_id}/", "Chat WebSocket (Production)"),
        # (f"{base_wss}/ws/notifications/", "Notifications WebSocket (Production)"),
    ]
    
    results = []
    
    for uri, test_name in endpoints:
        success = await test_websocket_endpoint(uri, test_name)
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All WebSocket endpoints are working!")
        return 0
    else:
        print("⚠️  Some WebSocket endpoints failed. Check your server configuration.")
        return 1

if __name__ == "__main__":
    # Überprüfen ob WebSocket Server läuft
    print("🔍 Make sure your WebSocket server is running:")
    print("   Local: daphne -p 8001 Schuch.asgi:application")
    print("   Or: ./start_websocket.sh")
    print()
    
    # Tests ausführen
    exit_code = asyncio.run(main())
    sys.exit(exit_code)