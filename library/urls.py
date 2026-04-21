from django.urls import path
from . import views

app_name = "library"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("refs/", views.reference_list, name="reference_list"),
    path("refs/add/", views.reference_add, name="reference_add"),
    path("refs/<int:pk>/", views.reference_detail, name="reference_detail"),
    path("refs/<int:pk>/edit/", views.reference_edit, name="reference_edit"),
    path("refs/<int:pk>/delete/", views.reference_delete, name="reference_delete"),
    path("import/", views.bibtex_import, name="bibtex_import"),
    path("collections/", views.collection_list, name="collection_list"),
    path("collections/add/", views.collection_add, name="collection_add"),
    path("collections/<int:pk>/", views.collection_detail, name="collection_detail"),
    path("zotero/", views.zotero_settings, name="zotero_settings"),
    path("zotero/sync/", views.zotero_sync_now, name="zotero_sync_now"),
]
