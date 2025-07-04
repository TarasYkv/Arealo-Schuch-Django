from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Main chat pages
    path('', views.chat_home, name='home'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    path('start/<int:user_id>/', views.start_chat, name='start_chat'),
    path('search/', views.user_search, name='user_search'),
    path('group/create/', views.create_group_chat, name='create_group_chat'),
    
    # AJAX endpoints
    path('api/room/<int:room_id>/send/', views.send_message, name='send_message'),
    path('api/room/<int:room_id>/messages/', views.get_messages, name='get_messages'),
    path('api/room/<int:room_id>/mark_read/', views.mark_messages_read, name='mark_messages_read'),
]