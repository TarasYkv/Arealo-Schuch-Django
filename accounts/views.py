from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db import models
import json
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AmpelCategoryForm, CategoryKeywordForm, KeywordBulkForm, ApiKeyForm, CompanyInfoForm, UserProfileForm, CustomPasswordChangeForm, SuperUserManagementForm, BugChatSettingsForm, AppPermissionForm
from .models import CustomUser, AmpelCategory, CategoryKeyword, UserLoginHistory, EditableContent, CustomPage, SEOSettings
from naturmacher.models import APIBalance
from .utils import redirect_with_params


class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'
    success_url = reverse_lazy('accounts:dashboard')


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Ihr Konto wurde erfolgreich erstellt! Sie können sich jetzt einloggen.')
        return response


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
    context = {
        'categories': categories,
        'use_custom_categories': request.user.use_custom_categories,
        'enable_ai_keyword_expansion': request.user.enable_ai_keyword_expansion,
        'dark_mode': request.user.dark_mode,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def manage_api_keys(request):
    if request.method == 'POST':
        form = ApiKeyForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'API Keys erfolgreich gespeichert.')
            return redirect('accounts:manage_api_keys')
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
    return redirect('accounts:manage_api_keys')


@login_required
def neue_api_einstellungen_view(request):
    """Zeigt die neue API-Einstellungsseite mit Canva- und Shopify-Integration an"""
    # Canva-Einstellungen laden oder erstellen
    from naturmacher.models import CanvaAPISettings
    canva_settings, created = CanvaAPISettings.objects.get_or_create(user=request.user)
    
    # Shopify-Stores des Benutzers laden
    from shopify_manager.models import ShopifyStore
    shopify_stores = ShopifyStore.objects.filter(user=request.user, is_active=True)
    
    return render(request, 'accounts/api_einstellungen.html', {
        'canva_settings': canva_settings,
        'shopify_stores': shopify_stores
    })


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


# Separate Profile-Views wurden in company_info_view integriert
# @login_required
# def profile_view(request):
#     """Benutzer-Profil anzeigen und bearbeiten - INTEGRIERT IN COMPANY_INFO_VIEW"""
#     pass

# @login_required
# def change_password_view(request):
#     """Passwort ändern - INTEGRIERT IN COMPANY_INFO_VIEW"""
#     pass


@login_required
def content_editor(request):
    """Editor für anpassbare Inhalte"""
    page = request.GET.get('page', 'startseite')
    
    # Hole existierende Inhalte für diese Seite
    contents = EditableContent.objects.filter(user=request.user, page=page).order_by('sort_order', 'created_at')
    
    # Dynamische Seiten-Choices basierend auf benutzerdefinierten Seiten
    page_choices = CustomPage.get_all_page_choices(request.user)
    
    context = {
        'page': page,
        'contents': contents,
        'page_choices': page_choices,
        'content_type_choices': EditableContent.CONTENT_TYPE_CHOICES,
    }
    return render(request, 'accounts/content_editor.html', context)


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