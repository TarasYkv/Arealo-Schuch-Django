#!/usr/bin/env python3
"""
Test WebSocket connection to debug call system
"""
import asyncio
import websockets
import json
import sys

async def test_websocket_connection():
    # Test WebSocket connection
    uri = "ws://127.0.0.1:8001/ws/call/1/"
    
    try:
        print("Attempting to connect to WebSocket server...")
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket server successfully!")
            
            # Send a test message
            test_message = {
                "type": "test",
                "message": "Hello WebSocket!"
            }
            
            await websocket.send(json.dumps(test_message))
            print("✓ Test message sent")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"✓ Received response: {response}")
            except asyncio.TimeoutError:
                print("⚠ No response received within 5 seconds")
                
    except Exception as e:
        print(f"✗ WebSocket connection failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing WebSocket connection for call system...")
    success = asyncio.run(test_websocket_connection())
    
    if success:
        print("\n✓ WebSocket connection test passed")
        sys.exit(0)
    else:
        print("\n✗ WebSocket connection test failed")
        sys.exit(1)