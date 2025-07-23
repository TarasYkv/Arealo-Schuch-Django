from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class SubscriptionPlan(models.Model):
    """Stripe subscription plans"""
    PLAN_TYPES = [
        ('storage', 'Storage Plan'),
        ('premium', 'Premium Features'),
        ('enterprise', 'Enterprise'),
        ('founder_access', 'Founder Early Access'),
    ]
    
    name = models.CharField(max_length=100)
    stripe_price_id = models.CharField(max_length=100, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    interval = models.CharField(max_length=20, default='month')  # month, year
    storage_mb = models.IntegerField(null=True, blank=True)  # For storage plans
    features = models.JSONField(default=dict, blank=True)  # Additional features
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - {self.price}€/{self.interval}"


class Customer(models.Model):
    """Stripe customer data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Customer: {self.user.username}"


class Subscription(models.Model):
    """User subscriptions"""
    STATUS_CHOICES = [
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('trialing', 'Trialing'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    stripe_subscription_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.user.username} - {self.plan.name}"
    
    @property
    def is_active(self):
        return self.status in ['active', 'trialing']
    
    @property
    def days_until_renewal(self):
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0


class Invoice(models.Model):
    """Stripe invoices"""
    INVOICE_STATUS = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('void', 'Void'),
        ('uncollectible', 'Uncollectible'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, null=True, blank=True)
    stripe_invoice_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='EUR')
    invoice_url = models.URLField(blank=True)
    invoice_pdf = models.URLField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.stripe_invoice_id} - {self.amount_due}€"


class PaymentMethod(models.Model):
    """Customer payment methods"""
    PAYMENT_TYPES = [
        ('card', 'Credit Card'),
        ('sepa_debit', 'SEPA Direct Debit'),
        ('paypal', 'PayPal'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    stripe_payment_method_id = models.CharField(max_length=100, unique=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    is_default = models.BooleanField(default=False)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    card_exp_month = models.IntegerField(null=True, blank=True)
    card_exp_year = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.payment_type == 'card' and self.card_last4:
            return f"{self.card_brand} ****{self.card_last4}"
        return f"{self.get_payment_type_display()}"


class WebhookEvent(models.Model):
    """Stripe webhook events log"""
    stripe_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.stripe_event_id}"
