"""
Mail App URL Configuration
"""
from django.urls import path
from django.shortcuts import render
from . import views_original as views
from . import views_modern
from .views import (
    MailModernView,
    MailSimpleView,
    MailStandaloneView,
    MailTicketsView,
    ToggleEmailStatusView,
    CloseTicketView,
    EmailContentAPIView
)

app_name = 'mail_app'

urlpatterns = [
    # Web Views
    path('', views.mail_dashboard, name='dashboard'),
    path('modern/', MailModernView.as_view(), name='mail_modern'),
    path('auth/authorize/', views.oauth_authorize, name='oauth_authorize'),
    path('auth/callback/', views.oauth_callback, name='oauth_callback'),
    path('auth/disconnect/', views.oauth_disconnect, name='oauth_disconnect'),
    
    # API Endpoints
    path('api/accounts/', views.api_accounts, name='api_accounts'),
    path('api/accounts/<int:account_id>/folders/', views.api_folders, name='api_folders'),
    path('api/accounts/<int:account_id>/folders/<int:folder_id>/emails/', views.api_emails, name='api_emails'),
    path('api/accounts/<int:account_id>/sync/', views.api_sync_emails, name='api_sync_emails'),
    path('api/accounts/<int:account_id>/sync/status/', views.api_sync_status, name='api_sync_status'),
    path('api/emails/<int:email_id>/', EmailContentAPIView.as_view(), name='api_email_html'),
    path('api/emails/<int:email_id>/detail/', views.api_email_detail, name='api_email_detail'),
    path('api/emails/<int:email_id>/mark/', views.api_mark_email, name='api_mark_email'),
    path('api/emails/<int:email_id>/mark-read/', views.api_mark_email, name='api_mark_read'),
    path('api/send/', views.api_send_email, name='api_send_email'),
    path('api/attachments/upload/', views.api_upload_attachment, name='api_upload_attachment'),
    path('api/attachments/<int:attachment_id>/download/', views.api_download_attachment, name='api_download_attachment'),
    
    # Thread Endpoints
    path('api/accounts/<int:account_id>/threads/', views.api_threads, name='api_threads'),
    path('api/threads/<int:thread_id>/emails/', views.api_thread_emails, name='api_thread_emails'),
    
    # Modern interface endpoints  
    path('api/emails/<int:email_id>/delete/', views_modern.delete_email, name='api_delete_email'),
    path('api/emails/<int:email_id>/toggle-open/', ToggleEmailStatusView.as_view(), name='api_toggle_email_open'),
    path('api/tickets/<int:ticket_id>/close/', CloseTicketView.as_view(), name='api_close_ticket'),
    path('api/tickets/<int:ticket_id>/emails/', views_modern.api_ticket_emails, name='api_ticket_emails'),
    path('api/search/', views_modern.api_email_search, name='api_email_search'),
    
    # Image display for email content
    path('ImageDisplay', views_modern.image_display, name='image_display'),
    
    # Debug route
    path('debug-css/', lambda request: render(request, 'mail_app/debug_css.html'), name='debug_css'),
    path('simple/', MailSimpleView.as_view(), name='mail_simple'),
    path('standalone/', MailStandaloneView.as_view(), name='mail_standalone'),
    path('tickets/', MailTicketsView.as_view(), name='mail_tickets'),
]