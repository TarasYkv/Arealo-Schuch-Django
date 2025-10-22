from django.urls import path
from . import views

app_name = 'keyengine'

urlpatterns = [
    # Dashboard (Hauptseite)
    path('', views.dashboard, name='dashboard'),

    # AJAX Endpoints - Keyword-Generierung
    path('generate/', views.generate_keywords, name='generate_keywords'),
    path('add/', views.add_to_watchlist, name='add_to_watchlist'),

    # Listen-Übersicht
    path('lists/', views.lists_overview, name='lists_overview'),
    path('list/<int:list_id>/', views.list_detail, name='list_detail'),

    # Legacy Watchlist (Redirect)
    path('watchlist/', views.watchlist, name='watchlist'),

    # Listen-Management (AJAX)
    path('list/create/', views.create_list, name='create_list'),
    path('list/<int:list_id>/update/', views.update_list, name='update_list'),
    path('list/<int:list_id>/delete/', views.delete_list, name='delete_list'),
    path('list/<int:list_id>/archive/', views.toggle_archive_list, name='toggle_archive_list'),
    path('list/<int:list_id>/duplicate/', views.duplicate_list, name='duplicate_list'),
    path('list/<int:list_id>/export/', views.export_list, name='export_list'),

    # Keyword-Management (AJAX)
    path('keyword/<int:keyword_id>/update/', views.update_keyword, name='update_keyword'),
    path('keyword/<int:keyword_id>/delete/', views.delete_keyword, name='delete_keyword'),
    path('keyword/<int:keyword_id>/move/', views.move_keyword, name='move_keyword'),
]
