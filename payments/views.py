import stripe
import json
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from .models import SubscriptionPlan, Customer, Subscription, WebhookEvent, Invoice
from .stripe_service import StripeService

logger = logging.getLogger(__name__)


@login_required
def subscription_plans(request):
    """Display available subscription plans"""
    # Get all plans separated by type
    all_plans = SubscriptionPlan.objects.filter(is_active=True)
    workloom_plans = all_plans.filter(plan_type='founder_access')
    storage_plans = all_plans.filter(plan_type='storage').order_by('price')
    all_user_subscriptions = []
    user_invoices = []
    
    try:
        customer = Customer.objects.get(user=request.user)
        all_user_subscriptions = Subscription.objects.filter(
            customer=customer,
            status__in=['active', 'trialing']
        ).select_related('plan')
        
        # Get recent invoices for the user
        user_invoices = Invoice.objects.filter(
            customer=customer,
            status='paid'
        ).order_by('-created_at')[:12]  # Last 12 invoices (1 year)
        
    except Customer.DoesNotExist:
        pass
    
    # Separate subscriptions by type
    workloom_subscription = None
    storage_subscription = None
    
    for sub in all_user_subscriptions:
        if sub.plan.plan_type == 'founder_access':
            workloom_subscription = sub
        elif sub.plan.plan_type == 'storage':
            storage_subscription = sub
    
    context = {
        'workloom_plans': workloom_plans,
        'storage_plans': storage_plans,
        'workloom_subscription': workloom_subscription,
        'storage_subscription': storage_subscription,
        'all_user_subscriptions': all_user_subscriptions,
        'user_invoices': user_invoices,
    }
    return render(request, 'payments/subscription_plans.html', context)


@login_required
def create_checkout_session(request, plan_id):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        try:
            # Check if Stripe is properly configured
            if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_51234'):
                return JsonResponse({
                    'error': 'Stripe ist noch nicht konfiguriert. Bitte setzen Sie echte Stripe API-Keys in der .env Datei.'
                }, status=400)
            
            plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
            
            success_url = request.build_absolute_uri(reverse('payments:checkout_success'))
            cancel_url = request.build_absolute_uri(reverse('payments:subscription_plans'))
            
            session = StripeService.create_checkout_session(
                user=request.user,
                plan_id=plan_id,
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url
            )
            
            return JsonResponse({'checkout_url': session.url})
        except Exception as e:
            error_msg = str(e)
            if 'API key' in error_msg:
                error_msg = 'Stripe API-Schlüssel nicht konfiguriert. Bitte echte Stripe-Keys in der .env Datei setzen.'
            logger.error(f"Error creating checkout session: {str(e)}")
            return JsonResponse({'error': error_msg}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def checkout_success(request):
    """Handle successful checkout"""
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.subscription:
                StripeService.sync_subscription_from_stripe(session.subscription)
                messages.success(request, 'Subscription activated successfully!')
            else:
                messages.error(request, 'No subscription found in checkout session')
        except Exception as e:
            logger.error(f"Error processing checkout success: {str(e)}")
            messages.error(request, 'Error processing subscription')
    
    return redirect('payments:subscription_plans')


@login_required
def customer_portal(request):
    """Redirect to Stripe customer portal"""
    try:
        # Check if Stripe is properly configured
        if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_51234'):
            messages.error(request, 'Stripe ist noch nicht konfiguriert. Bitte kontaktieren Sie den Support.')
            return redirect('payments:subscription_plans')
        
        return_url = request.build_absolute_uri(reverse('payments:subscription_plans'))
        session = StripeService.create_customer_portal_session(
            user=request.user,
            return_url=return_url
        )
        return redirect(session.url)
    except Exception as e:
        logger.error(f"Error creating portal session: {str(e)}")
        messages.error(request, f'Billing-Portal nicht verfügbar: {str(e)}')
        return redirect('payments:subscription_plans')


@login_required
def cancel_subscription(request, subscription_id):
    """Cancel user subscription"""
    if request.method == 'POST':
        try:
            subscription = get_object_or_404(
                Subscription,
                id=subscription_id,
                customer__user=request.user
            )
            
            at_period_end = request.POST.get('at_period_end', 'true').lower() == 'true'
            StripeService.cancel_subscription(subscription_id, at_period_end)
            
            if at_period_end:
                messages.success(request, 'Subscription will be canceled at the end of the current period')
            else:
                messages.success(request, 'Subscription canceled immediately')
                
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            messages.error(request, 'Error canceling subscription')
    
    return redirect('payments:subscription_plans')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    # Log incoming webhook for debugging
    logger.info(f"Webhook received - Signature: {sig_header[:20] if sig_header else 'None'}...")
    logger.info(f"Payload size: {len(payload)} bytes")
    
    # Check if webhook secret is configured
    if not settings.STRIPE_WEBHOOK_SECRET or settings.STRIPE_WEBHOOK_SECRET.startswith('whsec_1234'):
        logger.error("Webhook secret not properly configured")
        return HttpResponse("Webhook secret not configured", status=400)
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"Webhook event verified: {event['type']} - {event['id']}")
    except ValueError as e:
        logger.error(f"Invalid payload in webhook: {str(e)}")
        return HttpResponse("Invalid payload", status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature in webhook: {str(e)}")
        return HttpResponse("Invalid signature", status=400)
    
    # Log the webhook event
    webhook_event, created = WebhookEvent.objects.get_or_create(
        stripe_event_id=event['id'],
        defaults={
            'event_type': event['type'],
            'data': event['data'],
            'processed': False
        }
    )
    
    if not created and webhook_event.processed:
        logger.info(f"Webhook {event['id']} already processed")
        return HttpResponse(status=200)
    
    try:
        # Handle different event types
        if event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            StripeService.sync_subscription_from_stripe(subscription['id'])
            
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            StripeService.sync_subscription_from_stripe(subscription['id'])
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            StripeService.sync_subscription_from_stripe(subscription['id'])
            
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            StripeService.sync_invoice_from_stripe(invoice['id'])
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            StripeService.sync_invoice_from_stripe(invoice['id'])
            
        elif event['type'] == 'invoice.created':
            invoice = event['data']['object']
            StripeService.sync_invoice_from_stripe(invoice['id'])
            
        elif event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            if session.get('subscription'):
                StripeService.sync_subscription_from_stripe(session['subscription'])
        
        # Mark webhook as processed
        webhook_event.processed = True
        webhook_event.save()
        
        logger.info(f"Successfully processed webhook {event['id']} of type {event['type']}")
        
    except Exception as e:
        error_msg = f"Error processing webhook {event['id']}: {str(e)}"
        logger.error(error_msg)
        webhook_event.processing_error = error_msg
        webhook_event.save()
        return HttpResponse(status=500)
    
    return HttpResponse(status=200)


@login_required
def subscription_status_api(request):
    """API endpoint to get user's subscription status as JSON"""
    from videos.subscription_sync import StorageSubscriptionSync
    
    try:
        plan_info = StorageSubscriptionSync.get_user_plan_info(request.user)
        
        return JsonResponse({
            'success': True,
            'subscription': {
                'has_subscription': plan_info['has_subscription'],
                'plan_name': plan_info['plan_name'],
                'price': plan_info['price'],
                'currency': plan_info['currency'],
                'interval': plan_info['interval'],
                'storage_mb': plan_info['storage_mb'],
                'status': plan_info['status'],
                'is_premium': plan_info['is_premium'],
                'used_storage_mb': plan_info['used_storage_mb'],
                'max_storage_mb': plan_info['max_storage_mb'],
                'used_percentage': plan_info['used_percentage'],
                'available_mb': plan_info['available_mb'],
            }
        })
    except Exception as e:
        logger.error(f"Error getting subscription status for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Unable to load subscription status'
        }, status=500)
