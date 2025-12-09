from django.urls import path
from . import views

app_name = 'questionfinder'

urlpatterns = [
    # Dashboard (Hauptseite)
    path('', views.dashboard, name='dashboard'),

    # AJAX Endpoints - Suche
    path('search/', views.search_questions, name='search_questions'),

    # Gespeicherte Fragen
    path('saved/', views.saved_questions, name='saved_questions'),
    path('save/', views.save_question, name='save_question'),
    path('delete/<int:question_id>/', views.delete_question, name='delete_question'),
    path('toggle-used/<int:question_id>/', views.toggle_used, name='toggle_used'),
]
