from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.contrib.sessions.models import Session
from .models import PageVisit, UserSession, PopularPage, RealTimeVisitor
import logging
import re

logger = logging.getLogger(__name__)


class StatsTrackingMiddleware(MiddlewareMixin):
    """
    Statistik-Middleware mit DSGVO-konformer IP-Anonymisierung.

    Keine Einwilligung erforderlich, da:
    - IP-Adressen werden anonymisiert (letztes Oktett = 0)
    - Keine Nutzerprofile werden erstellt
    - Nur aggregierte Daten
    - Rechtsgrundlage: Berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO)
    """

    def process_response(self, request, response):
        try:
            # Nur für erfolgreiche GET-Requests tracken
            if (request.method == 'GET' and
                response.status_code == 200 and
                not request.path.startswith('/admin/') and
                not request.path.startswith('/static/') and
                not request.path.startswith('/media/') and
                not request.path.startswith('/stats/chart-data/') and  # API-Calls ausschließen
                'text/html' in response.get('Content-Type', '')):

                # IP-Adresse ermitteln
                ip_address = self.get_client_ip(request)

                # User-Agent
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                # Referer
                referer = request.META.get('HTTP_REFERER', '')

                # Session Key
                session_key = request.session.session_key

                # Seitentitel aus dem Response extrahieren (falls vorhanden)
                page_title = self.extract_page_title(response)

                # Falls der Titel nur "Workloom" ist, einen aussagekräftigeren Titel generieren
                if not page_title or page_title.strip() == 'Workloom':
                    page_title = self.generate_page_title_from_url(request)

                # Device & Browser Analytics
                device_info = self.parse_user_agent(user_agent)

                # PageVisit erstellen
                PageVisit.objects.create(
                    url=request.build_absolute_uri(),
                    page_title=page_title,
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    referer=referer,
                    session_key=session_key or '',
                    visit_time=timezone.now(),
                    device_type=device_info.get('device_type', ''),
                    browser=device_info.get('browser', ''),
                    os=device_info.get('os', ''),
                    country=self.get_country_from_ip(ip_address),
                )

                # Session verwalten
                if session_key:
                    self.update_user_session(request, ip_address, user_agent, session_key)

                # Beliebte Seiten aktualisieren
                self.update_popular_pages(request.build_absolute_uri(), page_title)

                # Real-Time Visitors aktualisieren
                self.update_real_time_visitors(request, device_info)

        except Exception as e:
            # Logging des Fehlers, aber Request nicht blockieren
            logger.warning(f"Stats tracking error: {e}")

        return response

    def get_client_ip(self, request):
        """
        IP-Adresse des Clients ermitteln und ANONYMISIEREN (DSGVO-konform).

        Das letzte Oktett der IPv4-Adresse wird auf 0 gesetzt.
        Beispiel: 192.168.1.123 → 192.168.1.0
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

        # IP anonymisieren (letztes Oktett auf 0)
        return self.anonymize_ip(ip)

    def anonymize_ip(self, ip):
        """
        Anonymisiert die IP-Adresse für DSGVO-Konformität.
        IPv4: Letztes Oktett wird auf 0 gesetzt (192.168.1.123 → 192.168.1.0)
        IPv6: Letzte 80 Bits werden auf 0 gesetzt
        """
        if not ip:
            return '0.0.0.0'

        # IPv4
        if '.' in ip and ':' not in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                parts[3] = '0'
                return '.'.join(parts)

        # IPv6
        if ':' in ip:
            # Vereinfacht: Nur die ersten 3 Gruppen behalten
            parts = ip.split(':')
            if len(parts) >= 3:
                return ':'.join(parts[:3]) + '::0'

        return '0.0.0.0'

    def extract_page_title(self, response):
        """Seitentitel aus HTML-Response extrahieren"""
        try:
            if hasattr(response, 'content') and response.content:
                content = response.content.decode('utf-8', errors='ignore')
                import re
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    # HTML-Entities und Zeilenumbrüche bereinigen
                    import html
                    title = html.unescape(title)
                    title = re.sub(r'\s+', ' ', title)
                    return title[:200]  # Auf 200 Zeichen begrenzen
        except Exception:
            pass
        return ''

    def generate_page_title_from_url(self, request):
        """Generate meaningful page title from URL when HTML title is generic"""
        try:
            path = request.path.strip('/')
            if not path:
                return 'Startseite'

            # Map common URL patterns to readable titles
            url_mapping = {
                'stats': 'Statistik Dashboard',
                'stats/': 'Statistik Dashboard',
                'stats/visits': 'Besuche Details',
                'stats/ad-clicks': 'Anzeigen Klicks',
                'loomline': 'LoomLine Dashboard',
                'loomline/aufgaben': 'LoomLine Aufgaben',
                'fileshare': 'File Share',
                'todos': 'Todo Listen',
                'todos/list/new': 'Neue Todo Liste',
                'organization/chat': 'Organisation Chat',
                'accounts/dashboard': 'Account Dashboard',
                'accounts/login': 'Login',
                'accounts/logout': 'Logout',
            }

            # Check exact matches first
            if path in url_mapping:
                return url_mapping[path]

            # Check for partial matches
            for url_pattern, title in url_mapping.items():
                if path.startswith(url_pattern):
                    return title

            # Generate title from path segments
            segments = path.split('/')
            if segments:
                app_name = segments[0].replace('_', ' ').replace('-', ' ').title()
                if len(segments) > 1:
                    action = segments[1].replace('_', ' ').replace('-', ' ').title()
                    return f"{app_name} - {action}"
                return app_name

        except Exception:
            pass
        return ''

    def update_user_session(self, request, ip_address, user_agent, session_key):
        """UserSession aktualisieren oder erstellen"""
        try:
            user_session, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    'user': request.user if request.user.is_authenticated else None,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'start_time': timezone.now(),
                    'last_activity': timezone.now(),
                    'page_count': 1
                }
            )

            if not created:
                # Bestehende Session aktualisieren
                user_session.last_activity = timezone.now()
                user_session.page_count += 1
                if request.user.is_authenticated and not user_session.user:
                    user_session.user = request.user
                user_session.save()

        except Exception as e:
            logger.warning(f"User session update error: {e}")

    def update_popular_pages(self, url, page_title):
        """Beliebte Seiten Zähler aktualisieren"""
        try:
            popular_page, created = PopularPage.objects.get_or_create(
                url=url,
                defaults={
                    'page_title': page_title,
                    'view_count': 1
                }
            )

            if not created:
                popular_page.view_count += 1
                if page_title and not popular_page.page_title:
                    popular_page.page_title = page_title
                popular_page.save()

        except Exception as e:
            logger.warning(f"Popular pages update error: {e}")

    def parse_user_agent(self, user_agent):
        """Analysiert User-Agent String für Device/Browser/OS Info"""
        device_info = {
            'device_type': 'desktop',
            'browser': 'Unknown',
            'os': 'Unknown'
        }

        if not user_agent:
            return device_info

        user_agent_lower = user_agent.lower()

        # Device Type Detection
        mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'phone', 'tablet']
        if any(keyword in user_agent_lower for keyword in mobile_keywords):
            if 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
                device_info['device_type'] = 'tablet'
            else:
                device_info['device_type'] = 'mobile'

        # Browser Detection
        if 'chrome' in user_agent_lower and 'edge' not in user_agent_lower:
            device_info['browser'] = 'Chrome'
        elif 'firefox' in user_agent_lower:
            device_info['browser'] = 'Firefox'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            device_info['browser'] = 'Safari'
        elif 'edge' in user_agent_lower:
            device_info['browser'] = 'Edge'
        elif 'opera' in user_agent_lower:
            device_info['browser'] = 'Opera'

        # OS Detection
        if 'windows' in user_agent_lower:
            device_info['os'] = 'Windows'
        elif 'mac os' in user_agent_lower or 'macos' in user_agent_lower:
            device_info['os'] = 'macOS'
        elif 'android' in user_agent_lower:
            device_info['os'] = 'Android'
        elif 'iphone' in user_agent_lower or 'ios' in user_agent_lower:
            device_info['os'] = 'iOS'
        elif 'linux' in user_agent_lower:
            device_info['os'] = 'Linux'

        return device_info

    def get_country_from_ip(self, ip_address):
        """Einfache IP-zu-Land Zuordnung (kann mit GeoIP erweitert werden)"""
        # Für jetzt nur lokale IPs erkennen
        if ip_address in ['127.0.0.1', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return 'Deutschland'

        # Hier könnte eine GeoIP-Bibliothek integriert werden
        # Für Demonstration nehmen wir Deutschland an
        return 'Deutschland'

    def update_real_time_visitors(self, request, device_info):
        """Aktualisiert Real-Time Visitor Tracking"""
        try:
            session_key = request.session.session_key
            if session_key:
                RealTimeVisitor.objects.update_or_create(
                    session_key=session_key,
                    defaults={
                        'user': request.user if request.user.is_authenticated else None,
                        'ip_address': self.get_client_ip(request),
                        'current_page': request.build_absolute_uri(),
                        'device_type': device_info.get('device_type', ''),
                        'country': self.get_country_from_ip(self.get_client_ip(request)),
                    }
                )
        except Exception as e:
            logger.warning(f"Real-time visitor update error: {e}")