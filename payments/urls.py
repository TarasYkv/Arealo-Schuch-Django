from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('statistics/', views.subscription_statistics, name='subscription_statistics'),
    path('subscriptions/', views.subscriptions_management, name='subscriptions_management'),
    path('storage-logs/', views.storage_logs_view, name='storage_logs'),
    path('user-storage/', views.user_storage_view, name='user_storage'),
    path('webhook-events/', views.webhook_events_view, name='webhook_events'),
    path('checkout/<int:plan_id>/', views.create_checkout_session, name='create_checkout_session'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('portal/', views.customer_portal, name='customer_portal'),
    path('cancel/<int:subscription_id>/', views.cancel_subscription, name='cancel_subscription'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('api/status/', views.subscription_status_api, name='subscription_status_api'),
    path('api/user-files/', views.user_files_api, name='user_files_api'),
    path('api/delete-file/', views.delete_user_file_api, name='delete_user_file_api'),
]