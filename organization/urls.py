from django.urls import path
from . import views

app_name = 'organization'

urlpatterns = [
    # Dashboard
    path('', views.organization_dashboard, name='dashboard'),
    
    # Notizen
    path('notes/', views.note_list, name='note_list'),
    path('notes/<int:pk>/', views.note_detail, name='note_detail'),
    path('notes/create/', views.note_create, name='note_create'),
    path('notes/<int:pk>/edit/', views.note_edit, name='note_edit'),
    
    # Kalender & Termine
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('events/create/', views.event_create, name='event_create'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:pk>/respond/', views.event_respond, name='event_respond'),
    
    # Ideenboards
    path('boards/', views.board_list, name='board_list'),
    path('boards/<int:pk>/', views.board_detail, name='board_detail'),
    path('boards/create/', views.board_create, name='board_create'),
    path('boards/<int:pk>/save-element/', views.board_save_element, name='board_save_element'),
    path('boards/<int:pk>/elements/', views.board_get_elements, name='board_get_elements'),
    path('boards/<int:pk>/update-element/', views.board_update_element, name='board_update_element'),
    path('boards/<int:pk>/upload-image/', views.board_upload_image, name='board_upload_image'),
    path('boards/<int:pk>/clear-elements/', views.board_clear_elements, name='board_clear_elements'),
    path('boards/<int:pk>/elements/<int:element_id>/delete/', views.board_delete_element, name='board_delete_element'),
    path('boards/<int:pk>/invite-collaborators/', views.board_invite_collaborators, name='board_invite_collaborators'),
    path('boards/<int:pk>/remove-collaborator/', views.board_remove_collaborator, name='board_remove_collaborator'),

    # Board Audio
    path('boards/<int:pk>/audio/join/', views.board_audio_join, name='board_audio_join'),
    path('boards/<int:pk>/audio/leave/', views.board_audio_leave, name='board_audio_leave'),
    path('boards/<int:pk>/audio/token/', views.board_audio_token, name='board_audio_token'),
    path('boards/<int:pk>/audio/status/', views.board_audio_status, name='board_audio_status'),
    path('boards/<int:pk>/audio/mute/', views.board_audio_mute, name='board_audio_mute'),

    # Board Mirror
    path('boards/<int:pk>/mirror/start/', views.board_mirror_start, name='board_mirror_start'),
    path('boards/<int:pk>/mirror/stop/', views.board_mirror_stop, name='board_mirror_stop'),
    path('boards/<int:pk>/mirror/status/', views.board_mirror_status, name='board_mirror_status'),
    path('boards/<int:pk>/mirror/token/', views.board_mirror_token, name='board_mirror_token'),

    # Board Notes
    path('boards/<int:pk>/update-notes/', views.board_update_notes, name='board_update_notes'),
    path('boards/<int:pk>/get-notes/', views.board_get_notes, name='board_get_notes'),

    # Video/Audio Calls
    path('calls/', views.call_start_page, name='call_start_page'),
    path('calls/start/', views.call_start, name='call_start'),
    path('calls/<uuid:call_id>/', views.call_join, name='call_join'),
    path('calls/<uuid:call_id>/end/', views.call_end, name='call_end'),
    path('calls/<uuid:call_id>/leave/', views.call_leave, name='call_leave'),
    path('calls/<uuid:call_id>/status/', views.call_status, name='call_status'),
    
    # Chat/Kommunikation (von chat app verschoben)
    path('chat/', views.chat_home, name='chat_home'),
    path('chat/schuch-dashboard/', views.schuch_dashboard, name='schuch_dashboard'),
    path('chat/room/<int:room_id>/', views.redirect_to_chat, name='room_detail'),
    path('chat/start/<int:user_id>/', views.start_chat, name='start_chat'),
    path('chat/search/', views.chat_user_search, name='chat_user_search'),
    path('chat/group/create/', views.create_group_chat, name='create_group_chat'),

    # Chat AJAX endpoints
    path('chat/api/batch/<int:room_id>/', views.batch_update, name='batch_update'),
    path('chat/api/room/<int:room_id>/send/', views.send_message, name='send_message'),
    path('chat/api/room/<int:room_id>/messages/', views.get_messages, name='get_messages'),
    path('chat/api/room/<int:room_id>/mark_read/', views.mark_messages_read, name='mark_messages_read'),
    path('chat/unread-count/', views.get_unread_count, name='get_unread_count'),
    path('chat/update-online-status/', views.update_online_status, name='update_online_status'),
    path('chat/set-offline/', views.set_offline, name='set_offline'),
    path('chat/api/room/<int:room_id>/delete/', views.delete_chat, name='delete_chat'),
    path('chat/api/room/<int:room_id>/info/', views.get_chat_info, name='get_chat_info'),
    path('chat/api/room/<int:room_id>/export-pdf/', views.export_chat_pdf, name='export_chat_pdf'),

    # API
    path('api/user-search/', views.user_search, name='user_search'),
    path('api/check-incoming-calls/', views.check_incoming_calls, name='check_incoming_calls'),
    path('api/get-agora-token/', views.get_agora_token, name='get_agora_token'),
    path('api/user/<int:user_id>/username/', views.get_username, name='get_username'),
]
