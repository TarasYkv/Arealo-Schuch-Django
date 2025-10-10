# Schuch/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

# GEÄNDERT: Wir importieren jetzt aus unserer neuen 'core'-App
from core import views as core_views
from videos import views as video_views
from core.sitemaps import sitemaps

urlpatterns = [
    # GEÄNDERT: Der Pfad verweist jetzt auf die View in der core-App
    path('', core_views.startseite_ansicht, name='startseite'),

    # Public App Info Pages (accessible without login)
    path('apps/', core_views.public_app_list, name='public_app_list'),
    path('app/<str:app_name>/', core_views.public_app_info, name='public_app_info'),

    # Schuch Tools
    path('beleuchtungsrechner/', core_views.beleuchtungsrechner, name='beleuchtungsrechner'),
    path('din-en-13201/', include('lighting_classification.urls')),
    path('licht/', include('lighting_tools.urls')),

    # Legal pages
    path('impressum/', core_views.impressum_view, name='impressum'),
    path('agb/', core_views.agb_view, name='agb'),
    path('datenschutz/', core_views.datenschutz_view, name='datenschutz'),

    # Der Rest bleibt unverändert
    path('accounts/', include('accounts.urls')),
    path('rechner/', include('amortization_calculator.urls')),
    path('sportplatz/', include('sportplatzApp.urls')),
    path('pdf-tool/', include('pdf_sucher.urls')),
    path('schulungen/', include('naturmacher.urls')),
    path('todos/', include('todos.urls')),
    # Chat wurde zu Organization verschoben
    path('chat/', core_views.redirect_to_organization_chat, name='chat_redirect'),
    path('shopify/', include('shopify_manager.urls')),
    path('images/', include('image_editor.urls')),
    path('bug-report/', include('bug_report.urls')),
    path('organization/', include('organization.urls')),
    # Chat namespace redirect for backward compatibility
    path('chat/', include('organization.urls', namespace='chat')),
    path('videos/', include('videos.urls', namespace='videos')),
    path('promptpro/', include('promptpro.urls', namespace='promptpro')),
    # Public video access shortcut
    path('v/<uuid:unique_id>/', video_views.video_view, name='public_video_view'),
    path('payments/', include('payments.urls')),
    path('mail/', include('mail_app.urls')),
    path('email-templates/', include('email_templates.urls')),
    path('somi-plan/', include('somi_plan.urls')),
    path('makeads/', include('makeads.urls')),
    path('streamrec/', include('streamrec.urls', namespace='streamrec')),
    path('superconfig/', include('superconfig.urls')),
    path('loomads/', include('loomads.urls')),
    path('loomline/', include('loomline.urls')),
    path('fileshare/', include('fileshare.urls')),
    path('stats/', include('stats.urls')),
    path('page/<str:page_name>/', core_views.dynamic_page_view, name='dynamic_page'),

    # SEO: Sitemap und robots.txt
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', core_views.robots_txt, name='robots_txt'),

    path('admin/', admin.site.urls),
]

# Static und Media files für Development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
