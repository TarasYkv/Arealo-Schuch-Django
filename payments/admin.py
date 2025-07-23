from django.contrib import admin
from .models import SubscriptionPlan, Customer, Subscription, Invoice, PaymentMethod, WebhookEvent


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'currency', 'interval', 'plan_type', 'storage_mb', 'is_active']
    list_filter = ['plan_type', 'interval', 'is_active']
    search_fields = ['name', 'stripe_price_id']
    readonly_fields = ['created_at']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'stripe_customer_id', 'created_at']
    search_fields = ['user__username', 'user__email', 'stripe_customer_id']
    readonly_fields = ['stripe_customer_id', 'created_at', 'updated_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'plan', 'status', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'plan__plan_type', 'cancel_at_period_end']
    search_fields = ['customer__user__username', 'customer__user__email', 'stripe_subscription_id']
    readonly_fields = ['stripe_subscription_id', 'created_at', 'updated_at']
    date_hierarchy = 'current_period_end'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['customer', 'stripe_invoice_id', 'status', 'amount_due', 'amount_paid', 'due_date']
    list_filter = ['status', 'currency']
    search_fields = ['customer__user__username', 'stripe_invoice_id']
    readonly_fields = ['stripe_invoice_id', 'invoice_url', 'invoice_pdf', 'created_at']
    date_hierarchy = 'due_date'


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['customer', 'payment_type', 'card_brand', 'card_last4', 'is_default']
    list_filter = ['payment_type', 'card_brand', 'is_default']
    search_fields = ['customer__user__username', 'stripe_payment_method_id']
    readonly_fields = ['stripe_payment_method_id', 'created_at']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['stripe_event_id', 'event_type', 'processed', 'created_at']
    list_filter = ['event_type', 'processed']
    search_fields = ['stripe_event_id', 'event_type']
    readonly_fields = ['stripe_event_id', 'data', 'created_at']
    date_hierarchy = 'created_at'
