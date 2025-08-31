from django.shortcuts import redirect
from django.urls import reverse
from django.http import Http404
from accounts.models import AppPermission

class PublicAppRedirectMiddleware:
    """
    Middleware, das nicht angemeldete Benutzer von App-URLs zu den entsprechenden Info-Seiten weiterleitet
    Nur für freigegebene Apps
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # App-Namen zu URL-Pfaden mapping (keys müssen mit AppPermission.app_name übereinstimmen)
        self.app_redirects = {
            'todos': ['todos/'],
            'organisation': ['organization/'],  # URL ist organization, aber app_name ist organisation
            'videos': ['videos/'],
            'streamrec': ['streamrec/'],
            'chat': ['chat/'],
            'shopify': ['shopify/'],
            'bilder': ['images/'],
            'mail': ['mail/'],
            'schulungen': ['schulungen/'],
            'somi_plan': ['somi-plan/'],
            'loomads': ['loomads/'],
            'promptpro': ['promptpro/'],
        }

    def __call__(self, request):
        # Prüfe nur bei nicht angemeldeten Benutzern
        if not request.user.is_authenticated:
            path = request.path_info.lstrip('/')
            
            # Prüfe ob der Pfad zu einer App gehört
            for app_name, url_patterns in self.app_redirects.items():
                for pattern in url_patterns:
                    if path.startswith(pattern):
                        # Prüfe ob die App freigegeben ist
                        try:
                            permission = AppPermission.objects.get(app_name=app_name, is_active=True)
                            # Nur weiterleiten wenn App für anonymous oder authenticated freigegeben ist
                            if permission.access_level in ['anonymous', 'authenticated'] and not permission.hide_in_frontend:
                                # Weiterleitung zur App-Info-Seite
                                return redirect('public_app_info', app_name=app_name)
                        except AppPermission.DoesNotExist:
                            # App nicht freigegeben - keine Weiterleitung
                            pass
                        break
        
        response = self.get_response(request)
        return response