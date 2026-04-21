from django.urls import path

from . import views

app_name = 'research'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ask/', views.ask, name='ask'),
    path('ask/<int:pk>/', views.query_detail, name='query_detail'),
    path('history/', views.history, name='history'),
    path('keys/', views.api_keys, name='api_keys'),
]
