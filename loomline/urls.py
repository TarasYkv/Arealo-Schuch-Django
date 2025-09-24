"""
LoomLine URLs - Einfache URL-Konfiguration
"""

from django.urls import path
from . import views

app_name = 'loomline'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Projekte
    path('projekte/', views.ProjectListView.as_view(), name='project-list'),
    path('projekte/neu/', views.ProjectCreateView.as_view(), name='project-create'),
    path('projekte/<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('projekte/<int:pk>/bearbeiten/', views.ProjectUpdateView.as_view(), name='project-edit'),
    path('projekte/<int:pk>/loeschen/', views.project_delete, name='project-delete'),

    # Aufgaben
    path('projekte/<int:project_id>/aufgabe/', views.add_task, name='add-task'),
    path('eintragen/', views.quick_add_task, name='quick-add-task'),
    path('aufgaben/', views.tasks_tiles_view, name='tasks-tiles'),
    path('aufgaben/<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('sub-aufgabe/', views.add_subtask, name='add-subtask'),

    # Mitglieder
    path('projekte/<int:project_id>/mitglied/hinzufuegen/', views.add_member_to_project, name='add-member'),
    path('projekte/<int:project_id>/mitglied/<int:user_id>/entfernen/', views.remove_member_from_project, name='remove-member'),

    # Bearbeiten und Löschen
    path('aufgaben/<int:task_id>/bearbeiten/', views.edit_task, name='edit-task'),
    path('aufgaben/<int:task_id>/loeschen/', views.delete_task, name='delete-task'),
    path('sub-aufgaben/<int:subtask_id>/loeschen/', views.delete_subtask, name='delete-subtask'),
]