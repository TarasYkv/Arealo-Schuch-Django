from django.urls import path
from . import views

app_name = 'lighting_classification'

urlpatterns = [
    path('', views.index, name='index'),
    path('straßentyp/', views.select_road_type, name='select_road_type'),
    path('start/', views.start_classification, name='start_classification'),
    path('parameter/<int:classification_id>/', views.configure_parameters, name='configure_parameters'),
    path('ergebnis/<int:classification_id>/', views.view_result, name='view_result'),
]