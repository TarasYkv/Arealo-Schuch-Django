from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AmpelCategoryForm, CategoryKeywordForm, KeywordBulkForm, ApiKeyForm
from .models import CustomUser, AmpelCategory, CategoryKeyword
from naturmacher.models import APIBalance


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
    return render(request, 'accounts/manage_api_keys.html', {'form': form})


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
    """Zeigt die neue API-Einstellungsseite an"""
    return render(request, 'accounts/api_einstellungen.html')


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
        if provider_key == 'openai' and request.user.openai_api_key:
            masked_api_key = request.user.openai_api_key[:4] + "*" * (len(request.user.openai_api_key) - 8) + request.user.openai_api_key[-4:]
        elif provider_key == 'anthropic' and request.user.anthropic_api_key:
            masked_api_key = request.user.anthropic_api_key[:4] + "*" * (len(request.user.anthropic_api_key) - 8) + request.user.anthropic_api_key[-4:]

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
    # TODO: Lade echte Statistiken aus der Datenbank
    # Für jetzt geben wir Mock-Daten zurück
    mock_stats = {
        'success': True,
        'period': 'Letzten 30 Tage',
        'total_cost': 12.45,
        'stats': {
            'openai': {
                'requests': 150,
                'cost': 8.20,
                'tokens': 45000
            },
            'anthropic': {
                'requests': 75,
                'cost': 3.50,
                'tokens': 20000
            },
            'google': {
                'requests': 25,
                'cost': 0.75,
                'tokens': 8000
            },
            'youtube': {
                'requests': 10,
                'cost': 0.00,
                'tokens': 0
            }
        }
    }
    
    return JsonResponse(mock_stats)