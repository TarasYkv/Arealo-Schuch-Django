# core/context_processors.py
"""
SEO Context Processor
Stellt SEO-relevante Informationen für alle Templates bereit
"""

from django.conf import settings


def seo_defaults(request):
    """
    Fügt Standard-SEO-Informationen zum Template-Context hinzu
    """
    # Basis-URL für kanonische Links und Open Graph
    protocol = 'https' if request.is_secure() else 'http'
    current_url = f"{protocol}://{request.get_host()}{request.path}"

    # Default SEO-Werte (können in Templates überschrieben werden)
    seo_context = {
        'seo': {
            'site_name': 'WorkLoom',
            'site_domain': settings.SITE_DOMAIN,
            'site_protocol': getattr(settings, 'SITE_PROTOCOL', 'https'),
            'canonical_url': current_url,
            'default_title': 'WorkLoom - Digitale Tools für effizientes Arbeiten',
            'default_description': 'WorkLoom bietet professionelle digitale Tools und Lösungen für Beleuchtungsplanung, Projektmanagement und mehr. Effizient, sicher und benutzerfreundlich.',
            'default_keywords': 'WorkLoom, Beleuchtungsrechner, Projektmanagement, digitale Tools, Beleuchtungsplanung, DIN EN 13201',
            'default_image': f"{protocol}://{request.get_host()}/media/workloom_icon.png",
            'og_type': 'website',
            'twitter_card': 'summary_large_image',
            'twitter_site': '@workloom',  # Anpassen wenn vorhanden
            'language': 'de-DE',
            'robots': 'index, follow',
        }
    }

    return seo_context
