# Schuch/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# GEÄNDERT: Wir importieren jetzt aus unserer neuen 'core'-App
from core import views as core_views

urlpatterns = [
    # GEÄNDERT: Der Pfad verweist jetzt auf die View in der core-App
    path('', core_views.startseite_ansicht, name='startseite'),

    # Der Rest bleibt unverändert
    path('accounts/', include('accounts.urls')),
    path('rechner/', include('amortization_calculator.urls')),
    path('sportplatz/', include('sportplatzApp.urls')),
    path('pdf-tool/', include('pdf_sucher.urls')),
    path('admin/', admin.site.urls),
]

# Media files für Development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)