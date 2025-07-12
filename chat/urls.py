from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Main chat pages
    path('', views.chat_home, name='home'),
    path('room/<int:room_id>/', views.redirect_to_chat, name='room_detail'),
    path('start/<int:user_id>/', views.start_chat, name='start_chat'),
    path('search/', views.user_search, name='user_search'),
    path('group/create/', views.create_group_chat, name='create_group_chat'),
    
    # AJAX endpoints
    path('api/room/<int:room_id>/send/', views.send_message, name='send_message'),
    path('api/room/<int:room_id>/messages/', views.get_messages, name='get_messages'),
    path('api/room/<int:room_id>/mark_read/', views.mark_messages_read, name='mark_messages_read'),
    path('unread-count/', views.get_unread_count, name='get_unread_count'),
    path('update-online-status/', views.update_online_status, name='update_online_status'),
    path('set-offline/', views.set_offline, name='set_offline'),
    path('api/room/<int:room_id>/delete/', views.delete_chat, name='delete_chat'),
    path('api/room/<int:room_id>/info/', views.get_chat_info, name='get_chat_info'),
    path('api/room/<int:room_id>/call/initiate/', views.initiate_call, name='initiate_call'),
    path('api/call/<int:call_id>/end/', views.end_call, name='end_call'),
    path('api/room/<int:room_id>/calls/', views.get_call_history, name='get_call_history'),
    
    # Agora Video/Audio calls
    path('get-agora-token/', views.get_agora_token, name='get_agora_token'),
    
    # Test pages
    path('websocket-test/', views.websocket_test, name='websocket_test'),
    path('test-call/', views.test_call, name='test_call'),
]