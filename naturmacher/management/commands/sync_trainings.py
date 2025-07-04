import os
import re
from io import StringIO
from django.core.management.base import BaseCommand
from django.conf import settings
from bs4 import BeautifulSoup
from naturmacher.models import Thema, Training
from naturmacher.utils.youtube_search import get_youtube_videos_for_training


class Command(BaseCommand):
    help = 'Synchronisiert Trainings mit Ordnerstruktur (Import + Löschung)'

    def handle(self, *args, **options):
        # Capture output for statistics
        self.stats = {
            'neue_themen': 0,
            'neue_trainings': 0,
            'geloeschte_trainings': 0,
            'geloeschte_themen': 0,
            'aktualisierte_trainings': 0
        }
        
        trainings_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        
        if not os.path.exists(trainings_path):
            return {'error': f'Trainings-Verzeichnis nicht gefunden: {trainings_path}'}
        
        # Count before
        themen_vorher = Thema.objects.count()
        trainings_vorher = Training.objects.count()
        
        # Sammle alle existierenden Ordner und HTML-Dateien
        existing_folders = set()
        existing_files_per_theme = {}
        
        for thema_folder in os.listdir(trainings_path):
            thema_path = os.path.join(trainings_path, thema_folder)
            
            if not os.path.isdir(thema_path):
                continue
                
            existing_folders.add(thema_folder)
            html_files = [f for f in os.listdir(thema_path) if f.endswith('.html')]
            existing_files_per_theme[thema_folder] = set(html_files)
        
        # Sammle alle Titel, die in den Dateien gefunden werden
        found_training_titles = {}  # thema_name -> set of titles
        
        # Import/Update Phase
        for thema_folder in existing_folders:
            thema_path = os.path.join(trainings_path, thema_folder)
            
            # Thema erstellen oder abrufen
            thema_name = thema_folder.replace('1. Web - ', '').replace('2. Web - ', '').replace('3. Web - ', '')
            thema, created = Thema.objects.get_or_create(
                name=thema_name,
                defaults={
                    'beschreibung': f'Trainings zum Thema {thema_name}',
                }
            )
            
            if created:
                self.stats['neue_themen'] += 1
            
            # Set für gefundene Titel initialisieren
            found_training_titles[thema_name] = set()
            
            # HTML-Dateien verarbeiten
            html_files = existing_files_per_theme[thema_folder]
            
            for html_file in html_files:
                html_path = os.path.join(thema_path, html_file)
                
                try:
                    # Trainings-Titel aus Dateiname extrahieren
                    training_titel = self.extract_title_from_filename(html_file)
                    
                    # HTML-Inhalt lesen und parsen
                    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                        html_content = f.read()
                    
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Titel aus HTML extrahieren (falls vorhanden)
                    title_tag = soup.find('title')
                    if title_tag:
                        html_title = title_tag.get_text().strip()
                        html_title = re.sub(r'^[🌟⭐]\s*Schulung\s*\d+:\s*', '', html_title)
                        if html_title:
                            training_titel = html_title
                    
                    # Titel zu gefundenen hinzufügen
                    found_training_titles[thema_name].add(training_titel)
                    
                    # Beschreibung und Inhalt extrahieren
                    beschreibung = self.extract_description(soup)
                    inhalt = self.extract_content(soup)
                    schwierigkeit = self.determine_difficulty(training_titel, inhalt)
                    dauer = self.extract_duration(inhalt)
                    
                    # Training erstellen oder aktualisieren
                    training, created = Training.objects.get_or_create(
                        titel=training_titel,
                        thema=thema,
                        defaults={
                            'beschreibung': beschreibung,
                            'schwierigkeit': schwierigkeit,
                            'dauer_minuten': dauer,
                            'inhalt': inhalt,
                        }
                    )
                    
                    if created:
                        self.stats['neue_trainings'] += 1
                        # Automatisch YouTube-Videos suchen für neue Trainings
                        self.add_youtube_videos(training, thema.name)
                    else:
                        # Training aktualisieren
                        training.beschreibung = beschreibung
                        training.inhalt = inhalt
                        training.schwierigkeit = schwierigkeit
                        training.dauer_minuten = dauer
                        training.save()
                        self.stats['aktualisierte_trainings'] += 1
                        
                        # YouTube-Videos hinzufügen, falls noch keine vorhanden
                        if not training.youtube_links.strip():
                            self.add_youtube_videos(training, thema.name)
                        
                except Exception as e:
                    pass  # Silent error handling for web interface
        
        # Lösch-Phase: Entferne verwaiste Trainings und Themen
        for thema in list(Thema.objects.all()):
            # Prüfe, ob der Thema-Ordner noch existiert
            thema_folder_name = ""
            # Rekonstruiere den erwarteten Ordnernamen basierend auf dem Thema-Namen
            # Dies ist eine Annahme basierend auf der Namenskonvention in create_thema
            # Es wäre besser, wenn Thema-Modell den Ordnernamen speichern würde
            trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
            
            # Finde den Ordner, der zu diesem Thema gehört
            found_thema_folder = None
            for folder in os.listdir(trainings_base_path):
                if os.path.isdir(os.path.join(trainings_base_path, folder)) and thema.name.lower() in folder.lower():
                    found_thema_folder = folder
                    break

            if not found_thema_folder:
                # Thema-Ordner existiert nicht mehr, lösche das Thema und seine Trainings
                print(f"🗑️ Thema-Ordner für '{thema.name}' nicht gefunden. Lösche Thema und zugehörige Trainings.")
                deleted_count = thema.trainings.count()
                self.stats['geloeschte_trainings'] += deleted_count
                thema.delete()
                self.stats['geloeschte_themen'] += 1
            else:
                # Prüfe einzelne Trainings gegen gefundene Titel
                found_titles = found_training_titles.get(thema.name, set())
                
                for training in list(thema.trainings.all()):
                    if training.titel not in found_titles:
                        print(f"🗑️ Training '{training.titel}' in Thema '{thema.name}' nicht mehr im Dateisystem gefunden. Lösche Training.")
                        training.delete()
                        self.stats['geloeschte_trainings'] += 1
        
        # Entferne den Block, der leere Themen löscht
        # empty_themes = Thema.objects.filter(trainings__isnull=True)
        # self.stats['geloeschte_themen'] += empty_themes.count()
        # empty_themes.delete()
        
        # Output für Kommandozeile
        if hasattr(self, 'stdout'):
            message_parts = []
            if self.stats['neue_themen'] > 0:
                message_parts.append(f"{self.stats['neue_themen']} neue Themen")
            if self.stats['neue_trainings'] > 0:
                message_parts.append(f"{self.stats['neue_trainings']} neue Trainings")
            if self.stats['aktualisierte_trainings'] > 0:
                message_parts.append(f"{self.stats['aktualisierte_trainings']} Trainings aktualisiert")
            if self.stats['geloeschte_trainings'] > 0:
                message_parts.append(f"{self.stats['geloeschte_trainings']} Trainings entfernt")
            if self.stats['geloeschte_themen'] > 0:
                message_parts.append(f"{self.stats['geloeschte_themen']} Themen entfernt")
            
            if message_parts:
                self.stdout.write(self.style.SUCCESS("Synchronisation erfolgreich! " + ", ".join(message_parts) + "."))
            else:
                self.stdout.write(self.style.SUCCESS("Alle Trainings sind bereits synchron."))
        
        return self.stats
    
    def extract_title_from_filename(self, filename):
        """Extrahiert den Titel aus dem Dateinamen"""
        title = filename.replace('.docx.html', '').replace('.html', '')
        title = re.sub(r'^Schulung\s*-\s*\d+\.\s*', '', title)
        return title.strip()
    
    def extract_description(self, soup):
        """Extrahiert eine Beschreibung aus den ersten Absätzen"""
        paragraphs = soup.find_all('p')
        description_parts = []
        
        for p in paragraphs[:3]:
            text = p.get_text().strip()
            if text and len(text) > 20:
                description_parts.append(text)
        
        if description_parts:
            return ' '.join(description_parts)[:500]
        
        return "Praktische Schulung für Naturmacher.de"
    
    def extract_content(self, soup):
        """Extrahiert den vollständigen Inhalt ohne Style-Tags"""
        for script in soup(["script", "style"]):
            script.decompose()
        
        body = soup.find('body')
        if body:
            return body.get_text().strip()
        
        return soup.get_text().strip()
    
    def determine_difficulty(self, titel, inhalt):
        """Bestimmt die Schwierigkeit basierend auf Titel und Inhalt"""
        titel_lower = titel.lower()
        
        if any(keyword in titel_lower for keyword in ['grundlagen', 'einführung', 'basics', 'start']):
            return 'anfaenger'
        
        if any(keyword in titel_lower for keyword in ['fortgeschritten', 'advanced', 'roi', 'analytics', 'automation']):
            return 'fortgeschritten'
        
        if any(keyword in titel_lower for keyword in ['experte', 'expert', 'skalierung', 'international']):
            return 'experte'
        
        return 'anfaenger'
    
    def extract_duration(self, inhalt):
        """Extrahiert die Dauer aus dem Inhalt oder verwendet Standard-Werte"""
        duration_match = re.search(r'(\d+)\s*(?:stunde|hour|min)', inhalt.lower())
        if duration_match:
            duration = int(duration_match.group(1))
            if 'stunde' in inhalt.lower() or 'hour' in inhalt.lower():
                return duration * 60
            return duration
        
        return 120
    
    def add_youtube_videos(self, training, thema_name):
        """Fügt automatisch YouTube-Videos zu einem Training hinzu"""
        try:
            # Suche nach passenden YouTube-Videos
            youtube_urls = get_youtube_videos_for_training(
                training_title=training.titel,
                training_description=training.beschreibung,
                thema_name=thema_name,
                user=None  # Management-Commands verwenden Fallback zu Web-Scraping
            )
            
            if youtube_urls:
                # Videos als mehrzeiligen String speichern
                training.youtube_links = '\n'.join(youtube_urls)
                training.save()
                
        except Exception as e:
            pass  # Silent error handling for web interface