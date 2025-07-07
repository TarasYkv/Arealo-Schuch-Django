"""
Canva API Service für die Integration mit Canva
Ermöglicht das Laden von Designs und Assets aus Canva
"""

import requests
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
import io
from PIL import Image


class CanvaAPIService:
    """Service-Klasse für die Canva API Integration"""
    
    BASE_URL = "https://api.canva.com/rest/v1"
    OAUTH_URL = "https://api.canva.com/rest/v1/oauth"
    
    def __init__(self, user):
        self.user = user
        self.settings = None
        self._load_user_settings()
    
    def _load_user_settings(self):
        """Lädt die Canva-Einstellungen des Benutzers"""
        try:
            from .models import CanvaAPISettings
            self.settings = CanvaAPISettings.objects.get(user=self.user)
        except CanvaAPISettings.DoesNotExist:
            from .models import CanvaAPISettings
            self.settings = CanvaAPISettings.objects.create(user=self.user)
    
    def get_authorization_url(self, redirect_uri):
        """Erstellt die OAuth-Autorisierungs-URL für Canva"""
        if not self.settings.has_valid_credentials():
            raise ValueError("Canva Client ID und Secret sind erforderlich")
        
        params = {
            'client_id': self.settings.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'design:read asset:read folder:read brand_template:read',
            'state': f'user_{self.user.id}'  # Für Sicherheit
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.OAUTH_URL}/authorize?{query_string}"
    
    def exchange_code_for_token(self, code, redirect_uri):
        """Tauscht Authorization Code gegen Access Token"""
        if not self.settings.has_valid_credentials():
            raise ValueError("Canva Client ID und Secret sind erforderlich")
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.settings.client_id,
            'client_secret': self.settings.client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        response = requests.post(f"{self.OAUTH_URL}/token", data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Speichere Token-Daten
            self.settings.access_token = token_data.get('access_token')
            self.settings.refresh_token = token_data.get('refresh_token')
            
            # Berechne Ablaufzeit
            expires_in = token_data.get('expires_in', 3600)  # Standard: 1 Stunde
            self.settings.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
            
            self.settings.save()
            return True
        else:
            error = response.json() if response.content else {'error': 'Unknown error'}
            raise Exception(f"Token-Exchange fehlgeschlagen: {error}")
    
    def refresh_access_token(self):
        """Erneuert den Access Token mit dem Refresh Token"""
        if not self.settings.refresh_token:
            raise ValueError("Kein Refresh Token verfügbar")
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.settings.client_id,
            'client_secret': self.settings.client_secret,
            'refresh_token': self.settings.refresh_token
        }
        
        response = requests.post(f"{self.OAUTH_URL}/token", data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            self.settings.access_token = token_data.get('access_token')
            if 'refresh_token' in token_data:
                self.settings.refresh_token = token_data.get('refresh_token')
            
            expires_in = token_data.get('expires_in', 3600)
            self.settings.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
            
            self.settings.save()
            return True
        else:
            raise Exception("Token-Refresh fehlgeschlagen")
    
    def _get_headers(self):
        """Erstellt die HTTP-Headers für API-Requests"""
        if not self.settings.has_access_token():
            raise ValueError("Kein Access Token verfügbar. OAuth-Autorisierung erforderlich.")
        
        # Prüfe Token-Ablauf und erneuere wenn nötig
        if self.settings.is_token_expired():
            self.refresh_access_token()
        
        return {
            'Authorization': f'Bearer {self.settings.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_user_profile(self):
        """Holt das Benutzerprofil von Canva"""
        headers = self._get_headers()
        response = requests.get(f"{self.BASE_URL}/me", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Fehler beim Laden des Profils: {response.status_code}")
    
    def list_designs(self, limit=20, continuation_token=None):
        """Listet die Designs des Benutzers auf"""
        headers = self._get_headers()
        
        params = {'limit': limit}
        if continuation_token:
            params['continuation_token'] = continuation_token
        
        response = requests.get(f"{self.BASE_URL}/designs", headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Fehler beim Laden der Designs: {response.status_code}")
    
    def get_design_details(self, design_id):
        """Holt Details zu einem spezifischen Design"""
        headers = self._get_headers()
        response = requests.get(f"{self.BASE_URL}/designs/{design_id}", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Fehler beim Laden des Designs: {response.status_code}")
    
    def export_design(self, design_id, format='PNG', quality='high'):
        """Exportiert ein Design als Bild"""
        headers = self._get_headers()
        
        export_data = {
            'format': {
                'type': format.upper()
            }
        }
        
        if format.upper() == 'JPG':
            export_data['format']['quality'] = quality
        
        # Starte Export-Job
        response = requests.post(
            f"{self.BASE_URL}/designs/{design_id}/export",
            headers=headers,
            json=export_data
        )
        
        if response.status_code == 202:  # Export started
            job_data = response.json()
            job_id = job_data.get('job', {}).get('id')
            
            if job_id:
                return self._wait_for_export_completion(job_id)
            else:
                raise Exception("Export-Job konnte nicht gestartet werden")
        else:
            raise Exception(f"Export fehlgeschlagen: {response.status_code}")
    
    def _wait_for_export_completion(self, job_id, max_wait=60):
        """Wartet auf die Fertigstellung des Export-Jobs"""
        headers = self._get_headers()
        import time
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = requests.get(f"{self.BASE_URL}/export-jobs/{job_id}", headers=headers)
            
            if response.status_code == 200:
                job_data = response.json()
                status = job_data.get('job', {}).get('status')
                
                if status == 'success':
                    # Download-URLs extrahieren
                    urls = job_data.get('job', {}).get('urls', [])
                    if urls:
                        return urls[0].get('url')  # Erste URL zurückgeben
                    else:
                        raise Exception("Keine Download-URL im Export-Job gefunden")
                
                elif status == 'failed':
                    error = job_data.get('job', {}).get('error', 'Unknown error')
                    raise Exception(f"Export fehlgeschlagen: {error}")
                
                # Status ist 'in_progress', weiter warten
                time.sleep(2)
            else:
                raise Exception(f"Fehler beim Prüfen des Export-Jobs: {response.status_code}")
        
        raise Exception("Export-Timeout erreicht")
    
    def download_image_from_url(self, url):
        """Lädt ein Bild von einer URL herunter und gibt es als ContentFile zurück"""
        response = requests.get(url, stream=True)
        
        if response.status_code == 200:
            # Bild-Daten laden
            image_data = response.content
            
            # PIL Image erstellen für Validierung
            try:
                img = Image.open(io.BytesIO(image_data))
                img.verify()  # Validiere Bild
            except Exception as e:
                raise Exception(f"Ungültiges Bildformat: {e}")
            
            # ContentFile erstellen
            return ContentFile(image_data)
        else:
            raise Exception(f"Fehler beim Herunterladen des Bildes: {response.status_code}")
    
    def import_design_to_project(self, design_id, project_name=None):
        """Importiert ein Canva-Design als neues Bildbearbeitungsprojekt"""
        try:
            # Design-Details holen
            design_details = self.get_design_details(design_id)
            design_title = design_details.get('title', f'Canva Design {design_id}')
            
            # Design exportieren
            download_url = self.export_design(design_id, format='PNG', quality='high')
            
            # Bild herunterladen
            image_file = self.download_image_from_url(download_url)
            
            # Projekt erstellen
            from image_editor.models import ImageProject
            
            project = ImageProject.objects.create(
                user=self.user,
                name=project_name or f'Canva: {design_title}',
                source_type='canva_import',
                original_filename=f'{design_id}.png',
                description=f'Importiert aus Canva Design: {design_title}'
            )
            
            # Bild zum Projekt hinzufügen
            project.original_image.save(
                f'canva_import_{design_id}.png',
                image_file,
                save=True
            )
            
            # Bildabmessungen ermitteln
            try:
                from PIL import Image
                with Image.open(project.original_image) as img:
                    project.original_width = img.width
                    project.original_height = img.height
                    project.save()
            except Exception:
                pass
            
            return project
            
        except Exception as e:
            raise Exception(f"Import fehlgeschlagen: {str(e)}")
    
    def list_folders(self):
        """Listet verfügbare Ordner auf"""
        headers = self._get_headers()
        response = requests.get(f"{self.BASE_URL}/folders", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Fehler beim Laden der Ordner: {response.status_code}")
    
    def list_brand_templates(self):
        """Listet verfügbare Brand Templates auf"""
        headers = self._get_headers()
        response = requests.get(f"{self.BASE_URL}/brand-templates", headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Fehler beim Laden der Brand Templates: {response.status_code}")