import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from bs4 import BeautifulSoup
from naturmacher.models import Thema, Training


class Command(BaseCommand):
    help = 'Importiert Trainings aus den Ordnern im media/naturmacher/trainings Verzeichnis'

    def handle(self, *args, **options):
        trainings_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        
        if not os.path.exists(trainings_path):
            self.stdout.write(self.style.ERROR(f'Trainings-Verzeichnis nicht gefunden: {trainings_path}'))
            return
        
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
        
        # Import/Update Phase
        for thema_folder in existing_folders:
            thema_path = os.path.join(trainings_path, thema_folder)
            
            if not os.path.isdir(thema_path):
                continue
                
            self.stdout.write(f'Verarbeite Thema: {thema_folder}')
            
            # Thema erstellen oder abrufen
            thema_name = thema_folder.replace('1. Web - ', '').replace('2. Web - ', '')
            thema, created = Thema.objects.get_or_create(
                name=thema_name,
                defaults={
                    'beschreibung': f'Trainings zum Thema {thema_name}',
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Thema "{thema_name}" erstellt'))
            else:
                self.stdout.write(f'Thema "{thema_name}" bereits vorhanden')
            
            # Inhaltsverzeichnis lesen
            inhaltsverzeichnis_path = os.path.join(thema_path, 'inhaltsverzeichnis.txt')
            training_titles = []
            
            if os.path.exists(inhaltsverzeichnis_path):
                with open(inhaltsverzeichnis_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extrahiere Trainings-Titel aus dem Inhaltsverzeichnis
                    lines = content.split('\n')
                    for line in lines:
                        # Suche nach Zeilen mit Nummern am Anfang
                        match = re.match(r'^\d+\.\s*(.+)', line.strip())
                        if match:
                            training_titles.append(match.group(1))
            
            # HTML-Dateien verarbeiten
            html_files = [f for f in os.listdir(thema_path) if f.endswith('.html')]
            
            for html_file in html_files:
                html_path = os.path.join(thema_path, html_file)
                
                # Trainings-Titel aus Dateiname extrahieren
                training_titel = self.extract_title_from_filename(html_file)
                
                # HTML-Inhalt lesen und parsen
                try:
                    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                        html_content = f.read()
                    
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Titel aus HTML extrahieren (falls vorhanden)
                    title_tag = soup.find('title')
                    if title_tag:
                        html_title = title_tag.get_text().strip()
                        # Entferne Emojis und "Schulung X:" vom Anfang
                        html_title = re.sub(r'^[🌟⭐]\s*Schulung\s*\d+:\s*', '', html_title)
                        if html_title:
                            training_titel = html_title
                    
                    # Beschreibung aus den ersten Absätzen extrahieren
                    beschreibung = self.extract_description(soup)
                    
                    # Vollständigen Inhalt extrahieren (ohne Style-Tags)
                    inhalt = self.extract_content(soup)
                    
                    # Schwierigkeit basierend auf Titel/Inhalt bestimmen
                    schwierigkeit = self.determine_difficulty(training_titel, inhalt)
                    
                    # Dauer extrahieren (Standard: 120 Minuten)
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
                        self.stdout.write(self.style.SUCCESS(f'  Training erstellt'))
                    else:
                        # Training aktualisieren
                        training.beschreibung = beschreibung
                        training.inhalt = inhalt
                        training.schwierigkeit = schwierigkeit
                        training.dauer_minuten = dauer
                        training.save()
                        self.stdout.write(f'  Training aktualisiert')
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Fehler bei {html_file}'))
        
        # Lösch-Phase: Entferne verwaiste Trainings und Themen
        deleted_trainings = 0
        deleted_themes = 0
        
        # 1. Lösche Trainings, deren HTML-Dateien nicht mehr existieren
        for thema in Thema.objects.all():
            thema_folder_candidates = [f for f in existing_folders if thema.name in f or f.endswith(thema.name)]
            
            if not thema_folder_candidates:
                # Thema-Ordner existiert nicht mehr - lösche alle Trainings
                deleted_count = thema.trainings.count()
                thema.trainings.all().delete()
                deleted_trainings += deleted_count
                
                # Lösche auch das leere Thema
                thema.delete()
                deleted_themes += 1
                self.stdout.write(f'Thema "{thema.name}" gelöscht (Ordner nicht mehr vorhanden)')
            else:
                # Prüfe einzelne Trainings
                thema_folder = thema_folder_candidates[0]
                existing_files = existing_files_per_theme.get(thema_folder, set())
                
                for training in thema.trainings.all():
                    # Suche nach entsprechender HTML-Datei
                    training_file_found = False
                    for html_file in existing_files:
                        extracted_title = self.extract_title_from_filename(html_file)
                        if extracted_title == training.titel or training.titel in html_file:
                            training_file_found = True
                            break
                    
                    if not training_file_found:
                        training.delete()
                        deleted_trainings += 1
                        self.stdout.write(f'Training "{training.titel}" gelöscht (Datei nicht mehr vorhanden)')
        
        # 2. Lösche Themen ohne Trainings
        empty_themes = Thema.objects.filter(trainings__isnull=True)
        for empty_theme in empty_themes:
            empty_theme.delete()
            deleted_themes += 1
            self.stdout.write(f'Leeres Thema "{empty_theme.name}" gelöscht')
        
        # Erfolgsmeldung mit Statistik
        if deleted_trainings > 0 or deleted_themes > 0:
            self.stdout.write(self.style.WARNING(f'Aufgeräumt: {deleted_trainings} Trainings und {deleted_themes} Themen gelöscht'))
        
        self.stdout.write(self.style.SUCCESS('Import abgeschlossen!'))
    
    def extract_title_from_filename(self, filename):
        """Extrahiert den Titel aus dem Dateinamen"""
        # Entferne ".docx.html" und "Schulung - X. "
        title = filename.replace('.docx.html', '').replace('.html', '')
        title = re.sub(r'^Schulung\s*-\s*\d+\.\s*', '', title)
        return title.strip()
    
    def extract_description(self, soup):
        """Extrahiert eine Beschreibung aus den ersten Absätzen"""
        # Suche nach den ersten Textabsätzen
        paragraphs = soup.find_all('p')
        description_parts = []
        
        for p in paragraphs[:3]:  # Erste 3 Absätze
            text = p.get_text().strip()
            if text and len(text) > 20:  # Ignoriere sehr kurze Texte
                description_parts.append(text)
        
        if description_parts:
            return ' '.join(description_parts)[:500]  # Maximal 500 Zeichen
        
        return "Praktische Schulung für Naturmacher.de"
    
    def extract_content(self, soup):
        """Extrahiert den vollständigen Inhalt ohne Style-Tags"""
        # Entferne Script und Style Tags
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extrahiere den Text aus dem Body
        body = soup.find('body')
        if body:
            return body.get_text().strip()
        
        return soup.get_text().strip()
    
    def determine_difficulty(self, titel, inhalt):
        """Bestimmt die Schwierigkeit basierend auf Titel und Inhalt"""
        titel_lower = titel.lower()
        inhalt_lower = inhalt.lower()
        
        # Grundlagen/Einsteiger-Keywords
        if any(keyword in titel_lower for keyword in ['grundlagen', 'einführung', 'basics', 'start']):
            return 'anfaenger'
        
        # Fortgeschrittene Keywords
        if any(keyword in titel_lower for keyword in ['fortgeschritten', 'advanced', 'roi', 'analytics', 'automation']):
            return 'fortgeschritten'
        
        # Experten-Keywords
        if any(keyword in titel_lower for keyword in ['experte', 'expert', 'skalierung', 'international']):
            return 'experte'
        
        # Standard: Anfänger
        return 'anfaenger'
    
    def extract_duration(self, inhalt):
        """Extrahiert die Dauer aus dem Inhalt oder verwendet Standard-Werte"""
        # Suche nach Zeitangaben im Text
        duration_match = re.search(r'(\d+)\s*(?:stunde|hour|min)', inhalt.lower())
        if duration_match:
            duration = int(duration_match.group(1))
            # Wenn es Stunden sind, in Minuten umwandeln
            if 'stunde' in inhalt.lower() or 'hour' in inhalt.lower():
                return duration * 60
            return duration
        
        # Standard: 120 Minuten (2 Stunden)
        return 120