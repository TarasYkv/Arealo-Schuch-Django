from django.urls import path
from . import views

app_name = 'stats'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('standalone/', views.dashboard_standalone, name='dashboard_standalone'),
    path('visits/', views.visits_detail, name='visits_detail'),
    path('ad-clicks/', views.ad_clicks_detail, name='ad_clicks_detail'),
    path('chart-data/', views.chart_data, name='chart_data'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/report/', views.export_report, name='export_report'),
]