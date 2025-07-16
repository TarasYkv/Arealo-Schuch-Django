from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket support for WebRTC signaling only
    re_path(r'ws/call/(?P<room_id>\w+)/$', consumers.CallConsumer.as_asgi()),
]