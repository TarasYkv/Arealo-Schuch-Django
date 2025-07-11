from django.urls import path
from . import views

app_name = 'todos'

urlpatterns = [
    # Hauptseiten
    path('', views.todo_home, name='home'),
    path('my-todos/', views.my_todos, name='my_todos'),
    
    # Listen-Management
    path('list/new/', views.create_list, name='create_list'),
    path('list/<int:pk>/', views.list_detail, name='list_detail'),
    
    # ToDo-Management
    path('list/<int:list_pk>/todo/new/', views.create_todo, name='create_todo'),
    path('todo/<int:pk>/', views.todo_detail, name='todo_detail'),
    
    # AJAX-Endpunkte
    path('api/todo/<int:pk>/status/', views.update_todo_status, name='update_todo_status'),
    path('api/todo/<int:pk>/assign/', views.assign_todo, name='assign_todo'),
    path('api/todo/<int:pk>/comment/', views.add_comment, name='add_comment'),
]