from django.urls import path
from . import views
from . import views_frontend
from . import views_wizard
from . import views_app
from . import views_simple

app_name = 'loomads'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Kampagnen
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/bulk-action/', views_frontend.campaign_bulk_action, name='campaign_bulk_action'),
    path('campaigns/create/', views.campaign_create, name='campaign_create'),
    path('campaigns/<uuid:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<uuid:campaign_id>/edit/', views.campaign_edit, name='campaign_edit'),
    path('campaigns/<uuid:campaign_id>/delete/', views.campaign_delete, name='campaign_delete'),
    
    # Anzeigen
    path('ads/', views.ad_list, name='ad_list'),
    path('ads/create/', views.ad_create, name='ad_create'),
    path('ads/<uuid:ad_id>/', views.ad_detail, name='ad_detail'),
    path('ads/<uuid:ad_id>/edit/', views.ad_edit, name='ad_edit'),
    path('ads/<uuid:ad_id>/delete/', views.ad_delete, name='ad_delete'),
    
    # Zonen
    path('zones/', views.zone_list, name='zone_list'),
    path('zones/create/', views.zone_create, name='zone_create'),
    path('zones/<int:zone_id>/edit/', views.zone_edit, name='zone_edit'),
    path('zones/<int:zone_id>/delete/', views.zone_delete, name='zone_delete'),
    
    # Auto-Kampagnen
    path('auto-campaigns/', views_frontend.auto_campaign_list, name='auto_campaign_list'),
    path('auto-campaigns/create/', views_frontend.auto_campaign_create, name='auto_campaign_create'),
    path('auto-campaigns/<uuid:campaign_id>/', views_frontend.auto_campaign_detail, name='auto_campaign_detail'),
    path('auto-campaigns/<uuid:campaign_id>/edit/', views_frontend.auto_campaign_edit, name='auto_campaign_edit'),
    path('auto-campaigns/<uuid:campaign_id>/delete/', views_frontend.auto_campaign_delete, name='auto_campaign_delete'),

    # App-Kampagnen
    path('app-campaigns/', views.app_campaign_list, name='app_campaign_list'),
    path('app-campaigns/bulk-action/', views_app.app_campaign_bulk_action, name='app_campaign_bulk_action'),
    path('app-campaigns/create/', views.app_campaign_create, name='app_campaign_create'),
    path('app-campaigns/<uuid:campaign_id>/', views.app_campaign_detail, name='app_campaign_detail'),
    path('app-campaigns/<uuid:campaign_id>/edit/', views.app_campaign_edit, name='app_campaign_edit'),
    path('app-campaigns/<uuid:campaign_id>/delete/', views.app_campaign_delete, name='app_campaign_delete'),

    # App-Anzeigen
    path('app-campaigns/<uuid:campaign_id>/ads/create/', views.app_ad_create, name='app_ad_create'),
    path('app-ads/<uuid:ad_id>/edit/', views.app_ad_edit, name='app_ad_edit'),
    path('app-ads/<uuid:ad_id>/delete/', views.app_ad_delete, name='app_ad_delete'),

    # Simple Ads (Vereinfachte globale Anzeigen)
    path('simple-ads/', views_simple.simple_ad_list, name='simple_ad_list'),
    path('simple-ads/create/', views_simple.simple_ad_create, name='simple_ad_create'),
    path('simple-ads/<uuid:ad_id>/edit/', views_simple.simple_ad_edit, name='simple_ad_edit'),
    path('simple-ads/<uuid:ad_id>/delete/', views_simple.simple_ad_delete, name='simple_ad_delete'),
    path('simple-ads/<uuid:ad_id>/toggle/', views_simple.simple_ad_toggle, name='simple_ad_toggle'),

    # Ad Creation Wizard
    path('wizard/', views_wizard.wizard_start, name='wizard_start'),
    path('wizard/<uuid:draft_id>/<str:step>/', views_wizard.wizard_step, name='wizard_step'),
    path('wizard/<uuid:draft_id>/cancel/', views_wizard.wizard_cancel, name='wizard_cancel'),
    path('wizard/drafts/', views_wizard.wizard_list_drafts, name='wizard_list_drafts'),

    # Auto-Campaign Formate
    path('auto-formats/', views_frontend.auto_format_list, name='auto_format_list'),
    
    # Zone Integrations
    path('integrations/create/', views_frontend.integration_create, name='integration_create'),
    path('integrations/<int:integration_id>/edit/', views_frontend.integration_edit, name='integration_edit'),
    path('integrations/<int:integration_id>/delete/', views_frontend.integration_delete, name='integration_delete'),
    
    # Analytics & Settings
    path('analytics/', views.analytics, name='analytics'),
    path('settings/', views_frontend.settings, name='settings'),
    
    # Examples
    path('examples/', views_frontend.examples_overview, name='examples_overview'),
    path('examples/zone/<str:zone_id>/', views_frontend.examples_zone_detail, name='examples_zone_detail'),
    
    # AJAX Endpoints
    path('ajax/update-zone-status/', views_frontend.ajax_update_zone_status, name='ajax_update_zone_status'),
    
    # API Endpoints (Legacy)
    path('api/zone/<str:zone_code>/ad/', views.get_ad_for_zone, name='get_ad_for_zone'),
    path('api/zone/<str:zone_code>/ads/<int:count>/', views.get_multiple_ads_for_zone, name='get_multiple_ads_for_zone'),
    path('api/track/click/<uuid:ad_id>/', views.track_click, name='track_click'),

    # Simple Ads API (Neu - Vereinfacht)
    path('api/simple-ad/', views.get_simple_ad, name='get_simple_ad'),
    path('api/simple-ad/<str:zone_code>/', views.get_simple_ad, name='get_simple_ad_zone'),
    path('api/simple-ad/track/<uuid:ad_id>/', views.track_simple_ad_click, name='track_simple_ad_click'),
]