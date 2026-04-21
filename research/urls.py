from django.urls import path

from . import views

app_name = 'research'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ask/', views.ask, name='ask'),
    path('ask/<int:pk>/', views.query_detail, name='query_detail'),
    path('history/', views.history, name='history'),
    # /research/keys/ entfernt — OpenRouter-Key wird zentral unter
    # /accounts/neue-api-einstellungen/ gepflegt.
]
