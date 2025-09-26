from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db import models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
import json
import logging
import secrets
import uuid
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AmpelCategoryForm, CategoryKeywordForm, KeywordBulkForm, ApiKeyForm, CompanyInfoForm, UserProfileForm, CustomPasswordChangeForm, SuperUserManagementForm, BugChatSettingsForm, AppPermissionForm, FeatureAccessForm, BulkFeatureAccessForm, FeatureAccessFilterForm, CustomPasswordResetForm, CustomSetPasswordForm
from .models import CustomUser, AmpelCategory, CategoryKeyword, UserLoginHistory, EditableContent, CustomPage, SEOSettings, FeatureAccess, AppUsageTracking, AppInfo, ZohoAPISettings, AppPermission, UserAppPermission
from naturmacher.models import APIBalance
from videos.models import UserStorage as VideoUserStorage, Subscription as VideoSubscription
from .utils import redirect_with_params

logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'
    success_url = reverse_lazy('accounts:dashboard')
    
    def form_valid(self, form):
        user = form.get_user()
        
        # Prüfe ob E-Mail verifiziert ist
        if not user.email_verified:
            messages.error(self.request, 
                'Ihr Konto ist noch nicht aktiviert. Bitte bestätigen Sie Ihre E-Mail-Adresse.')
            return redirect('accounts:resend_verification')
        
        return super().form_valid(form)


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:signup_success')
    
    def form_valid(self, form):
        # Benutzer erstellen aber nicht aktivieren
        user = form.save(commit=False)
        user.is_active = False  # Benutzer erst nach E-Mail-Verifikation aktivieren
        user.save()
        
        # Sende Verifikations-E-Mail
        if send_verification_email(user, self.request):
            messages.success(self.request, 
                f'Ihr Konto wurde erstellt! Wir haben eine Bestätigungs-E-Mail an {user.email} gesendet. '
                'Bitte klicken Sie auf den Link in der E-Mail, um Ihr Konto zu aktivieren.')
        else:
            messages.warning(self.request, 
                'Ihr Konto wurde erstellt, aber es gab ein Problem beim Senden der Bestätigungs-E-Mail. '
                'Bitte versuchen Sie es über "E-Mail erneut senden" noch einmal.')
        
        # Setze self.object für den Erfolgscase
        self.object = user
        return super(CreateView, self).form_valid(form)


def signup_success(request):
    """Zeigt die Erfolgsseite nach der Registrierung."""
    return render(request, 'accounts/signup_success.html')


@login_required
def dashboard(request):
    """Dashboard mit Übersicht der benutzerdefinierten Kategorien."""
    if request.method == 'POST':
        # Toggle für benutzerdefinierte Kategorien
        use_custom = request.POST.get('use_custom_categories') == 'on'
        request.user.use_custom_categories = use_custom
        
        # Toggle für KI-Keyword-Erweiterung
        enable_ai_expansion = request.POST.get('enable_ai_keyword_expansion') == 'on'
        request.user.enable_ai_keyword_expansion = enable_ai_expansion
        
        # Toggle für Dark Mode
        dark_mode = request.POST.get('dark_mode') == 'on'
        request.user.dark_mode = dark_mode
        
        request.user.save()
        
        # Feedback-Nachrichten
        if use_custom:
            messages.success(request, 'Benutzerdefinierte Kategorien wurden aktiviert.')
        else:
            messages.info(request, 'Standard-Kategorien werden verwendet.')
            
        if enable_ai_expansion and use_custom:
            messages.success(request, 'KI-Keyword-Erweiterung für Ihre Kategorien wurde aktiviert.')
        elif enable_ai_expansion and not use_custom:
            messages.warning(request, 'KI-Keyword-Erweiterung ist nur mit benutzerdefinierten Kategorien verfügbar.')
        elif not enable_ai_expansion:
            messages.info(request, 'KI-Keyword-Erweiterung wurde deaktiviert.')
        
        # Dark Mode Feedback
        if dark_mode:
            messages.success(request, 'Dunkles Design wurde aktiviert.')
        else:
            messages.info(request, 'Helles Design wurde aktiviert.')
        
        return redirect('accounts:dashboard')
    
    categories = AmpelCategory.objects.filter(user=request.user)
    
    # Generiere verfügbare Apps basierend auf Berechtigungen
    from .models import AppPermission
    
    # App-Definitionen mit URLs, Icons und Kategorien
    app_definitions = {
        'chat': {
            'name': 'Chat System',
            'description': 'Kommunizieren Sie direkt mit anderen Nutzern über unser integriertes Chat-System.',
            'icon': 'bi-chat-dots',
            'url': 'chat:home',
            'color': 'bg-primary',
            'category': 'communication'
        },
        'videos': {
            'name': 'Videos',
            'description': 'Verwalten und teilen Sie Ihre Video-Inhalte sicher und effizient.',
            'icon': 'bi-play-circle',
            'url': 'videos:list',
            'color': 'bg-danger',
            'category': 'media'
        },
        'schuch': {
            'name': 'Schuch Startseite',
            'description': 'Zugriff auf die zentrale Schuch Startseite und Kernfunktionen.',
            'icon': 'bi-house',
            'url': 'startseite',
            'color': 'bg-primary',
            'category': 'dashboard'
        },
        'schuch_dashboard': {
            'name': 'Schuch Dashboard',
            'description': 'Erweiterte Dashboard-Funktionen und Übersichten.',
            'icon': 'bi-speedometer2',
            'url': 'chat:schuch_dashboard',
            'color': 'bg-info',
            'category': 'dashboard'
        },
        'wirtschaftlichkeitsrechner': {
            'name': 'Wirtschaftlichkeitsrechner',
            'description': 'Berechnen Sie die Wirtschaftlichkeit Ihrer Projekte mit unserem professionellen Tool.',
            'icon': 'bi-calculator',
            'url': 'amortization_calculator:rechner_start',
            'color': 'bg-success',
            'category': 'tools'
        },
        'sportplatz_konfigurator': {
            'name': 'Sportplatz-Konfigurator',
            'description': 'Planen und konfigurieren Sie Sportplätze nach Ihren spezifischen Anforderungen.',
            'icon': 'bi-grid-3x3',
            'url': 'sportplatzApp:sportplatz_start',
            'color': 'bg-info',
            'category': 'tools'
        },
        'pdf_suche': {
            'name': 'PDF-Suche',
            'description': 'Durchsuchen Sie Ihre PDF-Dokumente schnell und effizient nach Inhalten.',
            'icon': 'bi-file-pdf',
            'url': 'pdf_sucher:pdf_suche',
            'color': 'bg-danger',
            'category': 'tools'
        },
        'ki_zusammenfassung': {
            'name': 'KI-Zusammenfassung',
            'description': 'Lassen Sie wichtige Dokumente automatisch durch KI zusammenfassen.',
            'icon': 'bi-robot',
            'url': 'pdf_sucher:document_list',
            'color': 'bg-secondary',
            'category': 'ai'
        },
        'shopify': {
            'name': 'Shopify Integration',
            'description': 'Verwalten Sie Ihre Shopify-Daten und synchronisieren Sie Produktinformationen.',
            'icon': 'bi-shop',
            'url': 'shopify_manager:dashboard',
            'color': 'bg-success',
            'category': 'ecommerce'
        },
        'bilder': {
            'name': 'Bilder-Editor',
            'description': 'Bearbeiten und optimieren Sie Bilder direkt in der Anwendung.',
            'icon': 'bi-image',
            'url': 'image_editor:dashboard',
            'color': 'bg-info',
            'category': 'media'
        },
        'organisation': {
            'name': 'Organisation',
            'description': 'Verwalten Sie Organisationsstrukturen und Zuständigkeiten.',
            'icon': 'bi-building',
            'url': 'organization:dashboard',
            'color': 'bg-secondary',
            'category': 'management'
        },
        'schulungen': {
            'name': 'Schulungen',
            'description': 'Zugriff auf Schulungsmaterialien und Weiterbildungsangebote.',
            'icon': 'bi-book',
            'url': 'naturmacher:thema_list',
            'color': 'bg-warning',
            'category': 'education'
        },
        'todos': {
            'name': 'ToDos',
            'description': 'Verwalten Sie Ihre Aufgaben und Projekte effizient.',
            'icon': 'bi-check-square',
            'url': 'todos:home',
            'color': 'bg-primary',
            'category': 'management'
        },
        'editor': {
            'name': 'Content Editor',
            'description': 'Bearbeiten Sie Inhalte und Seiten Ihrer Website.',
            'icon': 'bi-pencil-square',
            'url': 'accounts:content_editor',
            'color': 'bg-warning',
            'category': 'tools'
        },
        'bug_report': {
            'name': 'Bug Report',
            'description': 'Melden Sie Fehler und Verbesserungsvorschläge.',
            'icon': 'bi-bug',
            'url': 'bug_report:submit_bug_report',
            'color': 'bg-danger',
            'category': 'support'
        },
        'payments': {
            'name': 'Zahlungen & Abos',
            'description': 'Verwalten Sie Ihre Abonnements und Zahlungsinformationen.',
            'icon': 'bi-credit-card',
            'url': 'payments:subscription_plans',
            'color': 'bg-success',
            'category': 'management'
        }
    }
    
    # Filtere Apps basierend auf Berechtigungen (inklusive individuelle Berechtigungen)
    available_apps = []
    for app_name, app_config in app_definitions.items():
        # Prüfe ob App im Frontend angezeigt werden soll (berücksichtigt individuelle Berechtigungen)
        if UserAppPermission.user_can_see_app_in_frontend(app_name, request.user):
            # Prüfe ob App in Entwicklung ist (entweder in AppPermission oder FeatureAccess)
            is_in_development = False
            
            # Prüfe AppPermission
            try:
                app_permission = AppPermission.objects.get(app_name=app_name)
                if app_permission.access_level == 'in_development':
                    is_in_development = True
            except AppPermission.DoesNotExist:
                pass
            
            # Prüfe FeatureAccess Status
            feature_access = None
            try:
                feature_access = FeatureAccess.objects.get(app_name=app_name)
                if feature_access.subscription_required == 'in_development':
                    is_in_development = True
            except FeatureAccess.DoesNotExist:
                pass
            
            available_apps.append({
                'name': app_config['name'],
                'description': app_config['description'],
                'icon': app_config['icon'],
                'url': app_config['url'],
                'color': app_config['color'],
                'category': app_config['category'],
                'app_name': app_name,
                'available': True,
                'is_in_development': is_in_development,
                'feature_access': feature_access
            })
    
    context = {
        'categories': categories,
        'use_custom_categories': request.user.use_custom_categories,
        'enable_ai_keyword_expansion': request.user.enable_ai_keyword_expansion,
        'dark_mode': request.user.dark_mode,
        'available_apps': available_apps,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def toggle_dark_mode(request):
    """Universelle View für Dark Mode Toggle von überall."""
    if request.method == 'POST':
        dark_mode = request.POST.get('dark_mode') == 'on'
        request.user.dark_mode = dark_mode
        request.user.save()
        
        if dark_mode:
            messages.success(request, 'Dunkles Design wurde aktiviert.')
        else:
            messages.info(request, 'Helles Design wurde aktiviert.')
    
    # Redirect zurück zur vorherigen Seite oder Dashboard
    next_url = request.POST.get('next') or request.GET.get('next') or 'accounts:dashboard'
    return redirect(next_url)


@login_required
def toggle_desktop_view(request):
    """Toggle für Desktop-Ansicht (nur für Superuser)."""
    if not request.user.is_superuser:
        messages.error(request, 'Sie haben keine Berechtigung für diese Funktion.')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        desktop_view = request.POST.get('desktop_view') == 'on'
        request.user.desktop_view = desktop_view
        request.user.save()
        
        if desktop_view:
            messages.success(request, 'Desktop-Ansicht wurde aktiviert. Seite wird in voller Desktop-Auflösung angezeigt.')
        else:
            messages.info(request, 'Responsive Ansicht wurde aktiviert. Seite passt sich an Ihr Gerät an.')
    
    # Redirect zurück zur vorherigen Seite oder Dashboard
    next_url = request.POST.get('next') or request.GET.get('next') or 'accounts:dashboard'
    return redirect(next_url)


@login_required
def manage_api_keys(request):
    if request.method == 'POST':
        form = ApiKeyForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'API Keys erfolgreich gespeichert.')
            return redirect('accounts:neue_api_einstellungen')
    else:
        form = ApiKeyForm(instance=request.user)
    
    return render(request, 'accounts/manage_api_keys.html', {
        'form': form
    })


@login_required
def canva_settings_view(request):
    """Verwaltet Canva API-Einstellungen"""
    from naturmacher.models import CanvaAPISettings
    
    canva_settings, created = CanvaAPISettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        canva_settings.client_id = request.POST.get('client_id', '').strip()
        canva_settings.client_secret = request.POST.get('client_secret', '').strip()
        canva_settings.brand_template_id = request.POST.get('brand_template_id', '').strip()
        canva_settings.folder_id = request.POST.get('folder_id', '').strip()
        canva_settings.save()
        
        messages.success(request, 'Canva-Einstellungen wurden erfolgreich gespeichert.')
        return redirect('accounts:neue_api_einstellungen')
    
    # Redirect to the consolidated API settings page for GET requests
    return redirect('accounts:neue_api_einstellungen')


@login_required
def canva_oauth_start(request):
    """Startet den Canva OAuth-Prozess"""
    from naturmacher.canva_service import CanvaAPIService
    
    try:
        canva_service = CanvaAPIService(request.user)
        redirect_uri = request.build_absolute_uri('/accounts/canva-oauth-callback/')
        auth_url = canva_service.get_authorization_url(redirect_uri)
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f'Fehler beim Starten der Canva-Autorisierung: {str(e)}')
        return redirect('accounts:neue_api_einstellungen')


@login_required
def canva_oauth_callback(request):
    """Verarbeitet den Canva OAuth-Callback"""
    from naturmacher.canva_service import CanvaAPIService
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'Canva-Autorisierung fehlgeschlagen: {error}')
        return redirect('accounts:neue_api_einstellungen')
    
    if not code:
        messages.error(request, 'Kein Autorisierungscode von Canva erhalten.')
        return redirect('accounts:neue_api_einstellungen')
    
    # Sicherheitscheck: State validieren
    expected_state = f'user_{request.user.id}'
    if state != expected_state:
        messages.error(request, 'Sicherheitsfehler: Ungültiger State-Parameter.')
        return redirect('accounts:neue_api_einstellungen')
    
    try:
        canva_service = CanvaAPIService(request.user)
        redirect_uri = request.build_absolute_uri('/accounts/canva-oauth-callback/')
        
        if canva_service.exchange_code_for_token(code, redirect_uri):
            messages.success(request, 'Canva-Autorisierung erfolgreich! Sie können jetzt Designs importieren.')
        else:
            messages.error(request, 'Fehler beim Austausch des Autorisierungscodes.')
    
    except Exception as e:
        messages.error(request, f'Fehler bei der Canva-Autorisierung: {str(e)}')
    
    return redirect('accounts:neue_api_einstellungen')


@login_required
def canva_disconnect(request):
    """Trennt die Canva-Verbindung"""
    from naturmacher.models import CanvaAPISettings
    
    if request.method == 'POST':
        try:
            canva_settings = CanvaAPISettings.objects.get(user=request.user)
            canva_settings.access_token = ''
            canva_settings.refresh_token = ''
            canva_settings.token_expires_at = None
            canva_settings.save()
            
            messages.success(request, 'Canva-Verbindung wurde getrennt.')
        except CanvaAPISettings.DoesNotExist:
            pass
    
    return redirect('accounts:neue_api_einstellungen')


@login_required
def category_list(request):
    """Liste aller Kategorien des Benutzers."""
    categories = AmpelCategory.objects.filter(user=request.user)
    return render(request, 'accounts/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    """Neue Kategorie erstellen."""
    if request.method == 'POST':
        form = AmpelCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f'Kategorie "{category.name}" wurde erfolgreich erstellt.')
            return redirect('accounts:category_detail', pk=category.pk)
    else:
        form = AmpelCategoryForm()
    
    return render(request, 'accounts/category_form.html', {'form': form, 'title': 'Neue Kategorie erstellen'})


@login_required
def category_edit(request, pk):
    """Kategorie bearbeiten."""
    category = get_object_or_404(AmpelCategory, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AmpelCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kategorie "{category.name}" wurde erfolgreich aktualisiert.')
            return redirect('accounts:category_detail', pk=category.pk)
    else:
        form = AmpelCategoryForm(instance=category)
    
    return render(request, 'accounts/category_form.html', {
        'form': form, 
        'category': category,
        'title': f'Kategorie "{category.name}" bearbeiten'
    })


@login_required
def category_detail(request, pk):
    """Kategorie-Details mit Suchbegriffen."""
    category = get_object_or_404(AmpelCategory, pk=pk, user=request.user)
    keywords = CategoryKeyword.objects.filter(category=category)
    
    context = {
        'category': category,
        'keywords': keywords,
    }
    return render(request, 'accounts/category_detail.html', context)


@login_required
def category_delete(request, pk):
    """Kategorie löschen."""
    category = get_object_or_404(AmpelCategory, pk=pk, user=request.user)
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Kategorie "{category_name}" wurde gelöscht.')
        return redirect('accounts:category_list')
    
    return render(request, 'accounts/category_confirm_delete.html', {'category': category})


@login_required
def keyword_add(request, category_pk):
    """Einzelnen Suchbegriff hinzufügen."""
    category = get_object_or_404(AmpelCategory, pk=category_pk, user=request.user)
    
    if request.method == 'POST':
        form = CategoryKeywordForm(request.POST)
        if form.is_valid():
            keyword = form.save(commit=False)
            keyword.category = category
            keyword.save()
            messages.success(request, f'Suchbegriff "{keyword.keyword}" wurde hinzugefügt.')
            return redirect('accounts:category_detail', pk=category.pk)
    else:
        form = CategoryKeywordForm()
    
    return render(request, 'accounts/keyword_form.html', {
        'form': form,
        'category': category,
        'title': f'Suchbegriff zu "{category.name}" hinzufügen'
    })


@login_required
def keyword_bulk_add(request, category_pk):
    """Mehrere Suchbegriffe auf einmal hinzufügen."""
    category = get_object_or_404(AmpelCategory, pk=category_pk, user=request.user)
    
    if request.method == 'POST':
        form = KeywordBulkForm(request.POST)
        if form.is_valid():
            keywords_text = form.cleaned_data['keywords']
            
            # Parse keywords (by comma or newline)
            import re
            keywords = re.split(r'[,\n]+', keywords_text)
            keywords = [kw.strip() for kw in keywords if kw.strip()]
            
            added_count = 0
            for keyword_text in keywords:
                keyword, created = CategoryKeyword.objects.get_or_create(
                    category=category,
                    keyword=keyword_text,
                    defaults={'weight': 1}
                )
                if created:
                    added_count += 1
            
            messages.success(request, f'{added_count} neue Suchbegriffe wurden hinzugefügt.')
            return redirect('accounts:category_detail', pk=category.pk)
    else:
        form = KeywordBulkForm()
    
    return render(request, 'accounts/keyword_bulk_form.html', {
        'form': form,
        'category': category,
        'title': f'Mehrere Suchbegriffe zu "{category.name}" hinzufügen'
    })


@login_required
def keyword_delete(request, keyword_pk):
    """Suchbegriff löschen."""
    keyword = get_object_or_404(CategoryKeyword, pk=keyword_pk, category__user=request.user)
    category = keyword.category
    
    if request.method == 'POST':
        keyword_text = keyword.keyword
        keyword.delete()
        messages.success(request, f'Suchbegriff "{keyword_text}" wurde gelöscht.')
        return redirect('accounts:category_detail', pk=category.pk)
    
    return render(request, 'accounts/keyword_confirm_delete.html', {
        'keyword': keyword,
        'category': category
    })


@login_required
def api_settings_view(request):
    """Zeigt die API-Einstellungsseite an"""
    return redirect('accounts:neue_api_einstellungen')


@login_required
def neue_api_einstellungen_view(request):
    """Zeigt die neue API-Einstellungsseite an"""
    user = request.user
    
    if request.method == 'POST':
        # Update API Keys direkt im User Model
        action = request.POST.get('action')
        
        if action == 'update_openai':
            openai_key = request.POST.get('openai_api_key', '').strip()
            if openai_key:
                user.openai_api_key = openai_key
                user.save()
                messages.success(request, 'OpenAI API-Key erfolgreich gespeichert.')
            else:
                messages.error(request, 'Bitte geben Sie einen gültigen OpenAI API-Key ein.')
                
        elif action == 'update_youtube':
            youtube_key = request.POST.get('youtube_api_key', '').strip()
            if youtube_key:
                user.youtube_api_key = youtube_key
                user.save()
                messages.success(request, 'YouTube API-Key erfolgreich gespeichert.')
            else:
                messages.error(request, 'Bitte geben Sie einen gültigen YouTube API-Key ein.')
                
        elif action == 'clear_keys':
            user.openai_api_key = ''
            user.youtube_api_key = ''
            user.save()
            messages.success(request, 'Alle API-Keys wurden gelöscht.')
        
        return redirect('accounts:neue_api_einstellungen')
    
    # Hole Zoho API Settings für den Benutzer
    try:
        zoho_settings = ZohoAPISettings.objects.get(user=user)
    except ZohoAPISettings.DoesNotExist:
        zoho_settings = None
    
    # Hole Shopify Stores für den Benutzer
    try:
        from shopify_manager.models import ShopifyStore
        shopify_stores = ShopifyStore.objects.filter(user=user)
    except:
        shopify_stores = []
    
    # Erstelle maskierte Versionen der API-Keys für die Anzeige
    context = {
        'user': user,
        'openai_key_masked': '••••••••' + user.openai_api_key[-4:] if user.openai_api_key and len(user.openai_api_key) > 4 else '',
        'youtube_key_masked': '••••••••' + user.youtube_api_key[-4:] if user.youtube_api_key and len(user.youtube_api_key) > 4 else '',
        'openai_configured': bool(user.openai_api_key),
        'youtube_configured': bool(user.youtube_api_key),
        'zoho_configured': bool(zoho_settings and zoho_settings.is_configured),
        'shopify_configured': len(shopify_stores) > 0,
        'zoho_settings': zoho_settings,
        'shopify_stores': shopify_stores,
    }
    
    return render(request, 'accounts/api_einstellungen.html', context)


@login_required
def company_info_view(request):
    """Verwaltet die Firmeninformationen und das Profil des Benutzers"""
    # Bestimme den aktiven Tab
    active_tab = request.GET.get('tab', 'company')
    
    # Prüfe ob User Super User ist für Bug-Chat-Tab
    is_superuser = request.user.is_superuser
    
    # Prüfe ob User App-Freigaben verwalten darf
    can_manage_apps = request.user.is_superuser or request.user.can_manage_app_permissions
    
    if request.method == 'POST':
        # Prüfe welches Formular gesendet wurde
        if 'company_form' in request.POST:
            # Firmeninfo-Formular
            company_form = CompanyInfoForm(request.POST, instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            
            if company_form.is_valid():
                company_form.save()
                messages.success(request, 'Firmeninformationen wurden erfolgreich gespeichert.')
                return redirect_with_params('accounts:company_info', tab='company')
            active_tab = 'company'
            
        elif 'profile_form' in request.POST:
            # Profil-Formular
            company_form = CompanyInfoForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            
            # Prüfe ob Profilbild gelöscht werden soll
            if request.POST.get('delete_profile_picture') == 'true':
                if request.user.profile_picture:
                    import os
                    try:
                        os.remove(request.user.profile_picture.path)
                    except OSError:
                        pass
                    request.user.profile_picture = None
                    request.user.save()
                    messages.success(request, 'Ihr Profilbild wurde erfolgreich gelöscht!')
                else:
                    messages.info(request, 'Kein Profilbild vorhanden.')
                return redirect('accounts:company_info')
            
            # Normale Profilaktualisierung
            profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Ihr Profil wurde erfolgreich aktualisiert!')
                return redirect('accounts:company_info')
            active_tab = 'profile'
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            app_permission_form = AppPermissionForm() if can_manage_apps else None
            
        elif 'password_form' in request.POST:
            # Passwort-Formular
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            app_permission_form = AppPermissionForm() if can_manage_apps else None
            
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Ihr Passwort wurde erfolgreich geändert!')
                return redirect('accounts:company_info')
            active_tab = 'password'
            
        elif 'bug_chat_form' in request.POST:
            # Bug-Chat-Einstellungen
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(request.POST, instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            
            if bug_chat_form.is_valid():
                bug_chat_form.save()
                messages.success(request, 'Bug-Chat-Einstellungen wurden erfolgreich gespeichert!')
                return redirect('accounts:company_info')
            active_tab = 'bug_chat'
            
        elif 'superuser_form' in request.POST and is_superuser:
            # Super User Verwaltung
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(request.POST, current_user=request.user)
            
            if superuser_form.is_valid():
                # Verarbeite Super User Änderungen
                updated_count = 0
                for field_name, value in superuser_form.cleaned_data.items():
                    if field_name.startswith('user_'):
                        parts = field_name.split('_')
                        user_id = int(parts[1])
                        setting_type = '_'.join(parts[2:])
                        
                        try:
                            user = CustomUser.objects.get(id=user_id)
                            if setting_type == 'superuser':
                                user.is_bug_chat_superuser = value
                            elif setting_type == 'receive_reports':
                                user.receive_bug_reports = value
                            elif setting_type == 'receive_anonymous':
                                user.receive_anonymous_reports = value
                            
                            user.save()
                            updated_count += 1
                        except CustomUser.DoesNotExist:
                            continue
                
                messages.success(request, f'Super User Einstellungen wurden für {updated_count} Benutzer aktualisiert!')
                return redirect('accounts:company_info')
            active_tab = 'bug_chat'
            
        elif 'app_permission_form' in request.POST and can_manage_apps:
            # App-Freigabe-Einstellungen
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            app_permission_form = AppPermissionForm() if can_manage_apps else None
            app_permission_form = AppPermissionForm(request.POST)
            
            if app_permission_form.is_valid():
                app_permission_form.save()
                messages.success(request, 'App-Freigabe-Einstellungen wurden erfolgreich gespeichert!')
                return redirect_with_params('accounts:company_info', tab='app_permissions')
            active_tab = 'app_permissions'
            
        elif 'feature_access_form' in request.POST and is_superuser:
            # Feature-Access-Verwaltung
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            app_permission_form = AppPermissionForm() if can_manage_apps else None
            
            # Handle different feature access actions
            if 'add_feature' in request.POST:
                # Neues Feature hinzufügen
                feature_form = FeatureAccessForm(request.POST)
                if feature_form.is_valid():
                    feature_form.save()
                    messages.success(request, f'Feature-Zugriff für {feature_form.cleaned_data["app_name"]} wurde erfolgreich erstellt!')
                    return redirect_with_params('accounts:company_info', tab='feature_access')
            elif 'bulk_action' in request.POST:
                # Bulk-Aktion ausführen
                bulk_form = BulkFeatureAccessForm(request.POST)
                if bulk_form.is_valid():
                    action = bulk_form.cleaned_data['action']
                    selected_features = bulk_form.cleaned_data['selected_features']
                    
                    if action and selected_features:
                        count = 0
                        for feature in selected_features:
                            if action == 'activate':
                                feature.is_active = True
                            elif action == 'deactivate':
                                feature.is_active = False
                            elif action == 'set_free':
                                feature.subscription_required = 'free'
                            elif action == 'set_founder_access':
                                feature.subscription_required = 'founder_access'
                            elif action == 'set_any_paid':
                                feature.subscription_required = 'any_paid'
                            elif action == 'set_storage_plan':
                                feature.subscription_required = 'storage_plan'
                            elif action == 'set_blocked':
                                feature.subscription_required = 'blocked'
                            
                            feature.save()
                            count += 1
                        
                        messages.success(request, f'{count} Feature(s) wurden erfolgreich bearbeitet!')
                        return redirect_with_params('accounts:company_info', tab='feature_access')
            else:
                # Einzelnes Feature bearbeiten
                feature_id = request.POST.get('feature_id')
                if feature_id:
                    try:
                        feature = FeatureAccess.objects.get(id=feature_id)
                        feature_form = FeatureAccessForm(request.POST, instance=feature)
                        if feature_form.is_valid():
                            feature_form.save()
                            messages.success(request, f'Feature-Zugriff für {feature.get_app_name_display()} wurde erfolgreich aktualisiert!')
                            return redirect_with_params('accounts:company_info', tab='feature_access')
                    except FeatureAccess.DoesNotExist:
                        messages.error(request, 'Feature nicht gefunden!')
            
            active_tab = 'feature_access'
            
        else:
            # Fallback: Alle Formulare initialisieren
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            app_permission_form = AppPermissionForm() if can_manage_apps else None
            
    else:
        # GET-Request: Alle Formulare mit aktuellen Daten initialisieren
        company_form = CompanyInfoForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(request.user)
        bug_chat_form = BugChatSettingsForm(instance=request.user)
        superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
        app_permission_form = AppPermissionForm() if can_manage_apps else None
    
    # Feature Access Daten für Superuser
    feature_access_data = {}
    if is_superuser:
        # Filter-Parameter aus Request extrahieren
        filter_form = FeatureAccessFilterForm(request.GET)
        features_queryset = FeatureAccess.objects.all()
        
        if filter_form.is_valid():
            if filter_form.cleaned_data['subscription_required']:
                features_queryset = features_queryset.filter(
                    subscription_required=filter_form.cleaned_data['subscription_required']
                )
            if filter_form.cleaned_data['is_active']:
                is_active = filter_form.cleaned_data['is_active'] == 'active'
                features_queryset = features_queryset.filter(is_active=is_active)
            if filter_form.cleaned_data['search']:
                search_term = filter_form.cleaned_data['search']
                features_queryset = features_queryset.filter(
                    models.Q(app_name__icontains=search_term) |
                    models.Q(description__icontains=search_term)
                )
        
        # Sortierung: Hauptapps zuerst, dann Sub-Features
        main_apps = ['core', 'chat', 'videos', 'shopify_manager', 'image_editor', 'naturmacher', 
                     'organization', 'todos', 'pdf_sucher', 'amortization_calculator', 
                     'sportplatzApp', 'bug_report', 'payments']
        
        # Custom Sortierung: Hauptapps zuerst, dann Features
        features_list = list(features_queryset)
        features_list.sort(key=lambda x: (
            0 if x.app_name in main_apps else 1,  # Hauptapps zuerst
            main_apps.index(x.app_name) if x.app_name in main_apps else 999,  # Reihenfolge der Hauptapps
            x.get_app_name_display()  # Alphabetisch für Sub-Features
        ))
        
        features_queryset = features_list
        
        # Statistiken berechnen
        total_features = FeatureAccess.objects.count()
        free_features = FeatureAccess.objects.filter(subscription_required='free').count()
        founder_features = FeatureAccess.objects.filter(subscription_required='founder_access').count()
        paid_features = FeatureAccess.objects.filter(subscription_required='any_paid').count()
        storage_features = FeatureAccess.objects.filter(subscription_required='storage_plan').count()
        development_features = FeatureAccess.objects.filter(subscription_required='in_development').count()
        blocked_features = FeatureAccess.objects.filter(subscription_required='blocked').count()
        
        feature_access_data = {
            'features': features_queryset,
            'filter_form': filter_form,
            'bulk_form': BulkFeatureAccessForm(),
            'new_feature_form': FeatureAccessForm(),
            'stats': {
                'total': total_features,
                'free': free_features,
                'founder_access': founder_features,
                'any_paid': paid_features,
                'storage_plan': storage_features,
                'in_development': development_features,
                'blocked': blocked_features,
            }
        }
    
    # Video-App Abo-Daten für Template
    video_storage, created = VideoUserStorage.objects.get_or_create(user=request.user)
    video_usage_percentage = (video_storage.used_storage / video_storage.max_storage * 100) if video_storage.max_storage > 0 else 0
    
    # Lade alle Nutzer für die individuellen App-Berechtigungen (nur für Superuser)
    users = None
    if is_superuser:
        users = CustomUser.objects.all().order_by('username')
    
    return render(request, 'accounts/company_info.html', {
        'company_form': company_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'bug_chat_form': bug_chat_form,
        'superuser_form': superuser_form,
        'app_permission_form': app_permission_form if can_manage_apps else None,
        'active_tab': active_tab,
        'is_superuser': is_superuser,
        'can_manage_apps': can_manage_apps,
        'user': request.user,
        'users': users,
        'video_storage': video_storage,
        'video_usage_percentage': video_usage_percentage,
        'feature_access_data': feature_access_data,
    })


@login_required
def test_app_permissions_view(request):
    """Test-Seite für App-Berechtigungen"""
    return render(request, 'accounts/test_app_permissions.html')


@login_required
def get_all_users_api(request):
    """API Endpoint um alle aktiven Nutzer zu holen"""
    if not request.user.is_superuser and not request.user.can_manage_app_permissions:
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    
    users = CustomUser.objects.filter(is_active=True).values('id', 'username', 'email', 'first_name', 'last_name')
    users_list = []
    
    for user in users:
        display_name = user['username']
        if user['first_name'] and user['last_name']:
            display_name = f"{user['first_name']} {user['last_name']} ({user['username']})"
        elif user['first_name']:
            display_name = f"{user['first_name']} ({user['username']})"
        
        users_list.append({
            'id': str(user['id']),
            'username': user['username'],
            'display_name': display_name,
            'email': user['email'] or ''
        })
    
    return JsonResponse({'users': users_list})


def logout_view(request):
    """Benutzer ausloggen."""
    logout(request)
    messages.info(request, 'Sie wurden erfolgreich abgemeldet.')
    return redirect('accounts:login')


class CustomPasswordResetView(PasswordResetView):
    """Passwort zurücksetzen Ansicht"""
    form_class = CustomPasswordResetForm
    template_name = 'accounts/password_reset.html'
    success_url = reverse_lazy('accounts:password_reset_done')
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    
    def form_valid(self, form):
        messages.success(self.request, 
            'Falls ein Konto mit dieser E-Mail-Adresse existiert, haben wir Ihnen '
            'eine E-Mail mit Anweisungen zum Zurücksetzen des Passworts gesendet.')
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """Passwort zurücksetzen - E-Mail gesendet Ansicht"""
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Passwort zurücksetzen bestätigen Ansicht"""
    form_class = CustomSetPasswordForm
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, 'Ihr Passwort wurde erfolgreich geändert!')
        return super().form_valid(form)


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """Passwort zurücksetzen abgeschlossen Ansicht"""
    template_name = 'accounts/password_reset_complete.html'


@login_required
@require_http_methods(["POST"])
def validate_api_key(request):
    """AJAX-View zum Validieren eines API-Schlüssels"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    provider = request.POST.get('provider')
    api_key = request.POST.get('api_key', '').strip()
    
    if not provider or not api_key:
        return JsonResponse({'success': False, 'error': 'Provider und API-Key sind erforderlich'})

    # Validiere API-Key je nach Provider
    is_valid, error_message = test_api_key(provider, api_key)
    
    return JsonResponse({
        'success': True,
        'is_valid': is_valid,
        'provider': provider,
        'error_message': error_message
    })


def test_api_key(provider, api_key):
    """
    Testet einen API-Schlüssel durch einen einfachen API-Aufruf
    
    Args:
        provider: str - 'openai', 'anthropic', 'google', oder 'youtube'
        api_key: str - Der zu testende API-Schlüssel
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    try:
        if provider == 'openai':
            return test_openai_key(api_key)
        elif provider == 'anthropic':
            return test_anthropic_key(api_key)
        elif provider == 'google':
            return test_google_key(api_key)
        elif provider == 'youtube':
            return test_youtube_key(api_key)
        else:
            return False, f"Unbekannter Provider: {provider}"
    except Exception as e:
        return False, f"Validierungsfehler: {str(e)}"


def test_openai_key(api_key):
    """Testet OpenAI API-Schlüssel"""
    try:
        import requests
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Test mit einem einfachen Modelle-Aufruf
        response = requests.get(
            'https://api.openai.com/v1/models',
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and isinstance(data['data'], list):
                return True, "API-Schlüssel ist gültig"
            else:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 401:
            return False, "Ungültiger API-Schlüssel oder Authentifizierungsfehler"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        elif response.status_code == 403:
            # Oft bedeutet das, dass der Key gültig ist, aber keine Berechtigung für Models-Endpoint hat
            # Probiere einen einfachen Chat-Completion Test
            return test_openai_chat_completion(api_key)
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                if "exceeded your current quota" in error_msg.lower() or "quota_exceeded" in error_msg.lower():
                    return True, "API-Schlüssel gültig (Quota überschritten)"
                else:
                    return False, f"API-Fehler: {error_msg}"
            except:
                return False, f"API-Fehler: HTTP {response.status_code}"
                
    except Exception as e:
        error_msg = str(e)
        if "connection error" in error_msg.lower() or "network error" in error_msg.lower():
            return False, "Verbindungsfehler zur OpenAI API"
        else:
            return False, f"Verbindungsfehler: {error_msg}"


def test_openai_chat_completion(api_key):
    """Fallback-Test für OpenAI API-Schlüssel mit Chat Completion"""
    try:
        import requests
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': 'Hi'}],
            'max_tokens': 5
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "API-Schlüssel ist gültig"
        elif response.status_code == 401:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                if "exceeded your current quota" in error_msg.lower() or "quota_exceeded" in error_msg.lower():
                    return True, "API-Schlüssel gültig (Quota überschritten)"
                else:
                    return False, f"Chat API-Fehler: {error_msg}"
            except:
                return False, f"Chat API-Fehler: HTTP {response.status_code}"
                
    except Exception as e:
        return False, f"Chat API Verbindungsfehler: {str(e)}"


def test_anthropic_key(api_key):
    """Testet Anthropic API-Schlüssel"""
    try:
        import requests
        
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        # Test mit einer minimalen Nachricht an die neueste Claude-Version
        data = {
            'model': 'claude-3-5-haiku-20241022',
            'max_tokens': 5,
            'messages': [
                {'role': 'user', 'content': 'Hi'}
            ]
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "API-Schlüssel ist gültig"
        elif response.status_code == 400:
            # Prüfe auf spezifische Fehlermeldungen
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '')
                if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower():
                    return False, "Ungültiger API-Schlüssel"
                elif 'model' in error_msg.lower():
                    # Falls das Modell nicht verfügbar ist, probiere ein älteres
                    data['model'] = 'claude-3-haiku-20240307'
                    response2 = requests.post(
                        'https://api.anthropic.com/v1/messages',
                        headers=headers,
                        json=data,
                        timeout=15
                    )
                    if response2.status_code == 200:
                        return True, "API-Schlüssel ist gültig"
                    elif response2.status_code == 401:
                        return False, "Ungültiger API-Schlüssel"
                    else:
                        return False, f"API-Fehler: {error_msg}"
                else:
                    return False, f"API-Fehler: {error_msg}"
            except:
                return False, f"API-Fehler: HTTP {response.status_code}"
        elif response.status_code == 401:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        elif response.status_code == 403:
            return False, "API-Schlüssel ohne Berechtigung"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                return False, f"API-Fehler: {error_msg}"
            except:
                return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


def test_google_key(api_key):
    """Testet Google AI API-Schlüssel"""
    try:
        import requests
        
        # Test mit Gemini-API - verwende Content Generation API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Minimaler Test-Request
        data = {
            'contents': [{
                'parts': [{
                    'text': 'Hi'
                }]
            }],
            'generationConfig': {
                'maxOutputTokens': 5
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    return True, "API-Schlüssel ist gültig"
                else:
                    return False, "Ungültige API-Antwort"
            except:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 400:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '')
                if 'API_KEY_INVALID' in error_msg or 'invalid api key' in error_msg.lower():
                    return False, "Ungültiger API-Schlüssel"
                else:
                    # Fallback: Teste mit Models-Endpoint
                    models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                    models_response = requests.get(models_url, timeout=10)
                    
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        if 'models' in models_data and len(models_data['models']) > 0:
                            return True, "API-Schlüssel ist gültig"
                        else:
                            return False, "Ungültige API-Antwort"
                    elif models_response.status_code == 400:
                        return False, "Ungültiger API-Schlüssel"
                    elif models_response.status_code == 403:
                        return False, "API-Schlüssel ohne Berechtigung"
                    else:
                        return False, f"API-Fehler: {error_msg}"
            except:
                return False, f"API-Fehler: HTTP {response.status_code}"
        elif response.status_code == 403:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Keine Berechtigung')
                if 'API_KEY_INVALID' in error_msg:
                    return False, "Ungültiger API-Schlüssel"
                else:
                    return False, f"API-Schlüssel ohne Berechtigung: {error_msg}"
            except:
                return False, "API-Schlüssel ohne Berechtigung"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                return False, f"API-Fehler: {error_msg}"
            except:
                return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


def test_youtube_key(api_key):
    """Testet YouTube Data API-Schlüssel"""
    try:
        import requests
        
        # Test mit YouTube API
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=1&q=test&key={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data:
                return True, "API-Schlüssel ist gültig"
            else:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 400:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 403:
            return False, "API-Schlüssel gesperrt oder ohne Berechtigung"
        else:
            return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


@login_required
@require_http_methods(["GET"])
def get_api_balances(request):
    """Lädt die aktuellen API-Kontostände für den Benutzer"""
    user_balances = APIBalance.objects.filter(user=request.user)
    balances_data = {}
    
    # Initialize with default structure for all providers
    all_providers = [
        'openai', 'anthropic', 'google', 'youtube'
    ]
    
    for provider_key in all_providers:
        masked_api_key = 'Nicht konfiguriert'
        api_key = None
        
        # Get API key from user profile
        if provider_key == 'openai' and request.user.openai_api_key:
            api_key = request.user.openai_api_key
        elif provider_key == 'anthropic' and request.user.anthropic_api_key:
            api_key = request.user.anthropic_api_key
        elif provider_key == 'google' and request.user.google_api_key:
            api_key = request.user.google_api_key
        elif provider_key == 'youtube' and request.user.youtube_api_key:
            api_key = request.user.youtube_api_key
        
        # Mask the API key if it exists
        if api_key and len(api_key.strip()) > 0:
            api_key = api_key.strip()
            if len(api_key) <= 8:
                masked_api_key = "*" * len(api_key)
            else:
                masked_api_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]

        balances_data[provider_key] = {
            'balance': 0.00,
            'threshold': 5.00, # Default threshold
            'currency': 'USD',
            'masked_api_key': masked_api_key
        }

    for balance_obj in user_balances:
        provider = balance_obj.provider
        balances_data[provider]['balance'] = float(balance_obj.balance)
        balances_data[provider]['threshold'] = float(balance_obj.auto_warning_threshold)
        balances_data[provider]['currency'] = balance_obj.currency
        # Special handling for YouTube quota
        if provider == 'youtube':
            balances_data[provider]['balance'] = int(balance_obj.balance) # Quota is integer
            balances_data[provider]['threshold'] = int(balance_obj.auto_warning_threshold) # Quota threshold is integer
            balances_data[provider]['currency'] = 'QUOTA'
    
    return JsonResponse({
        'success': True,
        'balances': balances_data
    })


@login_required
@require_http_methods(["POST"])
def update_api_balance(request):
    """Aktualisiert einen API-Kontostand"""
    provider = request.POST.get('provider')
    api_key = request.POST.get('api_key', '').strip()
    balance_str = request.POST.get('balance')
    threshold_str = request.POST.get('threshold')
    currency = request.POST.get('currency', 'USD')
    
    if not provider:
        return JsonResponse({'success': False, 'error': 'Provider ist erforderlich'})
    
    try:
        balance = float(balance_str) if balance_str else 0.00
        threshold = float(threshold_str) if threshold_str else 5.00
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Ungültiger Wert für Kontostand oder Warnschwelle'})

    api_balance, created = APIBalance.objects.get_or_create(
        user=request.user,
        provider=provider,
        defaults={
            'balance': balance,
            'currency': currency,
            'auto_warning_threshold': threshold
        }
    )

    if not created:
        api_balance.balance = balance
        api_balance.currency = currency
        api_balance.auto_warning_threshold = threshold
        api_balance.save()
    
    # Save API key to user profile if provided
    if api_key:
        if provider == 'openai':
            request.user.openai_api_key = api_key
        elif provider == 'anthropic':
            request.user.anthropic_api_key = api_key
        elif provider == 'google':
            request.user.google_api_key = api_key
        elif provider == 'youtube':
            request.user.youtube_api_key = api_key
        request.user.save()
    
    masked_key = api_balance.get_masked_api_key()
    
    return JsonResponse({
        'success': True,
        'message': f'Kontostand für {provider} wurde aktualisiert',
        'masked_api_key': masked_key
    })


@login_required
@require_http_methods(["POST"])
def remove_api_key(request):
    """Entfernt einen API-Schlüssel"""
    provider = request.POST.get('provider')
    
    if not provider:
        return JsonResponse({'success': False, 'error': 'Provider ist erforderlich'})
    
    try:
        if provider == 'openai':
            request.user.openai_api_key = None
        elif provider == 'anthropic':
            request.user.anthropic_api_key = None
        elif provider == 'google':
            request.user.google_api_key = None
        elif provider == 'youtube':
            request.user.youtube_api_key = None
        else:
            return JsonResponse({'success': False, 'error': f'Entfernen des API-Schlüssels für {provider} nicht unterstützt'})
        request.user.save()
        return JsonResponse({
            'success': True,
            'message': f'API-Schlüssel für {provider} wurde entfernt'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Fehler beim Entfernen des API-Schlüssels: {str(e)}'})


@login_required
@require_http_methods(["GET"])
def get_usage_stats(request):
    """Lädt die Nutzungsstatistiken für den Benutzer"""
    try:
        # TODO: Lade echte Statistiken aus der Datenbank
        # Für jetzt geben wir Mock-Daten zurück
        mock_stats = {
            'success': True,
            'period': 'Letzten 30 Tage',
            'total_cost': 12.45,
            'stats': {
                'openai': {
                    'name': 'OpenAI (ChatGPT)',
                    'request_count': 150,
                    'total_cost': 8.20,
                    'total_tokens': 45000,
                    'last_used': '2025-01-02T10:30:00Z'
                },
                'anthropic': {
                    'name': 'Anthropic (Claude)',
                    'request_count': 75,
                    'total_cost': 3.50,
                    'total_tokens': 20000,
                    'last_used': '2025-01-01T15:20:00Z'
                },
                'google': {
                    'name': 'Google (Gemini)',
                    'request_count': 25,
                    'total_cost': 0.75,
                    'total_tokens': 8000,
                    'last_used': '2024-12-30T09:15:00Z'
                },
                'youtube': {
                    'name': 'YouTube Data API',
                    'request_count': 10,
                    'total_cost': 0.00,
                    'total_tokens': 0,
                    'last_used': None
                }
            }
        }
        
        return JsonResponse(mock_stats)
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Fehler beim Laden der Statistiken: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def add_shopify_store(request):
    """Fügt einen neuen Shopify Store hinzu"""
    try:
        from shopify_manager.models import ShopifyStore
        
        name = request.POST.get('name', '').strip()
        shop_domain = request.POST.get('shop_domain', '').strip()
        access_token = request.POST.get('access_token', '').strip()
        custom_domain = request.POST.get('custom_domain', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name or not shop_domain or not access_token:
            return JsonResponse({
                'success': False,
                'error': 'Name, Shop Domain und Access Token sind erforderlich'
            })
        
        # Shopify Domain normalisieren
        if not shop_domain.endswith('.myshopify.com'):
            if '.' not in shop_domain:
                shop_domain = f"{shop_domain}.myshopify.com"
        
        # Prüfen ob Store bereits existiert
        if ShopifyStore.objects.filter(user=request.user, shop_domain=shop_domain).exists():
            return JsonResponse({
                'success': False,
                'error': 'Ein Store mit dieser Domain existiert bereits'
            })
        
        # Store erstellen
        store = ShopifyStore.objects.create(
            user=request.user,
            name=name,
            shop_domain=shop_domain,
            access_token=access_token,
            custom_domain=custom_domain,
            description=description
        )
        
        # Verbindung testen
        from shopify_manager.shopify_api import ShopifyAPIClient
        client = ShopifyAPIClient(store)
        is_valid, message = client.test_connection()
        
        if not is_valid:
            store.delete()
            return JsonResponse({
                'success': False,
                'error': f'Verbindungstest fehlgeschlagen: {message}'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Store "{name}" erfolgreich hinzugefügt',
            'store_id': store.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Hinzufügen des Stores: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def test_shopify_connection(request):
    """Testet die Shopify API-Verbindung"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        from shopify_manager.shopify_api import ShopifyAPIClient
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        
        if not store_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID ist erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        client = ShopifyAPIClient(store)
        is_valid, message = client.test_connection()
        
        return JsonResponse({
            'success': is_valid,
            'message' if is_valid else 'error': message
        })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Testen der Verbindung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def delete_shopify_store(request):
    """Löscht einen Shopify Store"""
    try:
        import json
        from shopify_manager.models import ShopifyStore
        
        data = json.loads(request.body)
        store_id = data.get('store_id')
        
        if not store_id:
            return JsonResponse({
                'success': False,
                'error': 'Store ID ist erforderlich'
            })
        
        store = ShopifyStore.objects.get(id=store_id, user=request.user)
        store_name = store.name
        store.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Store "{store_name}" erfolgreich entfernt'
        })
        
    except ShopifyStore.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen des Stores: {str(e)}'
        })


@login_required
def user_permissions(request):
    """
    View für Nutzerverwaltung und Call-Berechtigungen (nur für Superuser)
    """
    if not request.user.is_superuser:
        messages.error(request, 'Sie haben keine Berechtigung für diese Seite.')
        return redirect('accounts:dashboard')
    
    users = CustomUser.objects.all().order_by('username')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        
        try:
            user = CustomUser.objects.get(id=user_id)
            
            if action == 'toggle_audio_calls':
                user.can_make_audio_calls = not user.can_make_audio_calls
                user.save()
                status = "aktiviert" if user.can_make_audio_calls else "deaktiviert"
                messages.success(request, f'Audioanrufe tätigen für {user.username} {status}.')
                
            elif action == 'toggle_video_calls':
                user.can_make_video_calls = not user.can_make_video_calls
                user.save()
                status = "aktiviert" if user.can_make_video_calls else "deaktiviert"
                messages.success(request, f'Videoanrufe tätigen für {user.username} {status}.')
                
            elif action == 'toggle_audio_receive':
                user.can_receive_audio_calls = not user.can_receive_audio_calls
                user.save()
                status = "aktiviert" if user.can_receive_audio_calls else "deaktiviert"
                messages.success(request, f'Audioanrufe empfangen für {user.username} {status}.')
                
            elif action == 'toggle_video_receive':
                user.can_receive_video_calls = not user.can_receive_video_calls
                user.save()
                status = "aktiviert" if user.can_receive_video_calls else "deaktiviert"
                messages.success(request, f'Videoanrufe empfangen für {user.username} {status}.')
                
            elif action == 'toggle_superuser':
                # Verhindere, dass sich der User selbst den Superuser-Status entziehen kann
                if user.id == request.user.id:
                    messages.error(request, 'Sie können sich selbst nicht den Superuser-Status entziehen.')
                else:
                    user.is_superuser = not user.is_superuser
                    user.is_staff = user.is_superuser  # Staff-Status sollte mit Superuser-Status übereinstimmen
                    user.save()
                    status = "aktiviert" if user.is_superuser else "deaktiviert"
                    messages.success(request, f'Superuser-Status für {user.username} {status}.')
            
            elif action == 'set_password':
                new_password = request.POST.get('new_password')
                if new_password:
                    user.set_password(new_password)
                    user.save()
                    messages.success(request, f'Passwort für {user.username} wurde erfolgreich geändert.')
                else:
                    messages.error(request, 'Bitte geben Sie ein neues Passwort ein.')
                
        except CustomUser.DoesNotExist:
            messages.error(request, 'Benutzer nicht gefunden.')
        except Exception as e:
            messages.error(request, f'Fehler beim Aktualisieren der Berechtigungen: {str(e)}')
        
        return redirect('accounts:user_permissions')
    
    context = {
        'users': users,
    }
    return render(request, 'accounts/user_permissions.html', context)


@login_required
def get_individual_permissions(request, user_id):
    """
    API View to get individual app permissions for a specific user
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'}, status=403)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        permissions_data = []
        for app_choice in AppPermission.APP_CHOICES:
            app_name = app_choice[0]
            app_display_name = app_choice[1]
            
            # Get global permission
            try:
                global_permission = AppPermission.objects.get(app_name=app_name)
                global_access = global_permission.access_level
            except AppPermission.DoesNotExist:
                global_access = 'blocked'
            
            # Get individual permission
            try:
                individual_permission = UserAppPermission.objects.get(
                    user=user, app_name=app_name, is_active=True
                )
                individual_override = individual_permission.override_type
            except UserAppPermission.DoesNotExist:
                individual_override = None
            
            permissions_data.append({
                'app_name': app_name,
                'app_display_name': app_display_name,
                'global_access': global_access,
                'individual_permission': individual_override
            })
        
        return JsonResponse({
            'success': True,
            'permissions': permissions_data
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Benutzer nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def save_individual_permissions(request):
    """
    API View to save individual app permissions for a user
    """
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Keine Berechtigung'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST erlaubt'}, status=405)
    
    try:
        user_id = request.POST.get('user_id')
        permissions_json = request.POST.get('permissions')
        
        if not user_id or not permissions_json:
            return JsonResponse({'success': False, 'error': 'Fehlende Parameter'}, status=400)
        
        user = CustomUser.objects.get(id=user_id)
        permissions = json.loads(permissions_json)
        
        for app_name, permission_type in permissions.items():
            if permission_type == 'remove':
                # Remove individual permission (fall back to global)
                UserAppPermission.objects.filter(
                    user=user, app_name=app_name
                ).delete()
            else:
                # Create or update individual permission
                permission, created = UserAppPermission.objects.update_or_create(
                    user=user,
                    app_name=app_name,
                    defaults={
                        'override_type': permission_type,
                        'is_active': True,
                        'created_by': request.user
                    }
                )
        
        return JsonResponse({'success': True})
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Benutzer nicht gefunden'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def user_online_times(request, user_id):
    """
    Zeigt die Onlinezeiten eines Benutzers grafisch an (nur für Superuser)
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        # Letzte 30 Tage Login-Historie
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        login_history = UserLoginHistory.objects.filter(
            user=user,
            login_time__gte=thirty_days_ago
        ).order_by('-login_time')
        
        # Daten für Chart.js vorbereiten
        chart_data = []
        daily_stats = {}
        
        for login in login_history:
            date_str = login.login_time.strftime('%Y-%m-%d')
            if date_str not in daily_stats:
                daily_stats[date_str] = {
                    'date': date_str,
                    'sessions': 0,
                    'total_duration': 0,
                    'first_login': login.login_time,
                    'last_logout': login.logout_time if login.logout_time else timezone.now()
                }
            
            daily_stats[date_str]['sessions'] += 1
            if login.session_duration:
                daily_stats[date_str]['total_duration'] += login.session_duration.total_seconds()
        
        # Daten für die letzten 30 Tage generieren (auch Tage ohne Login)
        for i in range(30):
            date = timezone.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            if date_str in daily_stats:
                chart_data.append({
                    'date': date_str,
                    'sessions': daily_stats[date_str]['sessions'],
                    'duration_hours': daily_stats[date_str]['total_duration'] / 3600,
                    'formatted_duration': f"{int(daily_stats[date_str]['total_duration'] / 3600):02d}:{int((daily_stats[date_str]['total_duration'] % 3600) / 60):02d}"
                })
            else:
                chart_data.append({
                    'date': date_str,
                    'sessions': 0,
                    'duration_hours': 0,
                    'formatted_duration': "00:00"
                })
        
        chart_data.reverse()  # Chronologische Reihenfolge
        
        # Detaillierte Session-Daten
        sessions_data = []
        for login in login_history[:20]:  # Letzte 20 Sessions
            sessions_data.append({
                'login_time': login.login_time.strftime('%d.%m.%Y %H:%M:%S'),
                'logout_time': login.logout_time.strftime('%d.%m.%Y %H:%M:%S') if login.logout_time else 'Läuft noch',
                'duration': login.get_duration_display(),
                'ip_address': login.ip_address,
                'is_active': login.is_active_session
            })
        
        return JsonResponse({
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'is_online': user.is_currently_online()
            },
            'chart_data': chart_data,
            'sessions_data': sessions_data,
            'summary': {
                'total_sessions': login_history.count(),
                'days_with_activity': len(daily_stats),
                'avg_sessions_per_day': len(daily_stats) and login_history.count() / len(daily_stats) or 0
            }
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Benutzer nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def user_app_usage_statistics(request, user_id):
    """
    API Endpoint für detaillierte App-Nutzungsstatistiken eines Benutzers (nur für Superuser)
    """
    print(f"DEBUG: user_app_usage_statistics called with user_id={user_id}, user={request.user}")
    
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        days = int(request.GET.get('days', 30))
        
        # Hole App-Nutzungsstatistiken
        statistics = AppUsageTracking.get_user_app_statistics(user, days=days)
        
        # Formatiere Daten für Chart.js
        chart_data = []
        for day_stat in statistics['daily_stats']:
            chart_data.append({
                'date': day_stat['day'],
                'sessions': day_stat['sessions'],
                'duration_hours': round((day_stat['duration'] or 0) / 3600, 2),
                'video_calls': day_stat['video_calls'] or 0,
                'audio_calls': day_stat['audio_calls'] or 0,
                'video_call_hours': round((day_stat['video_call_duration'] or 0) / 3600, 2),
                'audio_call_hours': round((day_stat['audio_call_duration'] or 0) / 3600, 2),
            })
        
        # App-spezifische Daten formatieren
        app_data = []
        for app_stat in statistics['app_stats']:
            app_tracking = AppUsageTracking()
            app_tracking.app_name = app_stat['app_name']
            
            app_data.append({
                'app_name': app_stat['app_name'],
                'app_display_name': app_tracking.get_app_display_name(),
                'total_sessions': app_stat['total_sessions'],
                'total_duration_hours': round((app_stat['total_duration'] or 0) / 3600, 2),
                'avg_duration_minutes': round((app_stat['avg_duration'] or 0) / 60, 1),
                'last_used': app_stat['last_used'].isoformat() if app_stat['last_used'] else None,
                'video_calls': app_stat['video_calls'] or 0,
                'audio_calls': app_stat['audio_calls'] or 0,
                'video_call_hours': round((app_stat['video_call_duration'] or 0) / 3600, 2),
                'audio_call_hours': round((app_stat['audio_call_duration'] or 0) / 3600, 2),
            })
        
        # Aktivitätstyp-Daten formatieren
        activity_data = []
        for activity_stat in statistics['activity_stats']:
            activity_data.append({
                'activity_type': activity_stat['activity_type'],
                'activity_display_name': dict(AppUsageTracking.ACTIVITY_TYPE_CHOICES)[activity_stat['activity_type']],
                'total_sessions': activity_stat['total_sessions'],
                'total_duration_hours': round((activity_stat['total_duration'] or 0) / 3600, 2),
                'avg_duration_minutes': round((activity_stat['avg_duration'] or 0) / 60, 1),
            })
        
        # Call-Statistiken formatieren
        call_stats = statistics['call_stats']
        formatted_call_stats = {
            'total_video_calls': call_stats['total_video_calls'],
            'total_audio_calls': call_stats['total_audio_calls'],
            'total_video_hours': round(call_stats['total_video_duration'] / 3600, 2),
            'total_audio_hours': round(call_stats['total_audio_duration'] / 3600, 2),
            'avg_video_call_minutes': round((call_stats['avg_video_call_duration'] or 0) / 60, 1),
            'avg_audio_call_minutes': round((call_stats['avg_audio_call_duration'] or 0) / 60, 1),
        }
        
        data = {
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name(),
                'is_online': user.is_currently_online(),
            },
            'summary': {
                'total_sessions': statistics['total_sessions'],
                'total_duration_hours': round(statistics['total_duration'] / 3600, 2),
                'days_analyzed': days,
            },
            'chart_data': chart_data,
            'app_data': app_data,
            'activity_data': activity_data,
            'call_stats': formatted_call_stats,
        }
        
        return JsonResponse(data)
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Benutzer nicht gefunden'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Fehler beim Laden der Statistiken: {str(e)}'}, status=500)


@login_required
def profile_view(request):
    """Benutzer-Profil anzeigen und bearbeiten"""
    # Video-App Abo-Daten für Template
    video_storage, created = VideoUserStorage.objects.get_or_create(user=request.user)
    video_usage_percentage = (video_storage.used_storage / video_storage.max_storage * 100) if video_storage.max_storage > 0 else 0
    
    if request.method == 'POST':
        # Prüfe ob Profilbild gelöscht werden soll
        if request.POST.get('delete_profile_picture') == 'true':
            if request.user.profile_picture:
                import os
                try:
                    os.remove(request.user.profile_picture.path)
                except OSError:
                    pass
                request.user.profile_picture = None
                request.user.save()
                messages.success(request, 'Ihr Profilbild wurde erfolgreich gelöscht!')
            else:
                messages.info(request, 'Kein Profilbild vorhanden.')
            return redirect('accounts:profile')
        
        # Normale Profilaktualisierung
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Ihr Profil wurde erfolgreich aktualisiert!')
            return redirect('accounts:profile')
    else:
        profile_form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'user': request.user,
        'video_storage': video_storage,
        'video_usage_percentage': video_usage_percentage,
    })

# @login_required
# def change_password_view(request):
#     """Passwort ändern - INTEGRIERT IN COMPANY_INFO_VIEW"""
#     pass


@login_required
# Old content_editor function removed - now using visual_editor for /content-editor/ URL


def _create_default_page_contents(user, page):
    """Erstellt Standard-Inhalte für verschiedene Seitentypen"""
    if page == 'startseite':
        _create_default_startseite_contents(user)
    elif page == 'impressum':
        _create_default_impressum_contents(user)
    elif page == 'agb':
        _create_default_agb_contents(user)
    elif page == 'datenschutz':
        _create_default_datenschutz_contents(user)
    elif 'dashboard' in page:
        _create_default_dashboard_contents(user, page)
    elif 'landing' in page:
        _create_default_landing_contents(user, page)
    elif 'shop' in page:
        _create_default_shop_contents(user, page)
    elif page in ['header', 'footer']:
        _create_default_global_contents(user, page)
    else:
        _create_default_generic_contents(user, page)


def _create_default_startseite_contents(user):
    """Erstellt Standard-Inhalte für die Startseite basierend auf dem Template"""
    default_contents = [
        # Hero Section
        {'key': 'hero_title', 'type': 'hero_title', 'content': 'Dein All-in-One Business Hub', 'section': 'hero', 'order': 1},
        {'key': 'hero_subtitle', 'type': 'hero_subtitle', 'content': 'Alle wichtigen Tools für Selbständige und Online-Shop-Gründer an einem Ort', 'section': 'hero', 'order': 2},
        {'key': 'hero_button', 'type': 'button_text', 'content': 'Kostenlos starten', 'section': 'hero', 'order': 3},
        
        # Value Proposition
        {'key': 'value_title', 'type': 'section_title', 'content': 'Starte dein Business ohne hohe Kosten', 'section': 'value', 'order': 4},
        {'key': 'value_text', 'type': 'section_text', 'content': 'Workloom bündelt alle wichtigen Business-Tools in einer Plattform. Spare Zeit und Geld, während du dein Unternehmen aufbaust.', 'section': 'value', 'order': 5},
        
        # Community Section
        {'key': 'community_title', 'type': 'section_title', 'content': 'Gemeinsam stärker', 'section': 'community', 'order': 6},
        {'key': 'community_text', 'type': 'section_text', 'content': 'Bei Workloom bist du nicht allein. Unsere Community aus Selbständigen und Shop-Betreibern unterstützt sich gegenseitig.', 'section': 'community', 'order': 7},
        {'key': 'testimonial_1', 'type': 'testimonial', 'content': 'Workloom hat mir geholfen, meinen Shop aufzubauen ohne teure Tools kaufen zu müssen. Die Community ist unbezahlbar!', 'section': 'community', 'order': 8},
        {'key': 'testimonial_1_author', 'type': 'text', 'content': '- Sarah, Online-Shop-Gründerin', 'section': 'community', 'order': 9},
        {'key': 'testimonial_2', 'type': 'testimonial', 'content': 'Endlich alle wichtigen Business-Tools an einem Ort. Das spart mir täglich Zeit und Nerven.', 'section': 'community', 'order': 10},
        {'key': 'testimonial_2_author', 'type': 'text', 'content': '- Max, Selbständiger Designer', 'section': 'community', 'order': 11},
        
        # Pricing Section
        {'key': 'pricing_title', 'type': 'section_title', 'content': 'Einfache, transparente Preise', 'section': 'pricing', 'order': 12},
        {'key': 'price_value', 'type': 'text', 'content': 'Kostenlos', 'section': 'pricing', 'order': 13},
        {'key': 'pricing_text', 'type': 'section_text', 'content': 'Starte ohne Risiko und ohne versteckte Kosten.<br>Upgrade nur wenn du mehr brauchst.', 'section': 'pricing', 'order': 14},
        {'key': 'pricing_button', 'type': 'button_text', 'content': 'Jetzt kostenlos registrieren', 'section': 'pricing', 'order': 15},
        
        # Call to Action
        {'key': 'cta_title', 'type': 'section_title', 'content': 'Bereit durchzustarten?', 'section': 'cta', 'order': 16},
        {'key': 'cta_text', 'type': 'section_text', 'content': 'Schließe dich hunderten von Selbständigen und Shop-Gründern an, die mit Workloom ihr Business aufbauen.', 'section': 'cta', 'order': 17},
        {'key': 'cta_button_1', 'type': 'button_text', 'content': 'Kostenlos starten', 'section': 'cta', 'order': 18},
        {'key': 'cta_button_2', 'type': 'button_text', 'content': 'Mehr erfahren', 'section': 'cta', 'order': 19},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user,
            page='startseite',
            content_key=item['key'],
            defaults={
                'content_type': item['type'],
                'text_content': item['content'],
                'sort_order': item['order'],
                'is_active': True,
                'section': item['section']
            }
        )


def _organize_contents_by_section(contents):
    """Organisiert Inhalte nach Bereichen für bessere Übersicht"""
    sections = {}
    section_names = {
        'hero': 'Hero-Bereich',
        'value': 'Wertversprechen',
        'features': 'Features',
        'community': 'Community',
        'pricing': 'Preise',
        'cta': 'Call-to-Action',
        'custom': 'Benutzerdefiniert'
    }
    
    for content in contents:
        section = getattr(content, 'section', 'custom') or 'custom'
        section_name = section_names.get(section, section.title())
        
        if section not in sections:
            sections[section] = {
                'name': section_name,
                'contents': []
            }
        sections[section]['contents'].append(content)
    
    return sections


def _create_default_impressum_contents(user):
    """Erstellt Standard-Inhalte für Impressum"""
    default_contents = [
        {'key': 'impressum_title', 'type': 'section_title', 'content': 'Impressum', 'section': 'legal', 'order': 1},
        {'key': 'company_info', 'type': 'section_text', 'content': 'Angaben gemäß § 5 TMG\n\nFirmenname\nStraße Hausnummer\nPLZ Ort', 'section': 'legal', 'order': 2},
        {'key': 'contact_title', 'type': 'section_title', 'content': 'Kontakt', 'section': 'contact', 'order': 3},
        {'key': 'contact_info', 'type': 'section_text', 'content': 'Telefon: +49 (0) 123 456789\nE-Mail: info@example.com', 'section': 'contact', 'order': 4},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page='impressum', content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_agb_contents(user):
    """Erstellt Standard-Inhalte für AGB"""
    default_contents = [
        {'key': 'agb_title', 'type': 'section_title', 'content': 'Allgemeine Geschäftsbedingungen', 'section': 'legal', 'order': 1},
        {'key': 'scope_title', 'type': 'section_title', 'content': '§ 1 Geltungsbereich', 'section': 'terms', 'order': 2},
        {'key': 'scope_text', 'type': 'section_text', 'content': 'Diese AGB gelten für alle Geschäfte zwischen uns und unseren Kunden.', 'section': 'terms', 'order': 3},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page='agb', content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_datenschutz_contents(user):
    """Erstellt Standard-Inhalte für Datenschutz"""
    default_contents = [
        {'key': 'privacy_title', 'type': 'section_title', 'content': 'Datenschutzerklärung', 'section': 'legal', 'order': 1},
        {'key': 'data_collection_title', 'type': 'section_title', 'content': 'Datenerfassung', 'section': 'privacy', 'order': 2},
        {'key': 'data_collection_text', 'type': 'section_text', 'content': 'Wir erheben und verwenden Ihre Daten nur im Rahmen der gesetzlichen Bestimmungen.', 'section': 'privacy', 'order': 3},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page='datenschutz', content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_dashboard_contents(user, page):
    """Erstellt Standard-Inhalte für Dashboard-Seiten"""
    app_name = page.replace('_dashboard', '').replace('_', ' ').title()
    default_contents = [
        {'key': 'dashboard_title', 'type': 'section_title', 'content': f'{app_name} Dashboard', 'section': 'header', 'order': 1},
        {'key': 'welcome_text', 'type': 'section_text', 'content': f'Willkommen im {app_name} Bereich. Hier können Sie alle Funktionen verwalten.', 'section': 'header', 'order': 2},
        {'key': 'features_title', 'type': 'section_title', 'content': 'Verfügbare Funktionen', 'section': 'features', 'order': 3},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page=page, content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_landing_contents(user, page):
    """Erstellt Standard-Inhalte für Landing Pages"""
    page_type = page.replace('landing_', '').replace('_', ' ').title()
    default_contents = [
        {'key': 'landing_title', 'type': 'hero_title', 'content': f'{page_type}', 'section': 'hero', 'order': 1},
        {'key': 'landing_subtitle', 'type': 'hero_subtitle', 'content': f'Erfahren Sie mehr über unsere {page_type.lower()}', 'section': 'hero', 'order': 2},
        {'key': 'cta_button', 'type': 'button_text', 'content': 'Mehr erfahren', 'section': 'hero', 'order': 3},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page=page, content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_shop_contents(user, page):
    """Erstellt Standard-Inhalte für Shop-Seiten"""
    page_type = page.replace('shop_', '').replace('_', ' ').title()
    default_contents = [
        {'key': 'shop_title', 'type': 'section_title', 'content': f'{page_type}', 'section': 'header', 'order': 1},
        {'key': 'shop_description', 'type': 'section_text', 'content': f'Hier finden Sie alle {page_type.lower()} in unserem Online-Shop.', 'section': 'header', 'order': 2},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page=page, content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_global_contents(user, page):
    """Erstellt Standard-Inhalte für globale Bereiche (Header/Footer)"""
    if page == 'header':
        default_contents = [
            {'key': 'site_logo', 'type': 'image', 'content': '', 'section': 'branding', 'order': 1},
            {'key': 'site_title', 'type': 'text', 'content': 'Ihre Website', 'section': 'branding', 'order': 2},
            {'key': 'nav_home', 'type': 'button_text', 'content': 'Startseite', 'section': 'navigation', 'order': 3},
            {'key': 'nav_about', 'type': 'button_text', 'content': 'Über uns', 'section': 'navigation', 'order': 4},
            {'key': 'nav_contact', 'type': 'button_text', 'content': 'Kontakt', 'section': 'navigation', 'order': 5},
        ]
    else:  # footer
        default_contents = [
            {'key': 'footer_copyright', 'type': 'text', 'content': '© 2024 Ihre Website. Alle Rechte vorbehalten.', 'section': 'legal', 'order': 1},
            {'key': 'footer_links_title', 'type': 'section_title', 'content': 'Links', 'section': 'links', 'order': 2},
            {'key': 'footer_impressum', 'type': 'button_text', 'content': 'Impressum', 'section': 'links', 'order': 3},
            {'key': 'footer_datenschutz', 'type': 'button_text', 'content': 'Datenschutz', 'section': 'links', 'order': 4},
        ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page=page, content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


def _create_default_generic_contents(user, page):
    """Erstellt Standard-Inhalte für generische Seiten"""
    page_name = page.replace('_', ' ').title()
    default_contents = [
        {'key': 'page_title', 'type': 'section_title', 'content': page_name, 'section': 'header', 'order': 1},
        {'key': 'page_content', 'type': 'section_text', 'content': f'Willkommen auf der {page_name} Seite. Hier können Sie Inhalte hinzufügen und bearbeiten.', 'section': 'content', 'order': 2},
        {'key': 'page_cta', 'type': 'button_text', 'content': 'Mehr erfahren', 'section': 'content', 'order': 3},
    ]
    
    for item in default_contents:
        EditableContent.objects.get_or_create(
            user=user, page=page, content_key=item['key'],
            defaults={
                'content_type': item['type'], 'text_content': item['content'],
                'sort_order': item['order'], 'is_active': True, 'section': item['section']
            }
        )


@login_required
@require_http_methods(["POST"])
def update_content(request):
    """AJAX-View zum Aktualisieren von Inhalten"""
    # Check if this is a sort order update request
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'update_sort_order':
                updates = data.get('updates', [])
                for update in updates:
                    content_id = update.get('id')
                    sort_order = update.get('sort_order')
                    try:
                        content = EditableContent.objects.get(id=content_id, user=request.user)
                        content.sort_order = sort_order
                        content.save(update_fields=['sort_order'])
                    except EditableContent.DoesNotExist:
                        continue
                return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    try:
        content_id = request.POST.get('content_id')
        page = request.POST.get('page')
        content_key = request.POST.get('content_key')
        content_type = request.POST.get('content_type')
        text_content = request.POST.get('text_content', '')
        image_alt_text = request.POST.get('image_alt_text', '')
        link_url = request.POST.get('link_url', '')
        sort_order = request.POST.get('sort_order')
        
        if content_id:
            # Update existing content
            content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        else:
            # Create new content - handle sort order
            if sort_order is None:
                # Default: append at the end
                max_sort_order = EditableContent.objects.filter(
                    user=request.user, 
                    page=page
                ).aggregate(models.Max('sort_order'))['sort_order__max'] or 0
                sort_order = max_sort_order + 1
            else:
                sort_order = int(sort_order)
                # If inserting at top (sort_order = 0), shift other elements down
                if sort_order == 0:
                    EditableContent.objects.filter(
                        user=request.user,
                        page=page
                    ).update(sort_order=models.F('sort_order') + 1)
            
            content = EditableContent.objects.create(
                user=request.user,
                page=page,
                content_key=content_key,
                content_type=content_type,
                sort_order=sort_order
            )
        
        content.text_content = text_content
        content.image_alt_text = image_alt_text
        content.link_url = link_url
        
        # Handle HTML and CSS content
        html_content = request.POST.get('html_content', '')
        css_content = request.POST.get('css_content', '')
        ai_prompt = request.POST.get('ai_prompt', '')
        
        # Handle font styling options for text content
        if content_type in ['text', 'section_title', 'section_text', 'hero_title', 'hero_subtitle', 'button_text']:
            font_family = request.POST.get('font_family', '')
            font_size = request.POST.get('font_size', '')
            font_weight = request.POST.get('font_weight', '')
            font_color = request.POST.get('font_color', '')
            text_align = request.POST.get('text_align', '')
            font_style = request.POST.get('font_style', '')
            text_decoration = request.POST.get('text_decoration', '')
            
            # Build CSS from font styling options
            css_rules = []
            if font_family:
                css_rules.append(f"font-family: {font_family};")
            if font_size:
                css_rules.append(f"font-size: {font_size};")
            if font_weight:
                css_rules.append(f"font-weight: {font_weight};")
            if font_color:
                css_rules.append(f"color: {font_color};")
            if text_align:
                css_rules.append(f"text-align: {text_align};")
            if font_style:
                css_rules.append(f"font-style: {font_style};")
            if text_decoration:
                css_rules.append(f"text-decoration: {text_decoration};")
            
            # If we have font styling rules, merge them with existing CSS
            if css_rules:
                font_css = " ".join(css_rules)
                if css_content:
                    # Merge with existing CSS
                    css_content = css_content + " " + font_css
                else:
                    css_content = font_css
        
        if html_content:
            content.html_content = html_content
        if css_content:
            content.css_content = css_content
        if ai_prompt:
            content.ai_prompt = ai_prompt
        
        # Handle image upload
        if 'image_content' in request.FILES:
            content.image_content = request.FILES['image_content']
        
        content.save()
        
        return JsonResponse({
            'success': True,
            'content_id': content.id,
            'display_content': content.get_display_content()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_content(request):
    """AJAX-View zum Löschen von Inhalten"""
    try:
        content_id = request.POST.get('content_id')
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        content.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_content(request, content_id):
    """AJAX-View zum Laden eines einzelnen Inhalts"""
    try:
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        
        return JsonResponse({
            'success': True,
            'content': {
                'id': content.id,
                'page': content.page,
                'content_key': content.content_key,
                'content_type': content.content_type,
                'text_content': content.text_content,
                'image_content': content.image_content.url if content.image_content else None,
                'image_alt_text': content.image_alt_text,
                'link_url': content.link_url,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def generate_ai_content(request):
    """AJAX-View für KI-gestützte Content-Generierung"""
    try:
        import json
        from naturmacher.services.ai_service import generate_html_content
        
        data = json.loads(request.body)
        prompt = data.get('prompt', '')
        content_type = data.get('content_type', 'ai_generated')
        page = data.get('page', 'startseite')
        
        if not prompt:
            return JsonResponse({'success': False, 'error': 'Prompt ist erforderlich'})
        
        # Nutze den bestehenden AI Service
        try:
            result = generate_html_content(request.user, prompt)
            
            if result.get('success'):
                html_content = result.get('html', '')
                css_content = result.get('css', '')
                
                return JsonResponse({
                    'success': True,
                    'html_content': html_content,
                    'css_content': css_content,
                    'prompt': prompt
                })
            else:
                return JsonResponse({'success': False, 'error': result.get('error', 'KI-Generierung fehlgeschlagen')})
                
        except Exception as ai_error:
            return JsonResponse({'success': False, 'error': f'KI-Service Fehler: {str(ai_error)}'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def ai_edit_content(request):
    """AJAX-View für KI-gestützte Container/Element-Bearbeitung"""
    try:
        from naturmacher.services.ai_service import generate_html_content
        
        content_id = request.POST.get('content_id')
        structure_prompt = request.POST.get('structure_prompt', '').strip()
        style_prompt = request.POST.get('style_prompt', '').strip()
        
        if not content_id:
            return JsonResponse({'success': False, 'error': 'Content ID ist erforderlich'})
        
        if not structure_prompt and not style_prompt:
            return JsonResponse({'success': False, 'error': 'Mindestens eine Struktur- oder Style-Änderung ist erforderlich'})
        
        # Get the content object
        try:
            content = EditableContent.objects.get(id=content_id, user=request.user)
        except EditableContent.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Content nicht gefunden'})
        
        # Prepare the AI prompt
        current_html = content.html_content or ''
        current_css = content.css_content or ''
        current_text = content.text_content or ''
        
        # Build comprehensive prompt for AI
        ai_prompt = f"""Bitte bearbeite das folgende HTML/CSS-Element entsprechend den Anweisungen:

AKTUELLER HTML-CODE:
{current_html}

AKTUELLER CSS-CODE:
{current_css}

AKTUELLER TEXT-INHALT:
{current_text}

STRUKTUR-ÄNDERUNGEN:
{structure_prompt if structure_prompt else 'Keine Struktur-Änderungen'}

STYLE-ÄNDERUNGEN:
{style_prompt if style_prompt else 'Keine Style-Änderungen'}

Bitte gib den überarbeiteten HTML- und CSS-Code zurück, der die gewünschten Änderungen umsetzt. Behalte die Funktionalität bei und verbessere das Design entsprechend den Anweisungen."""

        # Use AI service to generate modified content
        try:
            result = generate_html_content(request.user, ai_prompt)
            
            if result.get('success'):
                new_html = result.get('html', current_html)
                new_css = result.get('css', current_css)
                
                # Update the content
                content.html_content = new_html
                content.css_content = new_css
                content.ai_prompt = ai_prompt  # Store the prompt for reference
                content.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Element erfolgreich mit KI bearbeitet'
                })
            else:
                return JsonResponse({'success': False, 'error': result.get('error', 'KI-Bearbeitung fehlgeschlagen')})
                
        except Exception as ai_error:
            return JsonResponse({'success': False, 'error': f'KI-Service Fehler: {str(ai_error)}'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def ai_rephrase_content(request):
    """AJAX-View für KI-gestützte Text-Umformulierung"""
    try:
        from naturmacher.services.ai_service import generate_html_content
        
        content_id = request.POST.get('content_id')
        rephrase_prompt = request.POST.get('rephrase_prompt', '').strip()
        
        if not content_id:
            return JsonResponse({'success': False, 'error': 'Content ID ist erforderlich'})
        
        # Get the content object
        try:
            content = EditableContent.objects.get(id=content_id, user=request.user)
        except EditableContent.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Content nicht gefunden'})
        
        current_text = content.text_content or ''
        if not current_text:
            return JsonResponse({'success': False, 'error': 'Kein Text zum Umformulieren vorhanden'})
        
        # Build AI prompt for text rephrasing
        ai_prompt = f"""Bitte formuliere den folgenden Text um:

AKTUELLER TEXT:
"{current_text}"

ANWEISUNGEN:
{rephrase_prompt if rephrase_prompt else 'Formuliere den Text neu, behalte aber die Bedeutung bei. Mache ihn ansprechender und klarer.'}

Gib nur den umformulierten Text zurück, ohne zusätzliche Erklärungen oder Formatierung."""

        # Use AI service to rephrase text
        try:
            result = generate_html_content(request.user, ai_prompt)
            
            if result.get('success'):
                # For text rephrasing, we expect the result in the HTML field
                new_text = result.get('html', '').strip()
                
                # Clean up the response (remove HTML tags if any)
                import re
                new_text = re.sub(r'<[^>]+>', '', new_text)
                new_text = new_text.strip()
                
                if not new_text:
                    return JsonResponse({'success': False, 'error': 'KI hat keinen umformulierten Text zurückgegeben'})
                
                return JsonResponse({
                    'success': True,
                    'new_text': new_text,
                    'message': 'Text erfolgreich umformuliert'
                })
            else:
                return JsonResponse({'success': False, 'error': result.get('error', 'Text-Umformulierung fehlgeschlagen')})
                
        except Exception as ai_error:
            return JsonResponse({'success': False, 'error': f'KI-Service Fehler: {str(ai_error)}'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_page(request):
    """Erstellt eine neue benutzerdefinierte Seite"""
    try:
        data = json.loads(request.body)
        page_name = data.get('page_name', '').strip().lower()
        display_name = data.get('display_name', '').strip()
        page_type = data.get('page_type', 'custom')
        description = data.get('description', '').strip()
        
        # Validation
        if not page_name or not display_name:
            return JsonResponse({'success': False, 'error': 'Seiten-Name und Anzeigename sind erforderlich'})
        
        # Check if page already exists
        if CustomPage.objects.filter(user=request.user, page_name=page_name).exists():
            return JsonResponse({'success': False, 'error': 'Eine Seite mit diesem Namen existiert bereits'})
        
        # Create new page
        new_page = CustomPage.objects.create(
            user=request.user,
            page_name=page_name,
            display_name=display_name,
            page_type=page_type,
            description=description
        )
        
        # Don't create initial content - pages should start empty
        
        return JsonResponse({
            'success': True,
            'page_name': page_name,
            'display_name': display_name,
            'redirect_url': f'/accounts/content-editor/?page={page_name}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def create_initial_content(user, page_name, page_type, display_name, description):
    """Erstellt initial Content basierend auf Seitentyp"""
    
    # Base content for all page types
    initial_contents = []
    
    if page_type == 'landing':
        initial_contents = [
            {
                'content_key': 'hero_title',
                'content_type': 'hero_title',
                'text_content': f'Willkommen bei {display_name}',
                'sort_order': 0
            },
            {
                'content_key': 'hero_subtitle', 
                'content_type': 'hero_subtitle',
                'text_content': description or 'Ihre Lösung für erfolgreiche Projekte',
                'sort_order': 1
            },
            {
                'content_key': 'features_title',
                'content_type': 'section_title', 
                'text_content': 'Unsere Leistungen',
                'sort_order': 2
            },
            {
                'content_key': 'cta_button',
                'content_type': 'button_text',
                'text_content': 'Jetzt starten',
                'sort_order': 3
            }
        ]
    elif page_type == 'about':
        initial_contents = [
            {
                'content_key': 'about_title',
                'content_type': 'section_title',
                'text_content': f'Über {display_name}',
                'sort_order': 0
            },
            {
                'content_key': 'about_intro',
                'content_type': 'section_text',
                'text_content': description or 'Erfahren Sie mehr über unser Unternehmen und unsere Mission.',
                'sort_order': 1
            },
            {
                'content_key': 'mission_title',
                'content_type': 'section_title',
                'text_content': 'Unsere Mission',
                'sort_order': 2
            }
        ]
    elif page_type == 'contact':
        initial_contents = [
            {
                'content_key': 'contact_title',
                'content_type': 'section_title',
                'text_content': 'Kontakt',
                'sort_order': 0
            },
            {
                'content_key': 'contact_intro',
                'content_type': 'section_text',
                'text_content': 'Nehmen Sie Kontakt mit uns auf - wir freuen uns auf Ihre Nachricht!',
                'sort_order': 1
            }
        ]
    elif page_type == 'services':
        initial_contents = [
            {
                'content_key': 'services_title',
                'content_type': 'section_title',
                'text_content': 'Unsere Services',
                'sort_order': 0
            },
            {
                'content_key': 'services_intro',
                'content_type': 'section_text',
                'text_content': description or 'Entdecken Sie unser umfangreiches Leistungsportfolio.',
                'sort_order': 1
            }
        ]
    else:  # custom, blog, gallery
        initial_contents = [
            {
                'content_key': f'{page_name}_title',
                'content_type': 'section_title',
                'text_content': display_name,
                'sort_order': 0
            },
            {
                'content_key': f'{page_name}_content',
                'content_type': 'section_text',
                'text_content': description or f'Willkommen auf der {display_name} Seite.',
                'sort_order': 1
            }
        ]
    
    # Create content objects
    for content_data in initial_contents:
        EditableContent.objects.create(
            user=user,
            page=page_name,
            **content_data
        )


@login_required
@require_http_methods(["POST"])
def delete_page(request):
    """Löscht eine benutzerdefinierte Seite und alle zugehörigen Inhalte"""
    try:
        data = json.loads(request.body)
        page_name = data.get('page_name', '').strip()
        
        if not page_name:
            return JsonResponse({'success': False, 'error': 'Seiten-Name ist erforderlich'})
        
        # Prüfe ob es eine benutzerdefinierte Seite ist (Startseite kann nicht gelöscht werden)
        if page_name == 'startseite':
            return JsonResponse({'success': False, 'error': 'Die Startseite kann nicht gelöscht werden'})
        
        # Lösche die Seite
        page = CustomPage.objects.filter(user=request.user, page_name=page_name).first()
        if not page:
            return JsonResponse({'success': False, 'error': 'Seite nicht gefunden'})
        
        # Lösche alle zugehörigen Inhalte
        EditableContent.objects.filter(user=request.user, page=page_name).delete()
        
        # Lösche die Seite
        page.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Seite "{page.display_name}" wurde erfolgreich gelöscht'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_seo_settings(request):
    """Lädt SEO-Einstellungen für eine Seite"""
    page = request.GET.get('page', 'startseite')
    
    try:
        seo_settings = SEOSettings.objects.get(user=request.user, page=page)
        return JsonResponse({
            'success': True,
            'seo_title': seo_settings.seo_title,
            'seo_description': seo_settings.seo_description,
            'keywords': seo_settings.keywords,
            'canonical_url': seo_settings.canonical_url,
            'noindex': seo_settings.noindex,
        })
    except SEOSettings.DoesNotExist:
        return JsonResponse({
            'success': True,
            'seo_title': '',
            'seo_description': '',
            'keywords': '',
            'canonical_url': '',
            'noindex': False,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def save_seo_settings(request):
    """Speichert SEO-Einstellungen für eine Seite"""
    try:
        page = request.POST.get('page')
        seo_title = request.POST.get('seo_title', '')
        seo_description = request.POST.get('seo_description', '')
        keywords = request.POST.get('keywords', '')
        canonical_url = request.POST.get('canonical_url', '')
        noindex = request.POST.get('noindex') == 'on'
        
        # Update or create SEO settings
        seo_settings, created = SEOSettings.objects.update_or_create(
            user=request.user,
            page=page,
            defaults={
                'seo_title': seo_title,
                'seo_description': seo_description,
                'keywords': keywords,
                'canonical_url': canonical_url,
                'noindex': noindex,
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'SEO Einstellungen erfolgreich gespeichert'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_alt_texts(request):
    """Lädt alle Alt-Texte für Bilder einer Seite"""
    page = request.GET.get('page', 'startseite')
    
    try:
        # Hole alle Bild-Inhalte für diese Seite
        image_contents = EditableContent.objects.filter(
            user=request.user,
            page=page,
            content_type='image'
        ).exclude(image_content='')
        
        alt_texts = []
        for content in image_contents:
            if content.image_content:
                alt_texts.append({
                    'id': content.id,
                    'content_key': content.content_key,
                    'image_url': content.image_content.url,
                    'alt_text': content.image_alt_text or '',
                })
        
        return JsonResponse({
            'success': True,
            'alt_texts': alt_texts
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def manage_subscription(request, app_name):
    """Abo-Verwaltung für verschiedene Apps"""
    if app_name == 'video':
        return manage_video_subscription(request)
    else:
        messages.error(request, f'Abo-Verwaltung für App "{app_name}" nicht verfügbar.')
        return redirect('accounts:profile')


@login_required
def manage_video_subscription(request):
    """Video-App Abo-Verwaltung mit Stripe-Integration"""
    from videos.subscription_sync import StorageSubscriptionSync
    from payments.models import SubscriptionPlan
    
    # Sync user storage with Stripe subscriptions
    video_storage = StorageSubscriptionSync.sync_user_storage(request.user)
    plan_info = StorageSubscriptionSync.get_user_plan_info(request.user)
    
    # Get available Stripe plans
    available_plans = SubscriptionPlan.objects.filter(
        is_active=True,
        plan_type='storage'
    ).order_by('price')
    
    video_usage_percentage = plan_info['used_percentage']
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'change_plan':
            # For now, redirect to Stripe checkout
            # In the future, we could implement direct plan changes here
            messages.info(request, 'Bitte verwenden Sie die neue Stripe-Integration für Plan-Änderungen.')
            return redirect('payments:subscription_plans')
        
        return redirect('accounts:manage_subscription', app_name='video')
    
    # Prepare storage options for slider (maintaining compatibility)
    storage_options = []
    for plan in available_plans:
        option = {
            'mb': plan.storage_mb,
            'gb': plan.storage_mb / 1024 if plan.storage_mb >= 1024 else None,
            'price': float(plan.price),
            'name': plan.name,
            'bytes': plan.storage_mb * 1024 * 1024
        }
        storage_options.append(option)
    
    # Get current subscription info
    stripe_subscription = StorageSubscriptionSync.get_user_active_subscription(request.user)
    
    context = {
        'video_storage': video_storage,
        'video_usage_percentage': video_usage_percentage,
        'current_subscription': stripe_subscription,
        'videos_count': request.user.videos.count() if hasattr(request.user, 'videos') else 0,
        'available_space_mb': plan_info['available_mb'],
        'storage_options': storage_options,
        'current_storage_mb': plan_info['max_storage_mb'],
        'current_price': plan_info['price'],
        'plan_info': plan_info,
        'stripe_integration': True,  # Flag to indicate we're using Stripe
    }
    
    return render(request, 'accounts/manage_video_subscription.html', context)


@login_required
def app_info(request, app_name):
    """Zeigt detaillierte Informationen über eine App/Feature"""
    try:
        app_info = AppInfo.objects.get(app_name=app_name)
    except AppInfo.DoesNotExist:
        # Fallback: Erstelle minimale Info wenn nicht vorhanden
        app_info = AppInfo(
            app_name=app_name,
            title=app_name.replace('_', ' ').title(),
            short_description=f"Informationen über {app_name}",
            detailed_description="Detaillierte Informationen zu dieser App sind noch nicht verfügbar.",
            key_features=[],
            development_status='development'
        )
    
    # Feature Access Status prüfen
    feature_access = None
    try:
        feature_access = FeatureAccess.objects.get(app_name=app_name)
    except FeatureAccess.DoesNotExist:
        pass
    
    # Aktuellen Zugriffsstatus ermitteln
    has_access = False
    access_message = "Zugriff nicht verfügbar"
    
    if feature_access:
        has_access = feature_access.user_has_access(request.user)
        if feature_access.subscription_required == 'in_development':
            access_message = "Diese App befindet sich in der Entwicklung"
        elif feature_access.subscription_required == 'free':
            access_message = "Kostenlos verfügbar"
        elif feature_access.subscription_required == 'founder_access':
            access_message = "Founder's Early Access erforderlich"
        elif feature_access.subscription_required == 'any_paid':
            access_message = "Beliebiges bezahltes Abonnement erforderlich"
        elif feature_access.subscription_required == 'storage_plan':
            access_message = "Storage-Plan erforderlich"
        elif feature_access.subscription_required == 'blocked':
            access_message = "Aktuell nicht verfügbar"
    
    context = {
        'app_info': app_info,
        'feature_access': feature_access,
        'has_access': has_access,
        'access_message': access_message,
    }
    
    return render(request, 'accounts/app_info.html', context)


# Zoho Mail API Management Views
@login_required
@require_http_methods(["GET", "POST"])
def zoho_settings_api(request):
    """API endpoint für Zoho Mail Einstellungen"""
    try:
        zoho_settings, created = ZohoAPISettings.objects.get_or_create(user=request.user)
        
        if request.method == 'GET':
            # Einstellungen laden
            return JsonResponse({
                'success': True,
                'settings': {
                    'client_id': zoho_settings.client_id or '',
                    'client_secret': '***' if zoho_settings.client_secret else '',
                    'region': zoho_settings.region,
                    'redirect_uri': zoho_settings.redirect_uri or f"{request.build_absolute_uri('/')[:-1]}/mail/auth/callback/",
                    'status': zoho_settings.get_configuration_status(),
                    'is_configured': zoho_settings.is_configured,
                    'access_token': bool(zoho_settings.access_token),
                    'last_test_success': zoho_settings.last_test_success.isoformat() if zoho_settings.last_test_success else None,
                }
            })
        
        elif request.method == 'POST':
            # Einstellungen speichern
            client_id = request.POST.get('client_id', '').strip()
            client_secret = request.POST.get('client_secret', '').strip()
            region = request.POST.get('region', 'EU')
            redirect_uri = request.POST.get('redirect_uri', '').strip()
            
            if not client_id or not client_secret:
                return JsonResponse({
                    'success': False,
                    'error': 'Client ID und Client Secret sind erforderlich'
                })
            
            # Einstellungen aktualisieren
            zoho_settings.client_id = client_id
            zoho_settings.client_secret = client_secret
            zoho_settings.region = region
            zoho_settings.redirect_uri = redirect_uri
            zoho_settings.is_configured = True
            zoho_settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Zoho Mail Einstellungen gespeichert'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Verarbeiten der Einstellungen: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def zoho_test_api(request):
    """API endpoint zum Testen der Zoho Mail Verbindung"""
    try:
        zoho_settings = ZohoAPISettings.objects.get(user=request.user)
        
        if not zoho_settings.is_configured:
            return JsonResponse({
                'success': False,
                'error': 'Zoho Mail ist nicht konfiguriert'
            })
        
        # Importiere die Mail App Services
        from mail_app.services import ZohoMailAPIService
        from mail_app.models import EmailAccount
        
        # Erstelle temporären Account für Test
        if zoho_settings.access_token:
            temp_account = EmailAccount(
                user=request.user,
                email_address='test@example.com',
                access_token=zoho_settings.access_token
            )
            
            api_service = ZohoMailAPIService(temp_account)
            api_service.base_url = zoho_settings.base_url
            
            # Test API Connection
            if api_service.test_connection():
                from django.utils import timezone
                zoho_settings.last_test_success = timezone.now()
                zoho_settings.last_error = ''
                zoho_settings.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Zoho Mail Verbindung erfolgreich getestet'
                })
            else:
                zoho_settings.last_error = 'API Test fehlgeschlagen'
                zoho_settings.save()
                
                return JsonResponse({
                    'success': False,
                    'error': 'API Test fehlgeschlagen - Überprüfen Sie Ihre Konfiguration'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Keine Autorisierung vorhanden - bitte erst autorisieren'
            })
            
    except ZohoAPISettings.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Zoho Mail Einstellungen nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Testen der Verbindung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def zoho_disconnect_api(request):
    """API endpoint zum Trennen der Zoho Mail Verbindung und Löschen aller Email-Daten"""
    try:
        # Get user's email accounts before deletion
        from mail_app.models import EmailAccount
        user_accounts = EmailAccount.objects.filter(user=request.user, is_active=True)
        
        total_deleted_data = {}
        
        for account in user_accounts:
            # Count data before deletion for logging and user feedback
            emails_count = account.emails.count()
            folders_count = account.folders.count() 
            threads_count = account.threads.count()
            drafts_count = account.drafts.count()
            attachments_count = sum(email.attachments.count() for email in account.emails.all())
            sync_logs_count = account.sync_logs.count()
            
            logger.info(f"Disconnecting account {account.email_address} via API - deleting {emails_count} emails, {folders_count} folders, {threads_count} threads, {drafts_count} drafts, {attachments_count} attachments, {sync_logs_count} sync logs")
            
            # Delete all related data (CASCADE will handle most of this automatically)
            # But let's be explicit for clarity and logging
            
            # Delete emails (this will also delete attachments due to CASCADE)
            account.emails.all().delete()
            
            # Delete folders
            account.folders.all().delete()
            
            # Delete threads
            account.threads.all().delete()
            
            # Delete drafts
            account.drafts.all().delete()
            
            # Delete sync logs
            account.sync_logs.all().delete()
            
            # Update totals for logging
            total_deleted_data['emails'] = total_deleted_data.get('emails', 0) + emails_count
            total_deleted_data['folders'] = total_deleted_data.get('folders', 0) + folders_count
            total_deleted_data['threads'] = total_deleted_data.get('threads', 0) + threads_count
            total_deleted_data['drafts'] = total_deleted_data.get('drafts', 0) + drafts_count
            total_deleted_data['attachments'] = total_deleted_data.get('attachments', 0) + attachments_count
            total_deleted_data['sync_logs'] = total_deleted_data.get('sync_logs', 0) + sync_logs_count
            
            # Deactivate the account and clear OAuth data
            account.is_active = False
            account.access_token = ''
            account.refresh_token = ''
            account.token_expires_at = None
            account.last_sync = None
            account.save()
            
            logger.info(f"Successfully disconnected account {account.email_address} via API")
        
        # Also clear ZohoAPISettings
        try:
            zoho_settings = ZohoAPISettings.objects.get(user=request.user)
            # OAuth Tokens löschen
            zoho_settings.access_token = ''
            zoho_settings.refresh_token = ''
            zoho_settings.token_expires_at = None
            zoho_settings.is_active = False
            zoho_settings.last_test_success = None
            zoho_settings.save()
            logger.info(f"Cleared ZohoAPISettings for user {request.user.username} via API")
        except ZohoAPISettings.DoesNotExist:
            # Settings don't exist, which is fine
            pass
        
        # Create user-friendly message with deletion summary
        deleted_summary = []
        if total_deleted_data.get('emails', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['emails']} Emails")
        if total_deleted_data.get('folders', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['folders']} Ordner")
        if total_deleted_data.get('threads', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['threads']} Unterhaltungen")
        if total_deleted_data.get('drafts', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['drafts']} Entwürfe")
        if total_deleted_data.get('attachments', 0) > 0:
            deleted_summary.append(f"{total_deleted_data['attachments']} Anhänge")
        
        summary_text = ", ".join(deleted_summary) if deleted_summary else "keine Daten"
        
        logger.info(f"Successfully disconnected Zoho Mail for user {request.user.username} via API: {summary_text}")
        
        return JsonResponse({
            'success': True,
            'message': f'Zoho Mail Verbindung getrennt. Gelöscht: {summary_text}.'
        })
        
    except Exception as e:
        logger.error(f"Error disconnecting Zoho Mail for user {request.user.username} via API: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Trennen der Verbindung: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def zoho_delete_all_emails_api(request):
    """API endpoint zum Löschen aller Emails aus der Datenbank (nicht vom Server)"""
    try:
        from mail_app.models import Email, EmailAccount
        
        # Get user's email accounts
        user_accounts = EmailAccount.objects.filter(user=request.user, is_active=True)
        
        if not user_accounts.exists():
            return JsonResponse({
                'success': False,
                'error': 'Keine aktiven Email-Accounts gefunden'
            })
        
        total_deleted = 0
        
        for account in user_accounts:
            # Count emails before deletion
            emails_count = account.emails.count()
            
            logger.info(f"Deleting all emails for account {account.email_address} - {emails_count} emails")
            
            # Delete all emails (attachments will be deleted via CASCADE)
            account.emails.all().delete()
            
            total_deleted += emails_count
            
            logger.info(f"Successfully deleted {emails_count} emails from account {account.email_address}")
        
        logger.info(f"Successfully deleted {total_deleted} total emails for user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'deleted_count': total_deleted,
            'message': f'{total_deleted} Emails wurden aus der Datenbank gelöscht'
        })
        
    except Exception as e:
        logger.error(f"Error deleting all emails for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen der Emails: {str(e)}'
        })


@login_required
def get_model_preferences(request):
    """API Endpoint zum Abrufen der aktuellen KI-Model-Präferenzen des Users"""
    try:
        user = request.user
        return JsonResponse({
            'success': True,
            'openai_model': getattr(user, 'preferred_openai_model', 'gpt-4o-mini'),
            'anthropic_model': getattr(user, 'preferred_anthropic_model', 'claude-3-5-sonnet-20241022')
        })
    except Exception as e:
        logger.error(f"Error fetching model preferences for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Laden der Model-Präferenzen: {str(e)}'
        })


@login_required
def save_model_preference(request):
    """API Endpoint zum Speichern einer KI-Model-Präferenz"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required'})
    
    try:
        data = json.loads(request.body)
        provider = data.get('provider')
        model = data.get('model')
        
        if not provider or not model:
            return JsonResponse({
                'success': False,
                'error': 'Provider und Model sind erforderlich'
            })
        
        user = request.user
        
        # Validate and save based on provider
        if provider == 'openai':
            valid_models = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']
            if model not in valid_models:
                return JsonResponse({
                    'success': False,
                    'error': f'Ungültiges OpenAI Model: {model}'
                })
            user.preferred_openai_model = model
            
        elif provider == 'anthropic':
            valid_models = [
                'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022',
                'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 
                'claude-3-haiku-20240307'
            ]
            if model not in valid_models:
                return JsonResponse({
                    'success': False,
                    'error': f'Ungültiges Anthropic Model: {model}'
                })
            user.preferred_anthropic_model = model
            
        else:
            return JsonResponse({
                'success': False,
                'error': f'Ungültiger Provider: {provider}'
            })
        
        user.save()
        
        logger.info(f"Updated {provider} model preference to {model} for user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'{provider.capitalize()} Model auf {model} aktualisiert'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        logger.error(f"Error saving model preference for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Speichern der Model-Präferenz: {str(e)}'
        })


# E-Mail-Verifikation Funktionen
def send_verification_email(user, request):
    """Sendet eine E-Mail-Verifikation über das Zoho-System an den Benutzer."""
    try:
        # Importiere Zoho-Services
        from email_templates.models import ZohoMailServerConnection, EmailTemplate
        from email_templates.services import EmailTemplateService
        
        # Generiere einen sicheren Token
        token = secrets.token_urlsafe(32)
        
        # Speichere Token und Zeitstempel
        user.email_verification_token = token
        user.email_verification_sent_at = timezone.now()
        user.save()
        
        # Erstelle Verifikations-URL
        try:
            from django.conf import settings

            # Verwende konfigurierte Domain anstatt request.build_absolute_uri()
            if hasattr(settings, 'SITE_DOMAIN') and hasattr(settings, 'SITE_PROTOCOL'):
                verification_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}{reverse('accounts:verify_email', kwargs={'token': token})}"
            else:
                # Fallback auf request.build_absolute_uri()
                verification_url = request.build_absolute_uri(
                    reverse('accounts:verify_email', kwargs={'token': token})
                )
        except Exception as e:
            logger.error(f"Error building verification URL: {str(e)}")
            # Fallback URL mit konfigurierter Domain
            try:
                from django.conf import settings
                if hasattr(settings, 'SITE_DOMAIN') and hasattr(settings, 'SITE_PROTOCOL'):
                    verification_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/accounts/verify-email/{token}/"
                else:
                    verification_url = f"{request.build_absolute_uri('/')[:-1]}/accounts/verify-email/{token}/"
            except:
                verification_url = f"https://workloom.de/accounts/verify-email/{token}/"
        
        # Verwende das neue Trigger-System
        try:
            # Importiere das neue Trigger-System
            from email_templates.trigger_manager import TriggerManager
            trigger_manager = TriggerManager()
            
            context_data = {
                'user_name': user.get_full_name() or user.username,
                'username': user.username,
                'user_email': user.email,
                'verification_url': verification_url,
                'verification_token': token,
                'domain': request.get_host(),
                'site_name': 'Workloom',
                'company_name': 'Workloom'
            }
            
            # Feuer den user_registration Trigger (richtig benannt)
            results = trigger_manager.fire_trigger(
                trigger_key='user_registration',
                context_data=context_data,
                recipient_email=user.email,
                recipient_name=user.get_full_name() or user.username
            )
            
            # Check if any email was sent successfully
            if results and any(result['success'] for result in results):
                logger.info(f"Verification email sent via trigger system to {user.email}")
                return True
            elif results:
                # Some results but all failed
                logger.warning(f"All trigger templates failed for {user.email}, falling back to Django mail")
            else:
                # No results (no templates)
                logger.warning(f"No active templates found for user_registration trigger, falling back to Django mail")
        
        except Exception as trigger_error:
            logger.warning(f"Trigger system failed: {str(trigger_error)}, falling back to Django mail")
        
        # Fallback auf Django E-Mail-System
        html_content = render_to_string('accounts/emails/welcome_verification.html', {
            'user': user,
            'verification_url': verification_url,
        })
        text_content = render_to_string('accounts/emails/welcome_verification.txt', {
            'user': user,
            'verification_url': verification_url,
        })
        
        # Sende E-Mail über Django
        send_mail(
            subject=f'Willkommen bei Workloom - E-Mail bestätigen',
            message=text_content,
            from_email=None,  # Verwendet DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            html_message=html_content,
        )
        
        logger.info(f"Verification email sent via Django mail to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False


def verify_email(request, token):
    """Verifiziert die E-Mail-Adresse eines Benutzers."""
    try:
        # Finde Benutzer mit diesem Token
        user = get_object_or_404(CustomUser, email_verification_token=token)
        
        # Prüfe ob Token noch gültig ist (24 Stunden)
        if user.email_verification_sent_at:
            token_age = timezone.now() - user.email_verification_sent_at
            if token_age > timedelta(hours=24):
                messages.error(request, 
                    'Der Bestätigungslink ist abgelaufen. Bitte fordern Sie einen neuen Link an.')
                return redirect('accounts:resend_verification')
        
        # Aktiviere Benutzer und bestätige E-Mail
        user.email_verified = True
        user.is_active = True
        user.email_verification_token = None  # Token löschen
        user.save()
        
        # Logge Benutzer automatisch ein
        login(request, user)
        
        messages.success(request, 
            f'🎉 Herzlich willkommen bei Workloom, {user.username}! '
            'Ihre E-Mail-Adresse wurde erfolgreich bestätigt.')
        
        logger.info(f"Email verified for user {user.username}")
        return redirect('accounts:dashboard')
        
    except Exception as e:
        logger.error(f"Email verification failed for token {token}: {str(e)}")
        messages.error(request, 
            'Der Bestätigungslink ist ungültig oder abgelaufen. '
            'Bitte fordern Sie einen neuen Link an.')
        return redirect('accounts:resend_verification')


def resend_verification(request):
    """Sendet eine neue Verifikations-E-Mail."""
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                # Get the most recent unverified user for this email
                user = CustomUser.objects.filter(email=email, email_verified=False).order_by('-date_joined').first()
                
                if not user:
                    raise CustomUser.DoesNotExist
                
                # Prüfe ob seit letzter E-Mail genug Zeit vergangen ist (5 Minuten)
                if user.email_verification_sent_at:
                    time_since_last = timezone.now() - user.email_verification_sent_at
                    if time_since_last < timedelta(minutes=5):
                        remaining_minutes = 5 - int(time_since_last.total_seconds() / 60)
                        messages.warning(request, 
                            f'Bitte warten Sie noch {remaining_minutes} Minuten, '
                            'bevor Sie eine neue E-Mail anfordern.')
                        return render(request, 'accounts/resend_verification.html')
                
                # Sende neue Verifikations-E-Mail
                if send_verification_email(user, request):
                    messages.success(request, 
                        'Eine neue Bestätigungs-E-Mail wurde gesendet. '
                        'Bitte prüfen Sie Ihr Postfach.')
                else:
                    messages.error(request, 
                        'Fehler beim Senden der E-Mail. Bitte versuchen Sie es später erneut.')
                        
            except CustomUser.DoesNotExist:
                messages.error(request, 
                    'Keine unverifizierte E-Mail-Adresse gefunden oder E-Mail bereits bestätigt.')
            except CustomUser.MultipleObjectsReturned:
                # This shouldn't happen with our new logic, but adding as safety net
                messages.error(request, 
                    'Es gibt ein Problem mit Ihrem Konto. Bitte wenden Sie sich an den Support.')
    
    return render(request, 'accounts/resend_verification.html')
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db import models
import json

@login_required
@require_http_methods(["POST"])  
def update_content_simple(request):
    """Vereinfachte Content-Update View"""
    try:
        content_id = request.POST.get('content_id')
        page = request.POST.get('page')
        content_key = request.POST.get('content_key', '')
        content_type = request.POST.get('content_type', 'text')
        title = request.POST.get('title', '')
        text_content = request.POST.get('text_content', '')
        html_content = request.POST.get('html_content', '')
        sort_order = request.POST.get('sort_order', 1)
        is_active = request.POST.get('is_active') == 'on'
        
        if not page:
            return JsonResponse({'success': False, 'error': 'Seite ist erforderlich'})
            
        if not content_key.strip():
            return JsonResponse({'success': False, 'error': 'Content-Schlüssel ist erforderlich'})
        
        # Import the model here to avoid circular imports
        from accounts.models import EditableContent
        
        if content_id:
            # Update existing content
            content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        else:
            # Create new content
            try:
                sort_order = int(sort_order)
            except (ValueError, TypeError):
                sort_order = 1
                
            content = EditableContent.objects.create(
                user=request.user,
                page=page,
                content_key=content_key,
                content_type=content_type,
                sort_order=sort_order
            )
        
        # Update fields
        content.content_key = content_key
        content.content_type = content_type
        content.title = title
        content.text_content = text_content
        content.html_content = html_content
        content.sort_order = int(sort_order) if str(sort_order).isdigit() else 1
        content.is_active = is_active
        
        content.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Inhalt erfolgreich gespeichert',
            'content_id': content.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_content_simple(request):
    """Vereinfachte Content-Delete View"""
    try:
        from accounts.models import EditableContent
        
        content_id = request.POST.get('content_id')
        if not content_id:
            return JsonResponse({'success': False, 'error': 'Content-ID ist erforderlich'})
            
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        content.delete()
        
        return JsonResponse({'success': True, 'message': 'Inhalt erfolgreich gelöscht'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_content_simple(request, content_id):
    """Vereinfachte Content-Get View"""
    try:
        from accounts.models import EditableContent
        
        content = get_object_or_404(EditableContent, id=content_id, user=request.user)
        
        return JsonResponse({
            'success': True,
            'content': {
                'id': content.id,
                'page': content.page,
                'content_key': content.content_key or '',
                'content_type': content.content_type,
                'title': content.title or '',
                'text_content': content.text_content or '',
                'html_content': content.html_content or '',
                'sort_order': content.sort_order,
                'is_active': content.is_active,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def generate_ai_content_simple(request):
    """Vereinfachte AI Content Generation"""
    try:
        prompt = request.POST.get('prompt', '')
        page = request.POST.get('page', 'startseite')
        content_type = request.POST.get('content_type', 'ai_generated')
        
        if not prompt.strip():
            return JsonResponse({'success': False, 'error': 'Prompt ist erforderlich'})
        
        # Try to import AI service
        try:
            from naturmacher.services.ai_service import generate_html_content
            
            # Generate content with AI
            result = generate_html_content(prompt, page=page)
            
            if result and isinstance(result, dict):
                return JsonResponse({
                    'success': True,
                    'text_content': result.get('text_content', ''),
                    'html_content': result.get('html_content', ''),
                    'message': 'KI-Inhalt erfolgreich generiert'
                })
            else:
                return JsonResponse({'success': False, 'error': 'KI-Service lieferte kein Ergebnis'})
                
        except ImportError:
            return JsonResponse({'success': False, 'error': 'KI-Service nicht verfügbar'})
        except Exception as ai_error:
            return JsonResponse({'success': False, 'error': f'KI-Fehler: {str(ai_error)}'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Import visual editor views
from .views_visual_editor import (
    visual_editor,
    save_visual_changes,
    publish_visual_changes,
    get_page_content,
    clone_element,
    get_element_styles,
    save_element_style,
    preview_page,
    export_page_changes,
    import_page_changes
)

# Import site discovery views
from .views_site_discovery import (
    discover_site_structure,
    get_page_info,
    create_custom_page
)
