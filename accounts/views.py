from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
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