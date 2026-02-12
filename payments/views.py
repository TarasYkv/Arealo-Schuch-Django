import stripe
import json
import logging
import os
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


def calculate_total_storage_for_user(user):
    """
    Berechnet den tatsächlichen Speicherverbrauch aus ALLEN Apps.
    Gibt ein Dict mit used_bytes, max_bytes, used_mb, max_mb, percentage zurück.
    """
    from core.storage_service import StorageService
    from videos.models import UserStorage as VideoUserStorage

    total_used_bytes = 0

    # 1. Videos
    try:
        from videos.models import Video
        videos = Video.objects.filter(user=user, video_file__isnull=False)
        for video in videos:
            if video.video_file:
                try:
                    total_used_bytes += video.video_file.size if hasattr(video.video_file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 2. Fileshare
    try:
        from fileshare.models import TransferFile
        files = TransferFile.objects.filter(transfer__sender=user, file__isnull=False)
        for f in files:
            if f.file:
                try:
                    total_used_bytes += f.file.size if hasattr(f.file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 3. Streamrec
    try:
        user_prefix = f"{user.id}_"
        for dir_name in ['audio_recordings', 'video_recordings']:
            media_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
            if os.path.exists(media_dir):
                for filename in os.listdir(media_dir):
                    if filename.startswith(user_prefix):
                        filepath = os.path.join(media_dir, filename)
                        if os.path.isfile(filepath):
                            total_used_bytes += os.path.getsize(filepath)
    except:
        pass

    # 4. Chat Attachments
    try:
        from chat.models import ChatMessageAttachment
        attachments = ChatMessageAttachment.objects.filter(message__sender=user, file__isnull=False)
        for att in attachments:
            if att.file:
                try:
                    total_used_bytes += att.file.size if hasattr(att.file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 5. Organization (Notes & Board)
    try:
        from organization.models import Note, BoardElement
        notes = Note.objects.filter(author=user, image__isnull=False)
        for note in notes:
            if note.image:
                try:
                    total_used_bytes += note.image.size if hasattr(note.image, 'size') else 0
                except:
                    pass
    except:
        pass

    # 6. Image Editor
    try:
        from image_editor.models import ImageProject, AIGenerationHistory
        projects = ImageProject.objects.filter(user=user)
        for project in projects:
            for field in ['original_image', 'processed_image']:
                img = getattr(project, field, None)
                if img:
                    try:
                        total_used_bytes += img.size if hasattr(img, 'size') else 0
                    except:
                        pass
        histories = AIGenerationHistory.objects.filter(project__user=user, output_image__isnull=False)
        for history in histories:
            if history.output_image:
                try:
                    total_used_bytes += history.output_image.size if hasattr(history.output_image, 'size') else 0
                except:
                    pass
    except:
        pass

    # 7. PDF Sucher
    try:
        from pdf_sucher.models import SearchSession
        sessions = SearchSession.objects.filter(user=user, pdf_file__isnull=False)
        for session in sessions:
            if session.pdf_file:
                try:
                    total_used_bytes += session.pdf_file.size if hasattr(session.pdf_file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 8. Bug Report
    try:
        from bug_report.models import BugReportScreenshot
        screenshots = BugReportScreenshot.objects.filter(bug_report__sender=user, screenshot__isnull=False)
        for ss in screenshots:
            if ss.screenshot:
                try:
                    total_used_bytes += ss.screenshot.size if hasattr(ss.screenshot, 'size') else 0
                except:
                    pass
    except:
        pass

    # 9. ImageForge
    try:
        from imageforge.models import ImageGeneration, CharacterImage, ProductMockup
        for model, field in [(ImageGeneration, 'result_image'), (CharacterImage, 'image'), (ProductMockup, 'result_image')]:
            items = model.objects.filter(user=user)
            for item in items:
                img = getattr(item, field, None)
                if img:
                    try:
                        total_used_bytes += img.size if hasattr(img, 'size') else 0
                    except:
                        pass
    except:
        pass

    # 10. Ideopin
    try:
        from ideopin.models import PinDesign
        designs = PinDesign.objects.filter(user=user)
        for design in designs:
            for field in ['background_image', 'foreground_image', 'final_design']:
                img = getattr(design, field, None)
                if img:
                    try:
                        total_used_bytes += img.size if hasattr(img, 'size') else 0
                    except:
                        pass
    except:
        pass

    # 11. BlogPrep
    try:
        from blogprep.models import BlogPrepProject
        projects = BlogPrepProject.objects.filter(user=user)
        for project in projects:
            for field in ['title_image', 'diagram_image']:
                img = getattr(project, field, None)
                if img:
                    try:
                        total_used_bytes += img.size if hasattr(img, 'size') else 0
                    except:
                        pass
    except:
        pass

    # 12. VSkript
    try:
        from vskript.models import VSkriptImage
        images = VSkriptImage.objects.filter(project__user=user, image_file__isnull=False)
        for img in images:
            if img.image_file:
                try:
                    total_used_bytes += img.image_file.size if hasattr(img.image_file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 13. LoomConnect
    try:
        from loomconnect.models import ConnectProfile, ConnectPost, ConnectStory
        profiles = ConnectProfile.objects.filter(user=user, avatar__isnull=False)
        for profile in profiles:
            if profile.avatar:
                try:
                    total_used_bytes += profile.avatar.size if hasattr(profile.avatar, 'size') else 0
                except:
                    pass
        posts = ConnectPost.objects.filter(author__user=user, image__isnull=False)
        for post in posts:
            if post.image:
                try:
                    total_used_bytes += post.image.size if hasattr(post.image, 'size') else 0
                except:
                    pass
        stories = ConnectStory.objects.filter(profile__user=user, image__isnull=False)
        for story in stories:
            if story.image:
                try:
                    total_used_bytes += story.image.size if hasattr(story.image, 'size') else 0
                except:
                    pass
    except:
        pass

    # 14. MakeAds
    try:
        from makeads.models import ReferenceImage, Creative
        refs = ReferenceImage.objects.filter(campaign__user=user, image__isnull=False)
        for ref in refs:
            if ref.image:
                try:
                    total_used_bytes += ref.image.size if hasattr(ref.image, 'size') else 0
                except:
                    pass
        creatives = Creative.objects.filter(campaign__user=user, image_file__isnull=False)
        for creative in creatives:
            if creative.image_file:
                try:
                    total_used_bytes += creative.image_file.size if hasattr(creative.image_file, 'size') else 0
                except:
                    pass
    except:
        pass

    # 15. Shopify Uploads
    try:
        from shopify_uploads.models import FotogravurImage
        images = FotogravurImage.objects.filter(uploaded_by=user)
        for img in images:
            for field in ['image', 'original_image']:
                f = getattr(img, field, None)
                if f:
                    try:
                        total_used_bytes += f.size if hasattr(f, 'size') else 0
                    except:
                        pass
    except:
        pass

    # 16. Shopify Backups
    try:
        from shopify_manager.models import ShopifyBackup
        backups = ShopifyBackup.objects.filter(user=user, status='completed')
        for backup in backups:
            if backup.total_size_bytes > 0:
                total_used_bytes += backup.total_size_bytes
    except:
        pass

    # Max storage from UserStorage
    video_storage, _ = VideoUserStorage.objects.get_or_create(user=user)
    max_bytes = video_storage.max_storage

    used_mb = total_used_bytes / (1024 * 1024)
    max_mb = max_bytes / (1024 * 1024)
    percentage = round((total_used_bytes / max_bytes * 100), 2) if max_bytes > 0 else 0

    return {
        'used_bytes': total_used_bytes,
        'max_bytes': max_bytes,
        'used_mb': used_mb,
        'max_mb': max_mb,
        'percentage': percentage,
    }


def calculate_database_storage_for_user(user):
    """
    Schätzt den Datenbank-Speicherverbrauch für einen User.
    Berechnet die Größe von JSON-Feldern und Textfeldern.
    Gibt ein Dict mit Gesamtgröße und Aufschlüsselung zurück.
    """
    import json

    db_stats = {
        'total_bytes': 0,
        'by_category': {},
    }

    # 1. Shopify Products
    try:
        from shopify_manager.models import ShopifyProduct
        products = ShopifyProduct.objects.filter(store__user=user)
        product_bytes = 0
        for p in products:
            # raw_shopify_data ist das größte Feld
            if p.raw_shopify_data:
                product_bytes += len(json.dumps(p.raw_shopify_data).encode('utf-8'))
            # Andere Textfelder
            product_bytes += len((p.title or '').encode('utf-8'))
            product_bytes += len((p.description or '').encode('utf-8'))
            product_bytes += len((p.seo_title or '').encode('utf-8'))
            product_bytes += len((p.seo_description or '').encode('utf-8'))
        if product_bytes > 0:
            db_stats['by_category']['Shopify Produkte'] = {
                'bytes': product_bytes,
                'count': products.count(),
                'icon': 'fas fa-box'
            }
            db_stats['total_bytes'] += product_bytes
    except:
        pass

    # 2. Shopify Blog Posts
    try:
        from shopify_manager.models import ShopifyBlogPost
        posts = ShopifyBlogPost.objects.filter(blog__store__user=user)
        post_bytes = 0
        for p in posts:
            if p.raw_shopify_data:
                post_bytes += len(json.dumps(p.raw_shopify_data).encode('utf-8'))
            post_bytes += len((p.title or '').encode('utf-8'))
            post_bytes += len((p.content or '').encode('utf-8'))
            post_bytes += len((p.seo_title or '').encode('utf-8'))
            post_bytes += len((p.seo_description or '').encode('utf-8'))
        if post_bytes > 0:
            db_stats['by_category']['Shopify Blog-Beiträge'] = {
                'bytes': post_bytes,
                'count': posts.count(),
                'icon': 'fas fa-blog'
            }
            db_stats['total_bytes'] += post_bytes
    except:
        pass

    # 3. Shopify Collections
    try:
        from shopify_manager.models import ShopifyCollection
        collections = ShopifyCollection.objects.filter(store__user=user)
        coll_bytes = 0
        for c in collections:
            if c.raw_shopify_data:
                coll_bytes += len(json.dumps(c.raw_shopify_data).encode('utf-8'))
            coll_bytes += len((c.title or '').encode('utf-8'))
            coll_bytes += len((c.description or '').encode('utf-8'))
            coll_bytes += len((c.seo_title or '').encode('utf-8'))
            coll_bytes += len((c.seo_description or '').encode('utf-8'))
        if coll_bytes > 0:
            db_stats['by_category']['Shopify Kategorien'] = {
                'bytes': coll_bytes,
                'count': collections.count(),
                'icon': 'fas fa-folder'
            }
            db_stats['total_bytes'] += coll_bytes
    except:
        pass

    # 4. SEO Optimizations
    try:
        from shopify_manager.models import ProductSEOOptimization, BlogPostSEOOptimization, CollectionSEOOptimization
        seo_bytes = 0
        seo_count = 0

        for model in [ProductSEOOptimization, BlogPostSEOOptimization, CollectionSEOOptimization]:
            try:
                if model == ProductSEOOptimization:
                    items = model.objects.filter(product__store__user=user)
                elif model == BlogPostSEOOptimization:
                    items = model.objects.filter(blog_post__blog__store__user=user)
                else:
                    items = model.objects.filter(collection__store__user=user)

                for item in items:
                    seo_bytes += len((getattr(item, 'optimized_title', '') or '').encode('utf-8'))
                    seo_bytes += len((getattr(item, 'optimized_description', '') or '').encode('utf-8'))
                    seo_bytes += len((getattr(item, 'optimized_meta_title', '') or '').encode('utf-8'))
                    seo_bytes += len((getattr(item, 'optimized_meta_description', '') or '').encode('utf-8'))
                    seo_count += 1
            except:
                pass

        if seo_bytes > 0:
            db_stats['by_category']['SEO Optimierungen'] = {
                'bytes': seo_bytes,
                'count': seo_count,
                'icon': 'fas fa-search'
            }
            db_stats['total_bytes'] += seo_bytes
    except:
        pass

    # 5. Backup Items (raw_data JSON)
    try:
        from shopify_manager.models import BackupItem
        items = BackupItem.objects.filter(backup__user=user)
        backup_bytes = 0
        for item in items:
            if item.raw_data:
                backup_bytes += len(json.dumps(item.raw_data).encode('utf-8'))
        if backup_bytes > 0:
            db_stats['by_category']['Backup Metadaten'] = {
                'bytes': backup_bytes,
                'count': items.count(),
                'icon': 'fas fa-database'
            }
            db_stats['total_bytes'] += backup_bytes
    except:
        pass

    # 6. BlogPrep Projects
    try:
        from blogprep.models import BlogPrepProject
        projects = BlogPrepProject.objects.filter(user=user)
        bp_bytes = 0
        for p in projects:
            bp_bytes += len((p.keyword or '').encode('utf-8'))
            bp_bytes += len((p.seo_title or '').encode('utf-8'))
            bp_bytes += len((p.intro_text or '').encode('utf-8'))
            bp_bytes += len((p.main_text or '').encode('utf-8'))
            bp_bytes += len((p.tips_text or '').encode('utf-8'))
            bp_bytes += len((p.custom_section or '').encode('utf-8'))
            bp_bytes += len((p.faq_text or '').encode('utf-8'))
            if p.section_images:
                bp_bytes += len(json.dumps(p.section_images).encode('utf-8'))
        if bp_bytes > 0:
            db_stats['by_category']['BlogPrep Inhalte'] = {
                'bytes': bp_bytes,
                'count': projects.count(),
                'icon': 'fas fa-pen-fancy'
            }
            db_stats['total_bytes'] += bp_bytes
    except:
        pass

    # 7. VSkript Projects
    try:
        from vskript.models import VSkriptProject
        projects = VSkriptProject.objects.filter(user=user)
        vs_bytes = 0
        for p in projects:
            vs_bytes += len((p.title or '').encode('utf-8'))
            vs_bytes += len((p.topic or '').encode('utf-8'))
            vs_bytes += len((p.script_content or '').encode('utf-8'))
            if p.scenes:
                vs_bytes += len(json.dumps(p.scenes).encode('utf-8'))
        if vs_bytes > 0:
            db_stats['by_category']['VSkript Inhalte'] = {
                'bytes': vs_bytes,
                'count': projects.count(),
                'icon': 'fas fa-film'
            }
            db_stats['total_bytes'] += vs_bytes
    except:
        pass

    # Berechne MB und KB
    db_stats['total_kb'] = db_stats['total_bytes'] / 1024
    db_stats['total_mb'] = db_stats['total_bytes'] / (1024 * 1024)

    return db_stats


@login_required
def subscription_plans(request):
    """Display available subscription plans"""
    from core.storage_service import StorageService

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

    # Tatsächlichen Speicherverbrauch aus ALLEN Apps berechnen
    storage_stats = calculate_total_storage_for_user(request.user)

    # Datenbank-Metadaten Speicher berechnen (informativ)
    db_stats = calculate_database_storage_for_user(request.user)

    context = {
        'workloom_plans': workloom_plans,
        'storage_plans': storage_plans,
        'workloom_subscription': workloom_subscription,
        'storage_subscription': storage_subscription,
        'all_user_subscriptions': all_user_subscriptions,
        'user_invoices': user_invoices,
        # Storage stats (aus allen Apps berechnet)
        'used_storage_mb': storage_stats['used_mb'],
        'max_storage_mb': storage_stats['max_mb'],
        'usage_percentage': storage_stats['percentage'],
        # Database stats (informativ, nicht Teil des Kontingents)
        'db_stats': db_stats,
    }
    return render(request, 'payments/subscription_plans.html', context)


@login_required
def create_checkout_session(request, plan_id):
    """Create Stripe checkout session"""
    if request.method == 'POST':
        try:
            plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

            # Handle FREE plans (no Stripe checkout needed)
            if plan.price == 0:
                # Create free subscription directly
                from .models import Customer, Subscription

                customer, _ = Customer.objects.get_or_create(
                    user=request.user,
                    defaults={'stripe_customer_id': None}
                )

                # Check if already subscribed
                existing = Subscription.objects.filter(
                    customer=customer,
                    plan=plan,
                    status='active'
                ).exists()

                if existing:
                    return JsonResponse({
                        'success': True,
                        'message': 'Du hast diesen Plan bereits aktiviert!',
                        'redirect_url': reverse('payments:subscription_plans')
                    })

                # Create free subscription
                Subscription.objects.create(
                    customer=customer,
                    plan=plan,
                    stripe_subscription_id=None,
                    status='active',
                    current_period_end=None,
                    cancel_at_period_end=False,
                )

                messages.success(request, f'✅ {plan.name} erfolgreich aktiviert - komplett kostenlos!')
                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('payments:subscription_plans')
                })

            # Check if Stripe is properly configured for paid plans
            if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_51234'):
                return JsonResponse({
                    'error': 'Stripe ist noch nicht konfiguriert. Bitte setzen Sie echte Stripe API-Keys in der .env Datei.'
                }, status=400)
            
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


@login_required
def subscription_statistics(request):
    """
    Subscription Statistics Dashboard
    Nur für Superuser zugänglich
    """
    from django.contrib.auth.decorators import user_passes_test
    from django.db.models import Count, Avg, Sum, Q, F
    from django.db.models.functions import TruncMonth
    from datetime import timedelta
    from django.utils import timezone
    from decimal import Decimal

    # Nur Superuser dürfen diese Seite sehen
    if not request.user.is_superuser:
        messages.error(request, 'Zugriff verweigert. Diese Seite ist nur für Administratoren.')
        return redirect('payments:subscription_plans')

    # === GRUNDLEGENDE STATISTIKEN ===

    # Alle Subscriptions
    all_subscriptions = Subscription.objects.all()
    active_subscriptions = all_subscriptions.filter(status__in=['active', 'trialing'])
    canceled_subscriptions = all_subscriptions.filter(status='canceled')

    total_subscriptions = all_subscriptions.count()
    total_active = active_subscriptions.count()
    total_canceled = canceled_subscriptions.count()

    # Subscriptions nach Plan-Typ
    workloom_subs = all_subscriptions.filter(plan__plan_type='founder_access')
    storage_subs = all_subscriptions.filter(plan__plan_type='storage')

    workloom_active = workloom_subs.filter(status__in=['active', 'trialing']).count()
    storage_active = storage_subs.filter(status__in=['active', 'trialing']).count()

    # === DURCHSCHNITTLICHE ABO-DAUER ===

    # Für gekündigte Abos: Differenz zwischen created_at und canceled_at
    canceled_with_dates = canceled_subscriptions.filter(
        canceled_at__isnull=False,
        created_at__isnull=False
    )

    avg_duration_days = None
    if canceled_with_dates.exists():
        durations = []
        for sub in canceled_with_dates:
            duration = (sub.canceled_at - sub.created_at).days
            if duration > 0:  # Nur positive Werte
                durations.append(duration)

        if durations:
            avg_duration_days = sum(durations) / len(durations)

    # Für aktive Abos: Wie lange sind sie bereits aktiv?
    active_durations = []
    for sub in active_subscriptions.filter(created_at__isnull=False):
        duration = (timezone.now() - sub.created_at).days
        if duration >= 0:
            active_durations.append(duration)

    avg_active_duration_days = sum(active_durations) / len(active_durations) if active_durations else 0

    # === UMSATZ-STATISTIKEN ===

    # Bezahlte Abos (price > 0)
    paid_active_subs = active_subscriptions.filter(plan__price__gt=0)

    # Monatlicher Umsatz (nur monatliche Pläne)
    monthly_revenue = paid_active_subs.filter(
        plan__interval='month'
    ).aggregate(
        total=Sum('plan__price')
    )['total'] or Decimal('0.00')

    # Jährlicher Umsatz (Yearly plans / 12 für monatliche Rate)
    yearly_revenue = paid_active_subs.filter(
        plan__interval='year'
    ).aggregate(
        total=Sum('plan__price')
    )['total'] or Decimal('0.00')

    # Gesamter monatlicher Umsatz (monthly + yearly/12)
    total_monthly_revenue = monthly_revenue + (yearly_revenue / 12 if yearly_revenue > 0 else Decimal('0.00'))

    # Hochgerechneter Jahresumsatz
    projected_yearly_revenue = total_monthly_revenue * 12

    # Durchschnittlicher Umsatz pro zahlendem User
    paying_users = paid_active_subs.values('customer').distinct().count()
    avg_revenue_per_user = total_monthly_revenue / paying_users if paying_users > 0 else Decimal('0.00')

    # === PLAN-VERTEILUNG ===

    # Storage Plans Verteilung
    storage_distribution = storage_active_subs = storage_subs.filter(
        status__in=['active', 'trialing']
    ).values(
        'plan__name',
        'plan__price'
    ).annotate(
        count=Count('id')
    ).order_by('-count')

    # === CHURN RATE (letzte 30 Tage) ===

    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Abos die in den letzten 30 Tagen gekündigt wurden
    recent_cancellations = canceled_subscriptions.filter(
        canceled_at__gte=thirty_days_ago
    ).count()

    # Aktive Abos vor 30 Tagen (ungefähre Berechnung)
    active_30_days_ago = active_subscriptions.filter(
        created_at__lte=thirty_days_ago
    ).count() + recent_cancellations

    churn_rate = (recent_cancellations / active_30_days_ago * 100) if active_30_days_ago > 0 else 0

    # === NEUE ABOS PRO MONAT ===

    # Letzte 6 Monate
    six_months_ago = timezone.now() - timedelta(days=180)

    new_subs_by_month = all_subscriptions.filter(
        created_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    # === KÜNDIGUNGEN PRO MONAT ===

    cancellations_by_month = canceled_subscriptions.filter(
        canceled_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('canceled_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    # === TOP KUNDEN (nach Umsatz) ===

    top_customers = paid_active_subs.values(
        'customer__user__username',
        'customer__user__email',
        'plan__name',
        'plan__price'
    ).order_by('-plan__price')[:10]

    # === TRIAL CONVERSIONS ===

    # Abos die mal trialing waren
    trial_subs = all_subscriptions.filter(
        Q(status='trialing') | Q(trial_start__isnull=False)
    )

    # Konvertierte Trials (von trialing zu active)
    converted_trials = trial_subs.filter(status='active').count()
    total_trials = trial_subs.count()

    trial_conversion_rate = (converted_trials / total_trials * 100) if total_trials > 0 else 0

    # === RECENT ACTIVITY ===

    # Letzte 10 Subscriptions
    recent_subscriptions = all_subscriptions.select_related(
        'customer__user', 'plan'
    ).order_by('-created_at')[:10]

    # Letzte 10 Kündigungen
    recent_cancellations_list = canceled_subscriptions.select_related(
        'customer__user', 'plan'
    ).order_by('-canceled_at')[:10]

    # === CONTEXT ZUSAMMENSTELLEN ===

    context = {
        # Grundlegende Zahlen
        'total_subscriptions': total_subscriptions,
        'total_active': total_active,
        'total_canceled': total_canceled,
        'workloom_active': workloom_active,
        'storage_active': storage_active,

        # Durchschnittliche Dauer
        'avg_duration_days': round(avg_duration_days) if avg_duration_days else 'N/A',
        'avg_active_duration_days': round(avg_active_duration_days),

        # Umsatz
        'monthly_revenue': total_monthly_revenue,
        'projected_yearly_revenue': projected_yearly_revenue,
        'paying_users': paying_users,
        'avg_revenue_per_user': avg_revenue_per_user,

        # Verteilung
        'storage_distribution': storage_distribution,

        # Churn
        'churn_rate': round(churn_rate, 2),
        'recent_cancellations_count': recent_cancellations,

        # Timeline
        'new_subs_by_month': list(new_subs_by_month),
        'cancellations_by_month': list(cancellations_by_month),

        # Top Kunden
        'top_customers': list(top_customers),

        # Trials
        'trial_conversion_rate': round(trial_conversion_rate, 2),
        'total_trials': total_trials,
        'converted_trials': converted_trials,

        # Recent Activity
        'recent_subscriptions': recent_subscriptions,
        'recent_cancellations_list': recent_cancellations_list,
    }

    return render(request, 'payments/subscription_statistics.html', context)


@login_required
def subscriptions_management(request):
    """
    Subscriptions Management - Frontend View
    Zeigt alle Subscriptions wie im Admin, aber im Frontend-Design
    """
    if not request.user.is_superuser:
        messages.error(request, 'Zugriff verweigert.')
        return redirect('payments:subscription_plans')

    from django.db.models import Q

    # Filter parameter
    status_filter = request.GET.get('status', 'all')
    plan_type_filter = request.GET.get('plan_type', 'all')
    search_query = request.GET.get('search', '')

    # Base queryset
    subscriptions = Subscription.objects.select_related(
        'customer__user', 'plan'
    ).order_by('-created_at')

    # Apply filters
    if status_filter != 'all':
        subscriptions = subscriptions.filter(status=status_filter)

    if plan_type_filter != 'all':
        subscriptions = subscriptions.filter(plan__plan_type=plan_type_filter)

    if search_query:
        subscriptions = subscriptions.filter(
            Q(customer__user__username__icontains=search_query) |
            Q(customer__user__email__icontains=search_query) |
            Q(plan__name__icontains=search_query)
        )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(subscriptions, 50)  # 50 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_count = subscriptions.count()
    active_count = subscriptions.filter(status__in=['active', 'trialing']).count()
    canceled_count = subscriptions.filter(status='canceled').count()

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'plan_type_filter': plan_type_filter,
        'search_query': search_query,
        'total_count': total_count,
        'active_count': active_count,
        'canceled_count': canceled_count,
    }

    return render(request, 'payments/subscriptions_management.html', context)


@login_required
def storage_logs_view(request):
    """
    Storage Logs - Frontend View
    Zeigt alle Storage Logs wie im Admin
    """
    if not request.user.is_superuser:
        messages.error(request, 'Zugriff verweigert.')
        return redirect('payments:subscription_plans')

    from core.models import StorageLog
    from django.db.models import Q

    # Filter
    action_filter = request.GET.get('action', 'all')
    app_filter = request.GET.get('app', 'all')
    search_query = request.GET.get('search', '')

    # Base queryset
    logs = StorageLog.objects.select_related('user').order_by('-created_at')

    # Apply filters
    if action_filter != 'all':
        logs = logs.filter(action=action_filter)

    if app_filter != 'all':
        logs = logs.filter(app=app_filter)

    if search_query:
        logs = logs.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(file_name__icontains=search_query)
        )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_count = logs.count()
    upload_count = logs.filter(action='upload').count()
    delete_count = logs.filter(action='delete').count()

    # Total size
    from django.db.models import Sum
    total_uploaded = logs.filter(action='upload').aggregate(Sum('size_bytes'))['size_bytes__sum'] or 0
    total_deleted = logs.filter(action='delete').aggregate(Sum('size_bytes'))['size_bytes__sum'] or 0

    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'app_filter': app_filter,
        'search_query': search_query,
        'total_count': total_count,
        'upload_count': upload_count,
        'delete_count': delete_count,
        'total_uploaded_mb': total_uploaded / (1024 * 1024),
        'total_deleted_mb': total_deleted / (1024 * 1024),
    }

    return render(request, 'payments/storage_logs.html', context)


@login_required
def user_storage_view(request):
    """
    User Storage Overview - Frontend View
    Zeigt alle User Storage wie im Admin
    """
    if not request.user.is_superuser:
        messages.error(request, 'Zugriff verweigert.')
        return redirect('payments:subscription_plans')

    from videos.models import UserStorage
    from django.db.models import Q, F, Sum, Avg

    # Filter
    plan_filter = request.GET.get('plan', 'all')
    search_query = request.GET.get('search', '')

    # Base queryset
    storages = UserStorage.objects.select_related('user').order_by('-used_storage')

    # Apply filters
    if plan_filter == 'free':
        storages = storages.filter(max_storage=104857600)  # 100MB
    elif plan_filter == 'premium':
        storages = storages.filter(max_storage__gt=104857600)

    if search_query:
        storages = storages.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(storages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_count = storages.count()
    total_used = storages.aggregate(Sum('used_storage'))['used_storage__sum'] or 0
    total_max = storages.aggregate(Sum('max_storage'))['max_storage__sum'] or 0
    avg_usage = storages.aggregate(Avg('used_storage'))['used_storage__avg'] or 0

    # Users over 75%
    over_75_percent = storages.filter(
        used_storage__gte=F('max_storage') * 0.75
    ).count()

    context = {
        'page_obj': page_obj,
        'plan_filter': plan_filter,
        'search_query': search_query,
        'total_count': total_count,
        'total_used_gb': total_used / (1024 * 1024 * 1024),
        'total_max_gb': total_max / (1024 * 1024 * 1024),
        'avg_usage_mb': avg_usage / (1024 * 1024),
        'over_75_percent': over_75_percent,
    }

    return render(request, 'payments/user_storage.html', context)


@login_required
def webhook_events_view(request):
    """
    Webhook Events - Frontend View
    Zeigt alle Stripe Webhook Events
    """
    if not request.user.is_superuser:
        messages.error(request, 'Zugriff verweigert.')
        return redirect('payments:subscription_plans')

    from django.db.models import Q

    # Filter
    event_type_filter = request.GET.get('event_type', 'all')
    processed_filter = request.GET.get('processed', 'all')
    search_query = request.GET.get('search', '')

    # Base queryset
    events = WebhookEvent.objects.order_by('-created_at')

    # Apply filters
    if event_type_filter != 'all':
        events = events.filter(event_type=event_type_filter)

    if processed_filter == 'yes':
        events = events.filter(processed=True)
    elif processed_filter == 'no':
        events = events.filter(processed=False)

    if search_query:
        events = events.filter(
            Q(stripe_event_id__icontains=search_query) |
            Q(event_type__icontains=search_query)
        )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Stats
    total_count = events.count()
    processed_count = events.filter(processed=True).count()
    failed_count = events.filter(processed=False).exclude(processing_error='').count()

    # Event types
    event_types = events.values_list('event_type', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'event_type_filter': event_type_filter,
        'processed_filter': processed_filter,
        'search_query': search_query,
        'total_count': total_count,
        'processed_count': processed_count,
        'failed_count': failed_count,
        'event_types': list(event_types),
    }

    return render(request, 'payments/webhook_events.html', context)


@login_required
def user_files_api(request):
    """
    API endpoint for user's files
    Returns list of all actually existing files (not deleted ones)
    """
    import os

    files = []
    totals = {}

    # Videos
    try:
        from videos.models import Video
        videos = Video.objects.filter(user=request.user, video_file__isnull=False)
        video_total = 0
        for video in videos:
            if video.video_file and hasattr(video.video_file, 'size'):
                size = video.video_file.size
                video_total += size

                # Use video title as filename, fallback to actual filename
                display_filename = video.title if video.title else os.path.basename(video.video_file.name)
                # Add .webm extension if title doesn't have an extension
                if video.title and '.' not in display_filename:
                    display_filename = f"{display_filename}.webm"

                files.append({
                    'id': f'video_{video.id}',
                    'app': 'Videos',
                    'app_name': 'videos',
                    'filename': display_filename,
                    'size': size,
                    'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                    'created_at': video.created_at.strftime('%d.%m.%Y %H:%M'),
                    'metadata': {'video_id': video.id, 'title': video.title},
                })
        if video_total > 0:
            totals['Videos'] = {'bytes': video_total, 'mb': video_total / (1024 * 1024)}
    except Exception as e:
        logger.error(f"Error loading videos: {e}")

    # Fileshare
    try:
        from fileshare.models import TransferFile
        fileshare_files = TransferFile.objects.filter(
            transfer__sender=request.user,
            file__isnull=False
        ).select_related('transfer')
        fileshare_total = 0
        for fs_file in fileshare_files:
            if fs_file.file and hasattr(fs_file.file, 'size'):
                size = fs_file.file.size
                fileshare_total += size
                files.append({
                    'id': f'fileshare_{fs_file.id}',
                    'app': 'Fileshare',
                    'app_name': 'fileshare',
                    'filename': fs_file.original_filename or os.path.basename(fs_file.file.name),
                    'size': size,
                    'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                    'created_at': fs_file.uploaded_at.strftime('%d.%m.%Y %H:%M'),
                    'metadata': {'file_id': str(fs_file.id), 'transfer_id': fs_file.transfer.id},
                })
        if fileshare_total > 0:
            totals['Fileshare'] = {'bytes': fileshare_total, 'mb': fileshare_total / (1024 * 1024)}
    except Exception as e:
        logger.error(f"Error loading fileshare files: {e}")

    # Organization - Notes with images
    try:
        from organization.models import Note, BoardElement
        from django.core.files.storage import default_storage
        notes = Note.objects.filter(author=request.user, image__isnull=False)
        org_total = 0
        for note in notes:
            if note.image and hasattr(note.image, 'size'):
                size = note.image.size
                org_total += size

                # Generate readable filename from note title
                original_filename = os.path.basename(note.image.name)
                file_ext = os.path.splitext(original_filename)[1]  # Get extension (.jpg, .png, etc.)
                display_filename = f"{note.title}{file_ext}" if note.title else original_filename

                files.append({
                    'id': f'note_{note.id}',
                    'app': 'Organization',
                    'app_name': 'organization',
                    'filename': display_filename,
                    'size': size,
                    'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                    'created_at': note.created_at.strftime('%d.%m.%Y %H:%M'),
                    'metadata': {'note_id': note.id, 'title': note.title, 'file_type': 'note_image'},
                })

        # Organization - Board images
        board_elements = BoardElement.objects.filter(
            created_by=request.user,
            element_type='image'
        ).select_related('board')

        for element in board_elements:
            try:
                element_data = element.data if isinstance(element.data, dict) else {}
                image_url = element_data.get('url') or element_data.get('src')
                if not image_url:
                    continue

                import re
                match = re.search(r'board_images/[^/\s]+', image_url)
                if not match:
                    continue

                file_path = match.group(0)
                if default_storage.exists(file_path):
                    size = default_storage.size(file_path)
                    org_total += size

                    # Generate readable filename from board title
                    original_filename = os.path.basename(file_path)
                    file_ext = os.path.splitext(original_filename)[1]  # Get extension
                    display_filename = f"{element.board.title}-Bild{file_ext}" if element.board.title else original_filename

                    files.append({
                        'id': f'board_element_{element.id}',
                        'app': 'Organization',
                        'app_name': 'organization',
                        'filename': display_filename,
                        'size': size,
                        'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                        'created_at': element.created_at.strftime('%d.%m.%Y %H:%M'),
                        'metadata': {
                            'board_id': element.board.id,
                            'board_title': element.board.title,
                            'element_id': element.id,
                            'file_type': 'board_image'
                        },
                    })
            except Exception as e:
                logger.error(f"Error processing board element {element.id}: {e}")
                continue

        if org_total > 0:
            totals['Organization'] = {'bytes': org_total, 'mb': org_total / (1024 * 1024)}
    except Exception as e:
        logger.error(f"Error loading organization files: {e}")

    # Chat attachments
    try:
        from chat.models import ChatMessageAttachment
        attachments = ChatMessageAttachment.objects.filter(
            message__sender=request.user,
            file__isnull=False
        ).select_related('message')
        chat_total = 0
        for attachment in attachments:
            if attachment.file and hasattr(attachment.file, 'size'):
                size = attachment.file.size
                chat_total += size
                files.append({
                    'id': f'chat_{attachment.id}',
                    'app': 'Chat',
                    'app_name': 'chat',
                    'filename': attachment.filename or os.path.basename(attachment.file.name),
                    'size': size,
                    'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                    'created_at': attachment.uploaded_at.strftime('%d.%m.%Y %H:%M'),
                    'metadata': {'attachment_id': attachment.id, 'message_id': attachment.message.id},
                })
        if chat_total > 0:
            totals['Chat'] = {'bytes': chat_total, 'mb': chat_total / (1024 * 1024)}
    except Exception as e:
        logger.error(f"Error loading chat files: {e}")

    # Streamrec - Audio and Video recordings (stored directly on filesystem)
    try:
        from django.conf import settings
        from django.core.files.storage import default_storage
        import glob
        from datetime import datetime

        user_prefix = f"{request.user.id}_"
        streamrec_total = 0

        # Process both audio and video recordings
        recording_types = [
            ('audio_recordings', 'audio'),
            ('video_recordings', 'video')
        ]

        for dir_name, rec_type in recording_types:
            rec_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
            if os.path.exists(rec_dir):
                # Find all files for this user (format: {user_id}_{filename})
                for file_path in glob.glob(os.path.join(rec_dir, f"{user_prefix}*")):
                    try:
                        size = os.path.getsize(file_path)
                        streamrec_total += size

                        # Extract filename without user prefix
                        filename = os.path.basename(file_path)
                        original_filename = filename[len(user_prefix):]

                        # Get file modification time
                        mtime = os.path.getmtime(file_path)
                        created_at = datetime.fromtimestamp(mtime)

                        files.append({
                            'id': f'streamrec_{filename}',  # Use full filename as ID
                            'app': 'Streamrec',
                            'app_name': 'streamrec',
                            'filename': original_filename,
                            'size': size,
                            'size_display': f"{size/(1024*1024):.2f} MB" if size >= 1024*1024 else f"{size/1024:.2f} KB",
                            'created_at': created_at.strftime('%d.%m.%Y %H:%M'),
                            'metadata': {'file_path': file_path, 'recording_type': rec_type},
                        })
                    except Exception as e:
                        logger.error(f"Error processing streamrec file {file_path}: {e}")
                        continue

        if streamrec_total > 0:
            totals['Streamrec'] = {'bytes': streamrec_total, 'mb': streamrec_total / (1024 * 1024)}
    except Exception as e:
        logger.error(f"Error loading streamrec files: {e}")

    # Sort files by creation date (newest first)
    files.sort(key=lambda x: x['created_at'], reverse=True)

    return JsonResponse({
        'success': True,
        'files': files,
        'totals': totals,
        'total_files': len(files),
    })


@login_required
@require_POST
def delete_user_file_api(request):
    """
    API endpoint to delete a user file
    Deletes the actual file and updates storage tracking
    """
    from core.storage_service import StorageService
    from django.core.files.storage import default_storage
    import re

    try:
        data = json.loads(request.body)
        file_id = data.get('log_id')  # Actually file_id with format: app_objectid

        if not file_id:
            return JsonResponse({'success': False, 'error': 'Keine Datei-ID angegeben'}, status=400)

        # Parse file_id to get app type and object id
        parts = file_id.split('_', 1)
        if len(parts) != 2:
            return JsonResponse({'success': False, 'error': 'Ungültige Datei-ID'}, status=400)

        app_type, object_id = parts
        deleted = False

        if app_type == 'video':
            # Delete video file
            from videos.models import Video
            try:
                video = Video.objects.get(id=int(object_id), user=request.user)
                video.delete()  # Signals will handle storage tracking
                deleted = True
            except (Video.DoesNotExist, ValueError):
                return JsonResponse({'success': False, 'error': 'Video nicht gefunden'}, status=404)

        elif app_type == 'fileshare':
            # Delete fileshare file
            from fileshare.models import TransferFile
            try:
                # TransferFile uses UUID, not int
                fs_file = TransferFile.objects.filter(
                    id=object_id,
                    transfer__sender=request.user
                ).first()
                if fs_file:
                    fs_file.delete()  # Signals will handle storage tracking
                    deleted = True
                else:
                    return JsonResponse({'success': False, 'error': 'Datei nicht gefunden'}, status=404)
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Ungültige Datei-ID'}, status=400)

        elif app_type == 'note':
            # Delete note image
            from organization.models import Note
            try:
                note = Note.objects.get(id=int(object_id), author=request.user)
                if note.image:
                    note.delete()  # Delete entire note (signals will track deletion)
                    deleted = True
                else:
                    return JsonResponse({'success': False, 'error': 'Note hat kein Bild'}, status=400)
            except (Note.DoesNotExist, ValueError):
                return JsonResponse({'success': False, 'error': 'Notiz nicht gefunden'}, status=404)

        elif app_type == 'board':
            # Delete board element image
            from organization.models import BoardElement
            try:
                element_id = object_id.replace('element_', '')
                element = BoardElement.objects.get(id=int(element_id), created_by=request.user)
                element.delete()  # Signals will handle storage tracking
                deleted = True
            except (BoardElement.DoesNotExist, ValueError):
                return JsonResponse({'success': False, 'error': 'Board-Element nicht gefunden'}, status=404)

        elif app_type == 'chat':
            # Delete chat attachment
            from chat.models import ChatMessageAttachment
            try:
                attachment = ChatMessageAttachment.objects.get(id=int(object_id), message__sender=request.user)
                attachment.delete()  # Signals will handle storage tracking
                deleted = True
            except (ChatMessageAttachment.DoesNotExist, ValueError):
                return JsonResponse({'success': False, 'error': 'Anhang nicht gefunden'}, status=404)

        elif app_type == 'streamrec':
            # Delete streamrec audio/video recording (direct filesystem file)
            from django.conf import settings
            from streamrec.storage_helpers import track_recording_deletion
            try:
                # object_id is the full filename (including user prefix)
                # Try to find file in both audio and video directories
                user_prefix = f"{request.user.id}_"

                # Verify file belongs to user
                if not object_id.startswith(user_prefix):
                    return JsonResponse({'success': False, 'error': 'Keine Berechtigung'}, status=403)

                file_path = None
                recording_type = None

                # Check both directories
                for dir_name, rec_type in [('audio_recordings', 'audio'), ('video_recordings', 'video')]:
                    check_path = os.path.join(settings.MEDIA_ROOT, dir_name, object_id)
                    if os.path.exists(check_path):
                        file_path = check_path
                        recording_type = rec_type
                        break

                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)

                    # Delete file
                    os.remove(file_path)

                    # Track deletion in storage system
                    track_recording_deletion(
                        request.user,
                        file_size,
                        object_id[len(user_prefix):],  # Remove user prefix
                        recording_type=recording_type
                    )

                    deleted = True
                else:
                    return JsonResponse({'success': False, 'error': 'Datei nicht gefunden'}, status=404)
            except Exception as e:
                logger.error(f"Error deleting streamrec file: {e}")
                return JsonResponse({'success': False, 'error': f'Fehler beim Löschen: {str(e)}'}, status=500)

        else:
            return JsonResponse({'success': False, 'error': f'Unbekannter App-Typ: {app_type}'}, status=400)

        if deleted:
            return JsonResponse({
                'success': True,
                'message': 'Datei erfolgreich gelöscht'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Datei konnte nicht gefunden oder gelöscht werden'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige Anfrage'}, status=400)
    except Exception as e:
        logger.error(f"Error deleting user file: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen: {str(e)}'
        }, status=500)


@login_required
def user_storage_detail_api(request, user_id):
    """
    API endpoint for superusers to get detailed storage breakdown for a specific user.
    Returns per-app storage usage.
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Zugriff verweigert'}, status=403)

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User nicht gefunden'}, status=404)

    # Speicher neu berechnen bevor Details angezeigt werden
    from core.storage_service import StorageService
    StorageService.recalculate_storage(target_user)

    apps = {}

    # Videos
    try:
        from videos.models import Video
        videos = Video.objects.filter(user=target_user, video_file__isnull=False)
        video_total = 0
        video_count = 0
        for video in videos:
            if video.video_file and hasattr(video.video_file, 'size'):
                try:
                    video_total += video.video_file.size
                    video_count += 1
                except:
                    pass
        if video_total > 0:
            apps['Videos'] = {'bytes': video_total, 'mb': video_total / (1024 * 1024), 'count': video_count, 'icon': 'fas fa-video'}
    except Exception as e:
        logger.error(f"Error calculating videos storage for user {user_id}: {e}")

    # Fileshare
    try:
        from fileshare.models import TransferFile
        files = TransferFile.objects.filter(transfer__sender=target_user, file__isnull=False)
        fs_total = 0
        fs_count = 0
        for f in files:
            if f.file and hasattr(f.file, 'size'):
                try:
                    fs_total += f.file.size
                    fs_count += 1
                except:
                    pass
        if fs_total > 0:
            apps['Fileshare'] = {'bytes': fs_total, 'mb': fs_total / (1024 * 1024), 'count': fs_count, 'icon': 'fas fa-share-alt'}
    except Exception as e:
        logger.error(f"Error calculating fileshare storage for user {user_id}: {e}")

    # Chat
    try:
        from chat.models import ChatMessageAttachment
        attachments = ChatMessageAttachment.objects.filter(message__sender=target_user, file__isnull=False)
        chat_total = 0
        chat_count = 0
        for att in attachments:
            if att.file and hasattr(att.file, 'size'):
                try:
                    chat_total += att.file.size
                    chat_count += 1
                except:
                    pass
        if chat_total > 0:
            apps['Chat'] = {'bytes': chat_total, 'mb': chat_total / (1024 * 1024), 'count': chat_count, 'icon': 'fas fa-comments'}
    except Exception as e:
        logger.error(f"Error calculating chat storage for user {user_id}: {e}")

    # Organization (Notes + Board Images)
    try:
        from organization.models import Note, BoardElement
        from django.core.files.storage import default_storage
        import re

        org_total = 0
        org_count = 0

        notes = Note.objects.filter(author=target_user, image__isnull=False)
        for note in notes:
            if note.image and hasattr(note.image, 'size'):
                try:
                    org_total += note.image.size
                    org_count += 1
                except:
                    pass

        board_elements = BoardElement.objects.filter(created_by=target_user, element_type='image')
        for element in board_elements:
            try:
                element_data = element.data if isinstance(element.data, dict) else {}
                image_url = element_data.get('url') or element_data.get('src')
                if not image_url:
                    continue
                match = re.search(r'board_images/[^/\s]+', image_url)
                if match and default_storage.exists(match.group(0)):
                    org_total += default_storage.size(match.group(0))
                    org_count += 1
            except:
                pass

        if org_total > 0:
            apps['Organization'] = {'bytes': org_total, 'mb': org_total / (1024 * 1024), 'count': org_count, 'icon': 'fas fa-building'}
    except Exception as e:
        logger.error(f"Error calculating organization storage for user {user_id}: {e}")

    # Streamrec
    try:
        user_prefix = f"{target_user.id}_"
        streamrec_total = 0
        streamrec_count = 0
        for dir_name in ['audio_recordings', 'video_recordings']:
            media_dir = os.path.join(settings.MEDIA_ROOT, dir_name)
            if os.path.exists(media_dir):
                for filename in os.listdir(media_dir):
                    if filename.startswith(user_prefix):
                        filepath = os.path.join(media_dir, filename)
                        if os.path.isfile(filepath):
                            streamrec_total += os.path.getsize(filepath)
                            streamrec_count += 1
        if streamrec_total > 0:
            apps['Streamrec'] = {'bytes': streamrec_total, 'mb': streamrec_total / (1024 * 1024), 'count': streamrec_count, 'icon': 'fas fa-microphone'}
    except Exception as e:
        logger.error(f"Error calculating streamrec storage for user {user_id}: {e}")

    # Ideopin (Pinterest Pin Generator)
    try:
        from ideopin.models import PinProject, Pin
        ideopin_total = 0
        ideopin_count = 0

        # PinProject Bilder
        pin_projects = PinProject.objects.filter(user=target_user)
        for project in pin_projects:
            for field_name in ['product_image', 'generated_image', 'final_image']:
                field = getattr(project, field_name, None)
                if field and hasattr(field, 'size'):
                    try:
                        ideopin_total += field.size
                        ideopin_count += 1
                    except:
                        pass

        # Pin Bilder (Multi-Pin)
        pins = Pin.objects.filter(project__user=target_user)
        for pin in pins:
            for field_name in ['generated_image', 'final_image']:
                field = getattr(pin, field_name, None)
                if field and hasattr(field, 'size'):
                    try:
                        ideopin_total += field.size
                        ideopin_count += 1
                    except:
                        pass

        if ideopin_total > 0:
            apps['Ideopin'] = {'bytes': ideopin_total, 'mb': ideopin_total / (1024 * 1024), 'count': ideopin_count, 'icon': 'fab fa-pinterest'}
    except Exception as e:
        logger.error(f"Error calculating ideopin storage for user {user_id}: {e}")

    # Image Editor
    try:
        from image_editor.models import ImageProject, AIGenerationHistory
        img_total = 0
        img_count = 0
        projects = ImageProject.objects.filter(user=target_user)
        for project in projects:
            for field in ['original_image', 'processed_image']:
                img = getattr(project, field, None)
                if img and hasattr(img, 'size'):
                    try:
                        img_total += img.size
                        img_count += 1
                    except:
                        pass
        histories = AIGenerationHistory.objects.filter(project__user=target_user, output_image__isnull=False)
        for history in histories:
            if history.output_image and hasattr(history.output_image, 'size'):
                try:
                    img_total += history.output_image.size
                    img_count += 1
                except:
                    pass
        if img_total > 0:
            apps['Image Editor'] = {'bytes': img_total, 'mb': img_total / (1024 * 1024), 'count': img_count, 'icon': 'fas fa-image'}
    except Exception as e:
        logger.error(f"Error calculating image editor storage for user {user_id}: {e}")

    # LearnLoom
    try:
        from learnloom.models import Document
        ll_total = 0
        ll_count = 0
        docs = Document.objects.filter(user=target_user, file__isnull=False)
        for doc in docs:
            if doc.file and hasattr(doc.file, 'size'):
                try:
                    ll_total += doc.file.size
                    ll_count += 1
                except:
                    pass
        if ll_total > 0:
            apps['LearnLoom'] = {'bytes': ll_total, 'mb': ll_total / (1024 * 1024), 'count': ll_count, 'icon': 'fas fa-book'}
    except Exception as e:
        logger.error(f"Error calculating learnloom storage for user {user_id}: {e}")

    # Shopify Backups
    try:
        from shopify_manager.models import ShopifyBackup
        backup_total = 0
        backup_count = 0
        backups = ShopifyBackup.objects.filter(user=target_user, status='completed')
        for backup in backups:
            if backup.total_size_bytes > 0:
                backup_total += backup.total_size_bytes
                backup_count += 1
        if backup_total > 0:
            apps['Shopify Backups'] = {'bytes': backup_total, 'mb': backup_total / (1024 * 1024), 'count': backup_count, 'icon': 'fas fa-cloud-download-alt'}
    except Exception as e:
        logger.error(f"Error calculating shopify backups storage for user {user_id}: {e}")

    # Calculate totals
    total_bytes = sum(app['bytes'] for app in apps.values())
    total_mb = total_bytes / (1024 * 1024)

    # Get user's storage quota
    from videos.models import UserStorage
    try:
        user_storage = UserStorage.objects.get(user=target_user)
        max_bytes = user_storage.max_storage
        max_mb = max_bytes / (1024 * 1024)
        percentage = (total_bytes / max_bytes * 100) if max_bytes > 0 else 0
    except UserStorage.DoesNotExist:
        max_bytes = 100 * 1024 * 1024  # Default 100MB
        max_mb = 100
        percentage = (total_bytes / max_bytes * 100)

    # Sort apps by usage (highest first)
    sorted_apps = dict(sorted(apps.items(), key=lambda x: x[1]['bytes'], reverse=True))

    return JsonResponse({
        'success': True,
        'user_id': user_id,
        'username': target_user.username,
        'email': target_user.email,
        'total_bytes': total_bytes,
        'total_mb': round(total_mb, 2),
        'max_mb': round(max_mb, 2),
        'percentage': round(percentage, 2),
        'apps': sorted_apps
    })
