from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AmpelCategoryForm, CategoryKeywordForm, KeywordBulkForm
from .models import CustomUser, AmpelCategory, CategoryKeyword


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
    return render(request, 'accounts/api_settings.html')


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
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Einfacher Test-Call zu Models-Endpoint
        response = client.models.list()
        if response and hasattr(response, 'data'):
            return True, "API-Schlüssel ist gültig"
        else:
            return False, "Ungültige API-Antwort"
    except Exception as e:
        error_msg = str(e)
        if "Incorrect API key" in error_msg or "invalid api key" in error_msg.lower():
            return False, "Ungültiger API-Schlüssel"
        elif "exceeded your current quota" in error_msg.lower():
            return True, "API-Schlüssel gültig (Quota überschritten)"
        else:
            return False, f"API-Fehler: {error_msg}"


def test_anthropic_key(api_key):
    """Testet Anthropic API-Schlüssel"""
    try:
        import requests
        
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        # Test mit einer minimalen Nachricht
        data = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 10,
            'messages': [
                {'role': 'user', 'content': 'Hi'}
            ]
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "API-Schlüssel ist gültig"
        elif response.status_code == 401:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        else:
            return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


def test_google_key(api_key):
    """Testet Google AI API-Schlüssel"""
    try:
        import requests
        
        # Test mit Gemini-API
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'models' in data:
                return True, "API-Schlüssel ist gültig"
            else:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 400:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 403:
            return False, "API-Schlüssel ohne Berechtigung"
        else:
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
    # TODO: Implementierung für API-Kontostände aus der Datenbank
    # Für jetzt geben wir Mock-Daten zurück
    mock_balances = {
        'openai': {
            'balance': 25.50,
            'threshold': 5.00,
            'currency': 'USD',
            'masked_api_key': 'Nicht konfiguriert'
        },
        'anthropic': {
            'balance': 15.75,
            'threshold': 3.00,
            'currency': 'USD',
            'masked_api_key': 'Nicht konfiguriert'
        },
        'google': {
            'balance': 10.00,
            'threshold': 2.00,
            'currency': 'USD',
            'masked_api_key': 'Nicht konfiguriert'
        },
        'youtube': {
            'balance': 9500,
            'threshold': 1000,
            'currency': 'QUOTA',
            'masked_api_key': 'Nicht konfiguriert'
        }
    }
    
    return JsonResponse({
        'success': True,
        'balances': mock_balances
    })


@login_required
@require_http_methods(["POST"])
def update_api_balance(request):
    """Aktualisiert einen API-Kontostand"""
    provider = request.POST.get('provider')
    api_key = request.POST.get('api_key', '').strip()
    balance = request.POST.get('balance')
    threshold = request.POST.get('threshold')
    currency = request.POST.get('currency', 'USD')
    
    if not provider:
        return JsonResponse({'success': False, 'error': 'Provider ist erforderlich'})
    
    # TODO: Speichere die Daten in der Datenbank
    # Für jetzt geben wir eine Erfolgs-Antwort zurück
    masked_key = 'Nicht konfiguriert'
    if api_key:
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"{api_key[:4]}..."
    
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
    
    # TODO: Entferne den API-Schlüssel aus der Datenbank
    # Für jetzt geben wir eine Erfolgs-Antwort zurück
    
    return JsonResponse({
        'success': True,
        'message': f'API-Schlüssel für {provider} wurde entfernt'
    })


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