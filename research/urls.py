from django.urls import path

from . import views

app_name = 'research'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ask/', views.ask, name='ask'),
    path('ask/<int:pk>/', views.query_detail, name='query_detail'),
    path('ask/<int:pk>/status/', views.query_status, name='query_status'),
    path('history/', views.history, name='history'),
    path('stats/', views.stats, name='stats'),
]
