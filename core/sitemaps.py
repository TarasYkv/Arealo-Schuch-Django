# core/sitemaps.py
"""
SEO Sitemaps für WorkLoom
Definiert alle wichtigen URLs für Suchmaschinen
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone


class StaticViewSitemap(Sitemap):
    """Sitemap für statische Seiten (Startseite, Impressum, etc.)"""
    priority = 0.8
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        """Alle öffentlichen statischen Seiten"""
        return [
            'startseite',
            'impressum',
            'agb',
            'datenschutz',
            'public_app_list',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, obj):
        return timezone.now()


class ToolsSitemap(Sitemap):
    """Sitemap für öffentlich zugängliche Tools"""
    priority = 0.9
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        """Alle öffentlichen Tools und Rechner"""
        return [
            'beleuchtungsrechner',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, obj):
        return timezone.now()


class AppInfoSitemap(Sitemap):
    """Sitemap für App-Infoseiten"""
    priority = 0.7
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        """Alle verfügbaren App-Infoseiten"""
        from accounts.models import AppPermission

        return AppPermission.objects.filter(
            is_active=True,
            hide_in_frontend=False
        ).values_list('app_name', flat=True)

    def location(self, item):
        return reverse('public_app_info', args=[item])

    def lastmod(self, obj):
        return timezone.now()


# Sitemaps Dictionary für URL-Konfiguration
sitemaps = {
    'static': StaticViewSitemap,
    'tools': ToolsSitemap,
    'apps': AppInfoSitemap,
}
