from django.urls import path

from . import views

app_name = 'research'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ask/', views.ask, name='ask'),
    path('ask/<int:pk>/', views.query_detail, name='query_detail'),
    path('ask/<int:pk>/download/', views.query_download, name='query_download'),
    path('ask/<int:pk>/graph/', views.query_graph, name='query_graph'),
    path('ask/<int:pk>/ideas/', views.query_ideas, name='query_ideas'),
    path('ask/<int:pk>/status/', views.query_status, name='query_status'),
    path('ask/<int:pk>/toggle-share/', views.query_toggle_share, name='query_toggle_share'),
    # Oeffentliche Share-Links — kein Login erforderlich
    path('share/<str:token>/', views.share_detail, name='share_detail'),
    path('share/<str:token>/graph/', views.share_graph, name='share_graph'),
    path('share/<str:token>/ideas/', views.share_ideas, name='share_ideas'),
    path('share/<str:token>/download/', views.share_download, name='share_download'),
    path('history/', views.history, name='history'),
    path('stats/', views.stats, name='stats'),
]
