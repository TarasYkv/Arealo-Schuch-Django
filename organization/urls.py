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
    path('boards/<int:pk>/invite-collaborators/', views.board_invite_collaborators, name='board_invite_collaborators'),
    path('boards/<int:pk>/remove-collaborator/', views.board_remove_collaborator, name='board_remove_collaborator'),
    
    # API
    path('api/user-search/', views.user_search, name='user_search'),
]