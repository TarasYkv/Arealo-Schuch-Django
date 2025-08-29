from django.urls import path
from . import views

app_name = "promptpro"

urlpatterns = [
    path("", views.prompt_list, name="prompt_list"),
    path("neu/", views.prompt_create, name="prompt_create"),
    path("<int:pk>/bearbeiten/", views.prompt_edit, name="prompt_edit"),
    path("<int:pk>/loeschen/", views.prompt_delete, name="prompt_delete"),

    path("kategorien/uebersicht/", views.category_overview, name="category_overview"),
    path("kategorien/", views.category_list, name="category_list"),
    path("kategorien/neu/", views.category_create, name="category_create"),
    path("kategorien/<int:pk>/bearbeiten/", views.category_edit, name="category_edit"),
    path("kategorien/<int:pk>/loeschen/", views.category_delete, name="category_delete"),
]

