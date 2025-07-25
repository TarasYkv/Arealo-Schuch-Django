from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('toggle-dark-mode/', views.toggle_dark_mode, name='toggle_dark_mode'),
    path('api-keys/', views.manage_api_keys, name='manage_api_keys'),
    path('api-einstellungen/', views.api_settings_view, name='api_settings'),
    
    # Canva Integration (consolidated into neue-api-einstellungen)
    path('canva-settings/', views.canva_settings_view, name='canva_settings'),  # Keep for form handling
    path('canva-oauth-start/', views.canva_oauth_start, name='canva_oauth_start'),
    path('canva-oauth-callback/', views.canva_oauth_callback, name='canva_oauth_callback'),
    path('canva-disconnect/', views.canva_disconnect, name='canva_disconnect'),
    path('neue-api-einstellungen/', views.neue_api_einstellungen_view, name='neue_api_einstellungen'),
    path('firmeninfo/', views.company_info_view, name='company_info'),
    path('test-app-permissions/', views.test_app_permissions_view, name='test_app_permissions'),
    path('api/users/', views.get_all_users_api, name='get_all_users_api'),
    path('api/validate-key/', views.validate_api_key, name='validate_api_key'),
    path('api/balances/', views.get_api_balances, name='get_api_balances'),
    path('api/balances/update/', views.update_api_balance, name='update_api_balance'),
    path('api/balances/remove-key/', views.remove_api_key, name='remove_api_key'),
    path('api/usage/stats/', views.get_usage_stats, name='get_usage_stats'),
    
    # Shopify Integration APIs
    path('api/add-shopify-store/', views.add_shopify_store, name='add_shopify_store'),
    path('api/test-shopify-connection/', views.test_shopify_connection, name='test_shopify_connection'),
    path('api/delete-shopify-store/', views.delete_shopify_store, name='delete_shopify_store'),
    
    # User permissions management
    path('nutzerrechte/', views.user_permissions, name='user_permissions'),
    path('api/user-online-times/<int:user_id>/', views.user_online_times, name='user_online_times'),
    path('api/user-app-usage/<int:user_id>/', views.user_app_usage_statistics, name='user_app_usage_statistics'),
    
    # Subscription management
    path('abo/<str:app_name>/', views.manage_subscription, name='manage_subscription'),
    
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
    
    # Profil-Management
    path('profil/', views.profile_view, name='profile'),
    # path('passwort-aendern/', views.change_password_view, name='change_password'),
    
    # Content Editor
    path('content-editor/', views.content_editor, name='content_editor'),
    path('content/update/', views.update_content, name='update_content'),
    path('content/delete/', views.delete_content, name='delete_content'),
    path('content/<int:content_id>/', views.get_content, name='get_content'),
    path('content/generate-ai/', views.generate_ai_content, name='generate_ai_content'),
    path('content/ai-edit/', views.ai_edit_content, name='ai_edit_content'),
    path('content/ai-rephrase/', views.ai_rephrase_content, name='ai_rephrase_content'),
    path('page/create/', views.create_page, name='create_page'),
    path('page/delete/', views.delete_page, name='delete_page'),
    
    # SEO Editor
    path('seo/get/', views.get_seo_settings, name='get_seo_settings'),
    path('seo/save/', views.save_seo_settings, name='save_seo_settings'),
    path('seo/alt-texts/', views.get_alt_texts, name='get_alt_texts'),
    
    # App Info
    path('apps/<str:app_name>/info/', views.app_info, name='app_info'),
    
    # Zoho Mail API Management
    path('api/zoho-settings/', views.zoho_settings_api, name='zoho_settings_api'),
    path('api/zoho-test/', views.zoho_test_api, name='zoho_test_api'),
    path('api/zoho-disconnect/', views.zoho_disconnect_api, name='zoho_disconnect_api'),
    path('api/zoho-delete-all-emails/', views.zoho_delete_all_emails_api, name='zoho_delete_all_emails_api'),
]