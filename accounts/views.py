from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AmpelCategoryForm, CategoryKeywordForm, KeywordBulkForm, ApiKeyForm, CompanyInfoForm, UserProfileForm, CustomPasswordChangeForm, SuperUserManagementForm, BugChatSettingsForm
from .models import CustomUser, AmpelCategory, CategoryKeyword
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
    
    categories = AmpelCategory.objects.filter(user=request.user)
    context = {
        'categories': categories,
        'use_custom_categories': request.user.use_custom_categories,
        'enable_ai_keyword_expansion': request.user.enable_ai_keyword_expansion,
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
    is_superuser = request.user.is_bug_chat_superuser
    
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
            
        else:
            # Fallback: Alle Formulare initialisieren
            company_form = CompanyInfoForm(instance=request.user)
            profile_form = UserProfileForm(instance=request.user)
            password_form = CustomPasswordChangeForm(request.user)
            bug_chat_form = BugChatSettingsForm(instance=request.user)
            superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
            
    else:
        # GET-Request: Alle Formulare mit aktuellen Daten initialisieren
        company_form = CompanyInfoForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user)
        password_form = CustomPasswordChangeForm(request.user)
        bug_chat_form = BugChatSettingsForm(instance=request.user)
        superuser_form = SuperUserManagementForm(current_user=request.user) if is_superuser else None
    
    return render(request, 'accounts/company_info.html', {
        'company_form': company_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'bug_chat_form': bug_chat_form,
        'superuser_form': superuser_form,
        'active_tab': active_tab,
        'is_superuser': is_superuser,
        'user': request.user,
    })


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


# Separate Profile-Views wurden in company_info_view integriert
# @login_required
# def profile_view(request):
#     """Benutzer-Profil anzeigen und bearbeiten - INTEGRIERT IN COMPANY_INFO_VIEW"""
#     pass

# @login_required
# def change_password_view(request):
#     """Passwort ändern - INTEGRIERT IN COMPANY_INFO_VIEW"""
#     pass