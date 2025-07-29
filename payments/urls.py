from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('checkout/<int:plan_id>/', views.create_checkout_session, name='create_checkout_session'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),
    path('portal/', views.customer_portal, name='customer_portal'),
    path('cancel/<int:subscription_id>/', views.cancel_subscription, name='cancel_subscription'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('api/status/', views.subscription_status_api, name='subscription_status_api'),
]