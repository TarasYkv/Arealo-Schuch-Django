# core/views.py
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from accounts.models import CustomPage

def startseite_ansicht(request):
    """Diese Ansicht rendert nur die Kachel-Übersicht."""
    context = {
        'current_page': 'startseite'
    }
    return render(request, 'core/startseite.html', context)

def dynamic_page_view(request, page_name):
    """Rendert dynamische benutzerdefinierte Seiten"""
    # Check if page exists for this user
    if request.user.is_authenticated:
        try:
            page = CustomPage.objects.get(user=request.user, page_name=page_name, is_active=True)
            context = {
                'current_page': page_name,
                'page_title': page.display_name,
                'page_description': page.description,
            }
            return render(request, 'core/dynamic_page.html', context)
        except CustomPage.DoesNotExist:
            raise Http404("Seite nicht gefunden")
    else:
        raise Http404("Seite nicht verfügbar")

def impressum_view(request):
    """Impressum Seite"""
    context = {
        'page_title': 'Impressum',
    }
    return render(request, 'core/impressum.html', context)

def agb_view(request):
    """AGB Seite"""
    context = {
        'page_title': 'Allgemeine Geschäftsbedingungen',
    }
    return render(request, 'core/agb.html', context)

def datenschutz_view(request):
    """Datenschutzbedingungen Seite"""
    context = {
        'page_title': 'Datenschutzerklärung',
    }
    return render(request, 'core/datenschutz.html', context)