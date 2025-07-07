from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api-keys/', views.manage_api_keys, name='manage_api_keys'),
    path('api-einstellungen/', views.api_settings_view, name='api_settings'),
    
    # Canva Integration (consolidated into neue-api-einstellungen)
    path('canva-settings/', views.canva_settings_view, name='canva_settings'),  # Keep for form handling
    path('canva-oauth-start/', views.canva_oauth_start, name='canva_oauth_start'),
    path('canva-oauth-callback/', views.canva_oauth_callback, name='canva_oauth_callback'),
    path('canva-disconnect/', views.canva_disconnect, name='canva_disconnect'),
    path('neue-api-einstellungen/', views.neue_api_einstellungen_view, name='neue_api_einstellungen'),
    path('firmeninfo/', views.company_info_view, name='company_info'),
    path('api/validate-key/', views.validate_api_key, name='validate_api_key'),
    path('api/balances/', views.get_api_balances, name='get_api_balances'),
    path('api/balances/update/', views.update_api_balance, name='update_api_balance'),
    path('api/balances/remove-key/', views.remove_api_key, name='remove_api_key'),
    path('api/usage/stats/', views.get_usage_stats, name='get_usage_stats'),
    
    # Shopify Integration APIs
    path('api/add-shopify-store/', views.add_shopify_store, name='add_shopify_store'),
    path('api/test-shopify-connection/', views.test_shopify_connection, name='test_shopify_connection'),
    path('api/delete-shopify-store/', views.delete_shopify_store, name='delete_shopify_store'),
    
    # Kategorie-Management
    path('kategorien/', views.category_list, name='category_list'),
    path('kategorien/neu/', views.category_create, name='category_create'),
    path('kategorien/<int:pk>/', views.category_detail, name='category_detail'),
    path('kategorien/<int:pk>/bearbeiten/', views.category_edit, name='category_edit'),
    path('kategorien/<int:pk>/loeschen/', views.category_delete, name='category_delete'),
    
    # Suchbegriff-Management
    path('kategorien/<int:category_pk>/begriffe/neu/', views.keyword_add, name='keyword_add'),
    path('kategorien/<int:category_pk>/begriffe/bulk/', views.keyword_bulk_add, name='keyword_bulk_add'),
    path('begriffe/<int:keyword_pk>/loeschen/', views.keyword_delete, name='keyword_delete'),
]