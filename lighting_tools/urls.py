from django.urls import path
from . import views

app_name = 'lighting_tools'

urlpatterns = [
    path('', views.lighting_tools_overview, name='overview'),
]