import os
import zipfile
import requests
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.conf import settings
from django.db import models
from .models import Thema, Training, UserTrainingFortschritt, UserTrainingNotizen, APIBalance, APIUsageLog
from .utils.youtube_search import get_youtube_videos_for_training
from .api_pricing import calculate_cost, estimate_tokens, get_provider_from_model, get_model_info
from .utils import get_user_api_key


class ThemaListView(ListView):
    model = Thema
    template_name = 'naturmacher/thema_list.html'
    context_object_name = 'themen'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Erweitere jedes Thema um Benutzer-spezifische Daten
        if self.request.user.is_authenticated:
            themen_mit_fortschritt = []
            for thema in context['themen']:
                thema.user_fortschritt = thema.get_fortschritt(self.request.user)
                thema.user_komplett_erledigt = thema.ist_komplett_erledigt(self.request.user)
                themen_mit_fortschritt.append(thema)
            context['themen'] = themen_mit_fortschritt
        
        return context


class ThemaDetailView(DetailView):
    model = Thema
    template_name = 'naturmacher/thema_detail.html'
    context_object_name = 'thema'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Trainings alphabetisch sortieren
        trainings = self.object.trainings.all().order_by('titel')
        
        # Erweitere Trainings um Benutzer-spezifische Daten
        if self.request.user.is_authenticated:
            trainings_mit_status = []
            for training in trainings:
                training.user_erledigt = training.ist_erledigt(self.request.user)
                trainings_mit_status.append(training)
            context['trainings'] = trainings_mit_status
            
            # Thema-Fortschritt für den aktuellen User
            context['thema_fortschritt'] = self.object.get_fortschritt(self.request.user)
            context['thema_komplett_erledigt'] = self.object.ist_komplett_erledigt(self.request.user)
        else:
            context['trainings'] = trainings
        
        # Inhaltsverzeichnis hinzufügen
        context['inhaltsverzeichnis'] = self.object.get_inhaltsverzeichnis()
            
        return context


class TrainingDetailView(DetailView):
    model = Training
    template_name = 'naturmacher/training_detail.html'
    context_object_name = 'training'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Training-Status für den aktuellen User
        if self.request.user.is_authenticated:
            context['training_erledigt'] = self.object.ist_erledigt(self.request.user)
            context['training_notizen'] = self.object.get_notizen(self.request.user)
            
            # Notizen-Typ ermitteln
            try:
                notizen_obj = UserTrainingNotizen.objects.get(user=self.request.user, training=self.object)
                context['notizen_input_type'] = notizen_obj.input_type
            except UserTrainingNotizen.DoesNotExist:
                context['notizen_input_type'] = 'text'
        
        # YouTube-Videos verarbeiten
        youtube_videos = []
        if self.object.youtube_links:
            lines = self.object.youtube_links.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    video_id = self.object.get_youtube_video_id(line)
                    if video_id:
                        youtube_videos.append({
                            'url': line,
                            'video_id': video_id,
                            'embed_url': f'https://www.youtube.com/embed/{video_id}'
                        })
        context['youtube_videos'] = youtube_videos
        
        # HTML-Inhalt für KI-generierte Schulungen laden
        context['html_content'] = self.object.get_html_content()
        
        return context


def import_trainings_view(request):
    """View zum Ausführen des Sync-Commands über die Web-Oberfläche"""
    try:
        # Führe Sync-Command aus
        from naturmacher.management.commands.sync_trainings import Command
        sync_command = Command()
        stats = sync_command.handle()
        
        if 'error' in stats:
            messages.error(request, stats['error'])
        else:
            # Erstelle detaillierte Statusmeldung
            message_parts = []
            
            if stats['neue_themen'] > 0:
                message_parts.append(f"{stats['neue_themen']} neue Themen")
            
            if stats['neue_trainings'] > 0:
                message_parts.append(f"{stats['neue_trainings']} neue Trainings")
                
            if stats['aktualisierte_trainings'] > 0:
                message_parts.append(f"{stats['aktualisierte_trainings']} Trainings aktualisiert")
            
            if stats['geloeschte_trainings'] > 0:
                message_parts.append(f"{stats['geloeschte_trainings']} Trainings entfernt")
                
            if stats['geloeschte_themen'] > 0:
                message_parts.append(f"{stats['geloeschte_themen']} Themen entfernt")
            
            if message_parts:
                message = "Synchronisation erfolgreich! " + ", ".join(message_parts) + "."
                if stats['geloeschte_trainings'] > 0 or stats['geloeschte_themen'] > 0:
                    messages.warning(request, message)
                else:
                    messages.success(request, message)
            else:
                messages.info(request, "Alle Trainings sind bereits synchron. Keine Änderungen erforderlich.")
            
    except Exception as e:
        messages.error(request, f"Fehler bei der Synchronisation: {str(e)}")
    
    # Zurück zur Themen-Liste
    return redirect('naturmacher:thema_list')


@login_required
def toggle_training_status(request, training_id):
    """Togglet den Erledigungsstatus eines Trainings für den aktuellen User"""
    training = get_object_or_404(Training, id=training_id)
    
    # Hole oder erstelle den Fortschritt-Eintrag
    fortschritt, created = UserTrainingFortschritt.objects.get_or_create(
        user=request.user,
        training=training,
        defaults={'erledigt': False}
    )
    
    # Toggle den Status
    fortschritt.erledigt = not fortschritt.erledigt
    fortschritt.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX-Request
        return JsonResponse({
            'success': True,
            'erledigt': fortschritt.erledigt,
            'message': 'Training als erledigt markiert!' if fortschritt.erledigt else 'Training als offen markiert!'
        })
    else:
        # Normale HTTP-Request
        status_text = "erledigt" if fortschritt.erledigt else "offen"
        messages.success(request, f'Training "{training.titel}" als {status_text} markiert!')
        return redirect('naturmacher:training_detail', pk=training_id)


@login_required
def upload_trainings_view(request):
    """View für das Hochladen von Training-Ordnern"""
    if request.method == 'POST':
        # Prüfe ob Dateien hochgeladen wurden
        if 'training_files' not in request.FILES:
            messages.error(request, 'Keine Dateien ausgewählt.')
            return redirect('naturmacher:upload_trainings')
        
        thema_name = request.POST.get('thema_name', '').strip()
        if not thema_name:
            messages.error(request, 'Bitte geben Sie einen Thema-Namen ein.')
            return redirect('naturmacher:upload_trainings')
        
        uploaded_files = request.FILES.getlist('training_files')
        
        # Prüfe ob nur HTML-Dateien hochgeladen wurden
        html_files = [f for f in uploaded_files if f.name.endswith('.html')]
        if len(html_files) != len(uploaded_files):
            messages.error(request, 'Bitte laden Sie nur HTML-Dateien hoch.')
            return redirect('naturmacher:upload_trainings')
        
        if not html_files:
            messages.error(request, 'Keine HTML-Dateien gefunden.')
            return redirect('naturmacher:upload_trainings')
        
        try:
            # Erstelle Themen-Ordner
            trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
            os.makedirs(trainings_base_path, exist_ok=True)
            
            # Finde nächste verfügbare Nummer für das Thema
            existing_folders = [f for f in os.listdir(trainings_base_path) if os.path.isdir(os.path.join(trainings_base_path, f))]
            next_number = 1
            for folder in existing_folders:
                if folder.startswith(f"{next_number}. Web - "):
                    next_number += 1
            
            thema_folder_name = f"{next_number}. Web - {thema_name}"
            thema_folder_path = os.path.join(trainings_base_path, thema_folder_name)
            
            # Prüfe ob Thema bereits existiert
            if os.path.exists(thema_folder_path):
                messages.error(request, f'Thema "{thema_name}" existiert bereits.')
                return redirect('naturmacher:upload_trainings')
            
            # Erstelle Themen-Ordner
            os.makedirs(thema_folder_path, exist_ok=True)
            
            # Speichere HTML-Dateien
            saved_files = []
            for html_file in html_files:
                file_path = os.path.join(thema_folder_path, html_file.name)
                with open(file_path, 'wb+') as destination:
                    for chunk in html_file.chunks():
                        destination.write(chunk)
                saved_files.append(html_file.name)
            
            # Erstelle automatisch ein Inhaltsverzeichnis
            inhaltsverzeichnis_path = os.path.join(thema_folder_path, 'inhaltsverzeichnis.txt')
            with open(inhaltsverzeichnis_path, 'w', encoding='utf-8') as f:
                f.write(f"TRAININGS FÜR {thema_name.upper()}\n")
                f.write("=" * (len(thema_name) + 13) + "\n\n")
                for i, filename in enumerate(saved_files, 1):
                    # Extrahiere Titel aus Dateiname
                    title = filename.replace('.html', '').replace('.docx.html', '')
                    title = title.replace('Schulung - ', '').strip()
                    f.write(f"{i}. {title}\n")
                f.write(f"\nJede Schulung ist für 1-2 Stunden konzipiert.\n")
            
            messages.success(request, f'Erfolgreich {len(saved_files)} Trainings für Thema "{thema_name}" hochgeladen!')
            
            # Führe automatisch Import aus
            from naturmacher.management.commands.sync_trainings import Command
            sync_command = Command()
            stats = sync_command.handle()
            
            if stats.get('neue_themen', 0) > 0 or stats.get('neue_trainings', 0) > 0:
                messages.success(request, f"Neue Trainings wurden automatisch importiert: {stats.get('neue_trainings', 0)} Trainings in {stats.get('neue_themen', 0)} Themen.")
            
        except Exception as e:
            messages.error(request, f'Fehler beim Hochladen: {str(e)}')
        
        return redirect('naturmacher:thema_list')
    
    return render(request, 'naturmacher/upload_trainings.html')


@login_required
def get_training_notizen(request, training_id):
    """AJAX-View zum Abrufen der Notizen für ein Training"""
    training = get_object_or_404(Training, id=training_id)
    
    try:
        notizen_obj = UserTrainingNotizen.objects.get(user=request.user, training=training)
        notizen = notizen_obj.notizen
        input_type = notizen_obj.input_type
    except UserTrainingNotizen.DoesNotExist:
        notizen = ""
        input_type = "text"
    
    return JsonResponse({
        'success': True,
        'notizen': notizen,
        'input_type': input_type,
        'training_titel': training.titel
    })


@login_required
def save_training_notizen(request, training_id):
    """AJAX-View zum Speichern der Notizen für ein Training"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    training = get_object_or_404(Training, id=training_id)
    notizen_text = request.POST.get('notizen', '').strip()
    input_type = request.POST.get('input_type', 'text')
    
    # Debug-Ausgaben
    print(f"Speichere Notizen für Training {training_id}")
    print(f"Input Type: {input_type}")
    print(f"Daten Länge: {len(notizen_text)}")
    if input_type == 'handwriting':
        print(f"Handschrift-Daten (ersten 100 Zeichen): {notizen_text[:100]}")
    
    try:
        notizen_obj, created = UserTrainingNotizen.objects.get_or_create(
            user=request.user,
            training=training,
            defaults={'notizen': notizen_text, 'input_type': input_type}
        )
        
        if not created:
            notizen_obj.notizen = notizen_text
            notizen_obj.input_type = input_type
            notizen_obj.save()
        
        success_message = f'Notizen erfolgreich gespeichert! (Typ: {input_type}, Länge: {len(notizen_text)})'
        
        return JsonResponse({
            'success': True,
            'message': success_message,
            'hat_notizen': bool(notizen_text),
            'input_type': input_type,
            'data_length': len(notizen_text)
        })
        
    except Exception as e:
        print(f"Fehler beim Speichern: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Speichern: {str(e)}'
        })


@login_required
def get_thema_notizen(request, thema_id):
    """AJAX-View zum Abrufen aller Notizen für ein Thema"""
    thema = get_object_or_404(Thema, id=thema_id)
    
    # Direkt aus der Datenbank holen, um input_type zu bekommen
    notizen_list = []
    for training in thema.trainings.all().order_by('titel'):
        try:
            notizen = UserTrainingNotizen.objects.get(user=request.user, training=training)
            if notizen.notizen.strip():
                notizen_list.append({
                    'training_titel': training.titel,
                    'notizen': notizen.notizen,
                    'input_type': notizen.input_type,
                    'aktualisiert_am': notizen.aktualisiert_am.strftime('%d.%m.%Y %H:%M')
                })
        except UserTrainingNotizen.DoesNotExist:
            continue
    
    return JsonResponse({
        'success': True,
        'thema_name': thema.name,
        'notizen': notizen_list
    })


@login_required
def save_youtube_links(request, training_id):
    """AJAX-View zum Speichern der YouTube-Links für ein Training"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    training = get_object_or_404(Training, id=training_id)
    youtube_links = request.POST.get('youtube_links', '').strip()
    
    try:
        training.youtube_links = youtube_links
        training.save()
        
        return JsonResponse({
            'success': True,
            'message': 'YouTube-Links erfolgreich gespeichert!',
            'hat_videos': bool(youtube_links)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Speichern: {str(e)}'
        })


def search_themen_und_trainings(request):
    """AJAX-View für die Volltext-Suche in Themen und Trainings"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({
            'success': False,
            'error': 'Suchbegriff zu kurz'
        })
    
    # Themen durchsuchen
    themen_results = []
    themen = Thema.objects.filter(
        models.Q(name__icontains=query) | 
        models.Q(beschreibung__icontains=query)
    ).distinct()
    
    for thema in themen:
        themen_results.append({
            'type': 'thema',
            'id': thema.id,
            'title': thema.name,
            'description': thema.beschreibung[:100] + '...' if len(thema.beschreibung) > 100 else thema.beschreibung,
            'url': thema.get_absolute_url(),
            'training_count': thema.trainings.count(),
            'badge': f"{thema.trainings.count()} Training{'s' if thema.trainings.count() != 1 else ''}"
        })
    
    # Trainings durchsuchen
    trainings_results = []
    trainings = Training.objects.filter(
        models.Q(titel__icontains=query) | 
        models.Q(beschreibung__icontains=query) |
        models.Q(inhalt__icontains=query) |
        models.Q(thema__name__icontains=query)
    ).distinct().select_related('thema')
    
    for training in trainings:
        trainings_results.append({
            'type': 'training',
            'id': training.id,
            'title': training.titel,
            'description': training.beschreibung[:100] + '...' if len(training.beschreibung) > 100 else training.beschreibung,
            'url': training.get_absolute_url(),
            'thema_name': training.thema.name,
            'schwierigkeit': training.get_schwierigkeit_display(),
            'dauer': training.dauer_minuten,
            'badge': f"{training.thema.name} • {training.dauer_minuten} Min."
        })
    
    # Ergebnisse nach Relevanz sortieren (exakte Treffer zuerst)
    def sort_by_relevance(item):
        title_lower = item['title'].lower()
        query_lower = query.lower()
        
        if title_lower == query_lower:
            return 0  # Exakte Übereinstimmung
        elif title_lower.startswith(query_lower):
            return 1  # Beginnt mit Suchbegriff
        elif query_lower in title_lower:
            return 2  # Enthält Suchbegriff
        else:
            return 3  # In Beschreibung/Inhalt gefunden
    
    themen_results.sort(key=sort_by_relevance)
    trainings_results.sort(key=sort_by_relevance)
    
    return JsonResponse({
        'success': True,
        'query': query,
        'themen': themen_results,
        'trainings': trainings_results,
        'total_count': len(themen_results) + len(trainings_results)
    })


@login_required
def delete_training(request, training_id):
    """AJAX-View zum Löschen eines Trainings"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    try:
        from django.db import OperationalError, ProgrammingError
        
        training = get_object_or_404(Training, id=training_id)
        thema = training.thema
        thema_detail_url = thema.get_absolute_url()
        
        # Lösche verknüpfte HTML-Datei falls vorhanden (KI-generierte Schulungen)
        try:
            if "HTML-Datei:" in training.inhalt:
                lines = training.inhalt.split('\n')
                filename = None
                for line in lines:
                    if line.startswith('HTML-Datei:'):
                        filename = line.replace('HTML-Datei:', '').strip()
                        break
                
                if filename:
                    # Finde den passenden Thema-Ordner
                    trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
                    if os.path.exists(trainings_base_path):
                        for folder in os.listdir(trainings_base_path):
                            folder_path = os.path.join(trainings_base_path, folder)
                            if os.path.isdir(folder_path) and thema.name.lower() in folder.lower():
                                file_path = os.path.join(folder_path, filename)
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    print(f"HTML-Datei gelöscht: {file_path}")
                                
                                # Inhaltsverzeichnis aktualisieren
                                inhaltsverzeichnis_path = os.path.join(folder_path, 'inhaltsverzeichnis.txt')
                                if os.path.exists(inhaltsverzeichnis_path):
                                    with open(inhaltsverzeichnis_path, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    
                                    # Entferne die Zeile für dieses Training
                                    lines = content.split('\n')
                                    new_lines = []
                                    for line in lines:
                                        if training.titel not in line:
                                            new_lines.append(line)
                                    
                                    with open(inhaltsverzeichnis_path, 'w', encoding='utf-8') as f:
                                        f.write('\n'.join(new_lines))
                                break
        except Exception as e:
            print(f"Fehler beim Löschen der HTML-Datei: {e}")
        
        # Lösche alle verknüpften Daten
        # Fortschritt aller Benutzer löschen
        UserTrainingFortschritt.objects.filter(training=training).delete()
        
        # Notizen aller Benutzer löschen
        UserTrainingNotizen.objects.filter(training=training).delete()
        
        # Training selbst löschen - mit Datenbank-Fehlerbehandlung
        training_title = training.titel
        try:
            training.delete()
        except (OperationalError, ProgrammingError) as db_error:
            if "no such table" in str(db_error).lower():
                # Versuche das Training direkt zu löschen ohne die APIUsageLog Tabelle
                print(f"⚠️  APIUsageLog-Tabelle nicht vorhanden - Training wird trotzdem gelöscht")
                
                # Lösche das Training mit SQL um die ForeignKey-Constraints zu umgehen
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM naturmacher_training WHERE id = %s", [training.id])
                    
                print(f"Training '{training_title}' erfolgreich gelöscht (direkt über SQL)")
            else:
                # Andere Datenbankfehler weiterleiten
                raise db_error
        
        return JsonResponse({
            'success': True,
            'message': f'Training "{training_title}" wurde erfolgreich gelöscht',
            'redirect_url': thema_detail_url
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Löschen: {str(e)}'
        })


from django.views.decorators.http import require_POST, require_http_methods

@login_required
@require_http_methods(["POST"])
def create_thema(request):
    """AJAX-View zum Erstellen eines neuen Themas"""
    thema_name = request.POST.get('thema_name', '').strip()
    if not thema_name:
        return JsonResponse({'success': False, 'error': 'Thema-Name darf nicht leer sein'})

    try:
        trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        os.makedirs(trainings_base_path, exist_ok=True)

        existing_folders = [f for f in os.listdir(trainings_base_path) if os.path.isdir(os.path.join(trainings_base_path, f))]
        next_number = 1
        for folder in existing_folders:
            if folder.startswith(f"{next_number}. Web - "):
                next_number += 1

        thema_folder_name = f"{next_number}. Web - {thema_name}"
        thema_folder_path = os.path.join(trainings_base_path, thema_folder_name)

        if os.path.exists(thema_folder_path):
            return JsonResponse({'success': False, 'error': f'Thema "{thema_name}" existiert bereits.'})

        os.makedirs(thema_folder_path, exist_ok=True)

        inhaltsverzeichnis_path = os.path.join(thema_folder_path, 'inhaltsverzeichnis.txt')
        with open(inhaltsverzeichnis_path, 'w', encoding='utf-8') as f:
            f.write(f"TRAININGS FÜR {thema_name.upper()}\n")
            f.write("=" * (len(thema_name) + 13) + "\n\n")
            f.write(f"Jede Schulung ist für 1-2 Stunden konzipiert.\n")

        # Führe Sync-Command aus, um das neue Thema in der DB zu erstellen
        from naturmacher.management.commands.sync_trainings import Command
        sync_command = Command()
        sync_command.handle()

        return JsonResponse({'success': True, 'message': f'Thema "{thema_name}" erfolgreich erstellt und synchronisiert!'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Fehler beim Erstellen des Themas: {str(e)}'})


from django.views.decorators.http import require_POST

@login_required
@require_POST
def delete_thema(request, thema_id):
    """AJAX-View zum Löschen eines Themas"""
    try:
        thema = get_object_or_404(Thema, id=thema_id)

        # Prüfen, ob das Thema Trainings enthält
        if thema.trainings.exists():
            return JsonResponse({'success': False, 'error': 'Thema kann nicht gelöscht werden, da es noch Trainings enthält.'})

        # Thema-Ordner löschen
        trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        
        # Finde den Ordner, der zu diesem Thema gehört
        thema_folder_path = None
        for folder in os.listdir(trainings_base_path):
            folder_path = os.path.join(trainings_base_path, folder)
            if os.path.isdir(folder_path) and thema.name.lower() in folder.lower():
                thema_folder_path = folder_path
                break

        if thema_folder_path and os.path.exists(thema_folder_path):
            import shutil
            shutil.rmtree(thema_folder_path)
            print(f"Thema-Ordner gelöscht: {thema_folder_path}")
        else:
            print(f"Warnung: Thema-Ordner für '{thema.name}' nicht gefunden oder bereits gelöscht.")

        # Thema aus der Datenbank löschen
        thema_name = thema.name
        thema.delete()

        # Führe Sync-Command aus, um die DB zu aktualisieren
        from naturmacher.management.commands.sync_trainings import Command
        sync_command = Command()
        sync_command.handle()

        return JsonResponse({'success': True, 'message': f'Thema "{thema_name}" erfolgreich gelöscht!'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Fehler beim Löschen des Themas: {str(e)}'})


@login_required
def generate_ai_training(request):
    """AJAX-View für die KI-gestützte Schulungserstellung"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    try:
        thema_id = request.POST.get('thema_id')
        thema_name = request.POST.get('thema_name')
        training_title = request.POST.get('training_title')
        training_description = request.POST.get('training_description')
        training_level = request.POST.get('training_level')
        ai_provider = request.POST.get('ai_provider')
        company_info = request.POST.get('company_info')
        learning_goals = request.POST.get('learning_goals')
        
        # Validierung
        if not all([thema_id, training_title, training_description, training_level, ai_provider]):
            return JsonResponse({'success': False, 'error': 'Alle Pflichtfelder müssen ausgefüllt werden'})
        
        thema = get_object_or_404(Thema, id=thema_id)
        
        # KI-Prompt je nach Provider anpassen
        if ai_provider == 'openai':
            # Kürzerer Prompt für OpenAI wegen Token-Limits
            ai_prompt = f"""
Erstelle eine HTML-Schulung für "{training_title}" (Thema: {thema_name}).

Beschreibung: {training_description}
Schwierigkeitsgrad: {training_level}

ANFORDERUNGEN:
- MINIMUM 15.000 Zeichen HTML-Code
- 6 Hauptkapitel mit je 3-5 Unterabschnitten  
- 8 praktische Übungen mit Checklisten
- Vollständiges HTML mit CSS-Styling
- Naturmacher.de Beispiele verwenden

Firmeninfo: Naturmacher.de - Familienunternehmen für natürliche Baby-/Kleinkindspielzeuge und personalisierte Blumentöpfe (40W Laser). Blog mit 15.000 Besuchern/Monat. Tools: Fliki, Canva, Ubersuggest, Claude, Gemini.

WICHTIG: Antworte NUR mit vollständigem HTML-Code. Keine Erklärungen!"""
        else:
            # Vollständiger Prompt für Claude/Gemini
            ai_prompt = f"""
{company_info}

{learning_goals}

# WICHTIGE ANFORDERUNGEN AN DIE SCHULUNGSLÄNGE:
- MINIMUM 15.000 Zeichen HTML-Code
- MINIMUM 5.000 Wörter Schulungsinhalt
- MINIMUM 6 Hauptkapitel mit jeweils 3-5 Unterabschnitten
- MINIMUM 8 praktische Übungen mit detaillierten Checklisten
- Jedes Kapitel soll mindestens 800-1200 Wörter enthalten

# KRITISCHE INHALTLICHE ANFORDERUNGEN:
## Textstruktur und Formatierung:
- JEDER Abschnitt muss MINDESTENS 6 vollständige Sätze enthalten
- VERMEIDE kurze, oberflächliche Absätze von 1-3 Sätzen
- Verwende substanzielle, ausführliche Erklärungen statt Stichpunkten
- Baue zusammenhängende Argumentationsketten auf
- Jeder Gedanke soll vollständig ausgearbeitet werden

## Vielfältige Inhaltsformate PFLICHT:
- **Tabellen**: Mindestens 3 aussagekräftige Vergleichstabellen pro Schulung
- **Fun Facts**: 2-3 interessante Fakten pro Kapitel in farbigen Boxen
- **Listen**: Verwende nummerierte und Bullet-Listen nur sparsam, dafür ausführlich
- **Vergleiche**: Before/After Szenarien, Pro/Contra Analysen
- **Fallstudien**: Konkrete Naturmacher-Beispiele mit detaillierter Analyse
- **Schritt-für-Schritt Anleitungen**: Mit Begründungen für jeden Schritt
- **Statistiken und Zahlen**: Relevante Branchendaten einbauen

## Schreibstil-Richtlinien:
- Schreibe wie ein Fachbuch, nicht wie eine Präsentation
- Verwende komplexe, aber verständliche Sätze
- Baue logische Übergänge zwischen Absätzen ein
- Erkläre das "Warum" hinter jedem Konzept ausführlich
- Verwende konkrete Beispiele zur Veranschaulichung
- Jeder Absatz soll eine vollständige Gedankeneinheit bilden

# Arbeite alles systematisch durch
Schaue dir alles an und lese die jeweiligen Aufgaben gründlich durch. Überspringe keine Aufgaben.

# Detaillierte Aufgabe für diese spezifische Schulung:
Erstelle eine UMFASSENDE und AUSFÜHRLICHE Schulung zum Thema "{training_title}" für das Thema "{thema_name}".

Detaillierte Beschreibung der gewünschten Schulung:
{training_description}

Schwierigkeitsgrad: {training_level}

# STRENGE STRUKTUR-ANFORDERUNGEN:

## 1. UMFANG UND LÄNGE:
- Die Schulung MUSS für genau 2 Stunden Lernzeit ausgelegt sein
- Jedes Kapitel MUSS ausführlich und detailliert sein
- KEINE oberflächlichen Erklärungen - alles tiefgreifend behandeln
- Viele konkrete Beispiele speziell für Naturmacher.de verwenden

## 2. PFLICHT-STRUKTUR (NICHT OPTIONAL):

### Kapitel 1: Einführung und Grundlagen (20 Min.)
**Inhaltliche Gestaltung:**
- Beginne jedes Unterkapitel mit einer ausführlichen Einleitung von mindestens 6-8 Sätzen
- Erstelle eine Vergleichstabelle: "Traditionelle Methoden vs. Moderne Ansätze"
- Integriere 2-3 Fun Facts in farbigen Kästen
- Detaillierte Begriffserklärungen mit konkreten Naturmacher-Fallbeispielen (je 4-6 Sätze)
- Erkläre die Relevanz für das Familienunternehmen in zusammenhängenden Absätzen

### Kapitel 2: Analyse der aktuellen Situation (20 Min.)
**Erweiterte Analysemethoden:**
- Erstelle eine SWOT-Analyse-Tabelle speziell für Naturmacher
- Führe eine detaillierte Bestandsaufnahme durch (jeder Punkt min. 4 Sätze)
- Integriere Branchenstatistiken und Benchmark-Daten in Tabellenform
- Beschreibe Herausforderungen in ausführlichen Absätzen mit Lösungsansätzen
- **ÜBUNG 1**: Vollständige Ist-Analyse mit Schritt-für-Schritt Anleitung (15 Min.)

### Kapitel 3: Strategieentwicklung (25 Min.)
**Strategische Tiefenanalyse:**
- Entwickle mindestens 4 Strategieoptionen mit jeweils 6+ Sätzen Erklärung
- Erstelle eine Pro/Contra-Tabelle für jede Strategie
- Füge eine "Aufwand vs. Nutzen"-Matrix als Tabelle hinzu
- Beschreibe Implementierungsschritte in zusammenhängenden Textblöcken
- **ÜBUNG 2**: Strategieauswahl-Workshop für Naturmacher (20 Min.)

### Kapitel 4: Praktische Umsetzung - Teil 1 (20 Min.)
**Detaillierte Implementierung:**
- Konkrete Handlungsschritte in ausführlichen Absätzen (nicht Stichpunkte!)
- Tool-Vergleichstabelle mit Bewertungskriterien
- Häufige Fehler als Fallstudien beschrieben (je 5-6 Sätze)
- **ÜBUNG 3**: Erste Umsetzungsschritte mit Erfolgskontrolle (15 Min.)
- **ÜBUNG 4**: Tool-Setup mit Troubleshooting-Guide (10 Min.)

### Kapitel 5: Praktische Umsetzung - Teil 2 (25 Min.)
**Erweiterte Methoden:**
- Beschreibe erweiterte Techniken in substantiellen Textblöcken
- Erstelle Prozess-Integration-Tabelle für bestehende Naturmacher-Workflows
- Automatisierungsmöglichkeiten mit ROI-Berechnung
- **ÜBUNG 5**: Erweiterte Implementierung mit Qualitätssicherung (20 Min.)
- **ÜBUNG 6**: Prozessoptimierung-Workshop (15 Min.)

### Kapitel 6: Erfolgsmessung und Optimierung (20 Min.)
**Messbare Ergebnisse:**
- KPI-Definition-Tabelle mit Zielwerten und Messmethoden
- Monitoring-Dashboard-Beschreibung in ausführlichen Absätzen
- Verbesserungszyklen detailliert erklärt (min. 6 Sätze pro Zyklus)
- **ÜBUNG 7**: KPI-Dashboard-Erstellung mit Reporting-Plan (20 Min.)

### Kapitel 7: Langfristige Strategie (10 Min.)
**Zukunftsplanung:**
- Skalierungsoptionen in zusammenhängenden Analysen beschrieben
- Trend-Analyse-Tabelle für die nächsten 2-3 Jahre
- Anpassungsstrategien ausführlich dargelegt
- **ÜBUNG 8**: 6-Monats-Roadmap mit Meilenstein-Planung (15 Min.)

## 3. NATURMACHER-SPEZIFISCHE INHALTE:
Verwende in JEDEM Kapitel konkrete Beispiele zu:
- Den 40W Lasergravierern und Personalisierung
- Den einzigartigen Designern (Bleistift-Upload, Himmelcreator, etc.)
- Blog mit 15.000 monatlichen Besuchern
- Social Media Kanälen (TikTok, Instagram, etc.)
- Dem Familienbetrieb-Aspekt (Eltern von 3- und 6-jährigen Jungs)
- Natürlichen Baby-/Kleinkindspielzeugen
- Personalisierten Blumentöpfen (22,49€ / 34,99€)
- Tools: Fliki, Canva, Ubersuggest, Claude, Gemini
- Vertriebskanälen (eigener Shop, Etsy, Amazon Handmade, etc.)

## 4. ÜBUNGEN - DETAILLIERTE ANFORDERUNGEN:
Jede Übung MUSS enthalten:
- Ausführliche Einleitung zur Übung (mindestens 4-5 Sätze)
- Klare Zeitangabe (10-25 Minuten) mit Begründung
- Schritt-für-Schritt Anleitung in zusammenhängenden Absätzen (nicht nur Stichpunkte)
- Mindestens 8-12 Checklistenpunkte mit Erklärungen
- Konkrete Naturmacher-Fallbeispiele mit detaillierter Beschreibung
- Tabelle mit erwarteten vs. tatsächlichen Ergebnissen
- Troubleshooting-Sektion für häufige Probleme
- Reflexionsfragen mit Lösungshinweisen am Ende
- Success-Metrics zur Erfolgsmessung

## 5. SPEZIELLE GESTALTUNGSELEMENTE (PFLICHT):
### Tabellen (mindestens 3 pro Schulung):
- Vergleichstabellen (Before/After, Tool-Vergleiche, Strategien)
- Bewertungsmatrizen (Aufwand vs. Nutzen, Risiko vs. Chance)
- Checklisten-Tabellen mit Status-Spalten
- KPI-Übersichtstabellen mit Zielwerten

### Fun Facts Boxen (2-3 pro Kapitel):
- Interessante Branchenstatistiken
- Überraschende Erkenntnisse zum Thema
- Historische Entwicklungen
- Erfolgsgeschichten anderer Unternehmen

### Vergleichsanalysen:
- Vorher/Nachher-Szenarien mit konkreten Zahlen
- Naturmacher vs. Wettbewerber-Analysen
- Traditionelle vs. innovative Ansätze
- Kurz- vs. langfristige Strategien

# Folgende TODOs sind dabei zu beachten:
- [ ] erarbeite die Inhalte der Schulung VOLLSTÄNDIG und AUSFÜHRLICH
- [ ] sei dabei gründlich und halte dich an die Anweisungen zur Erstellung der Schulung (Abschnitt "Ziel")
- [ ] überprüfe nach Richtigkeit und Vollständigkeit - MINIMUM 15.000 Zeichen!
- [ ] Schicke den KOMPLETTEN HTML-Code

Das HTML soll vollständig formatiert sein mit:
- Vollständiger HTML-Struktur (DOCTYPE, head, body)
- Professionellem CSS-Styling (embedded styles)
- Sparsame Verwendung von Überschriften (h1, h2, h3 - NICHT h4, h5, h6)
- WENIGE Aufzählungen - stattdessen ausführliche Absätze
- Praktische Übungen in farbigen Boxen
- VIELE aussagekräftige Tabellen für Vergleiche, Analysen und KPIs
- Fun Facts in auffälligen, farbigen Boxen
- Interaktive Checklisten mit Checkboxen
- Farbiges aber dezentes Design
- Druckfreundliches Layout (@media print)
- Responsive Design
- Icons und visuelle Elemente

## ABSOLUTE CONTENT-REGELN:
- VERMEIDE kurze Absätze von 1-3 Sätzen
- SCHREIBE substanzielle Textblöcke von mindestens 6-8 Sätzen
- VERWENDE Tabellen statt Listen wo möglich
- INTEGRIERE Fun Facts als Auflockerung
- ERKLÄRE das "Warum" hinter jedem Konzept ausführlich
- BAUE logische Übergänge zwischen Absätzen

## KRITISCHE HTML-ANFORDERUNGEN:
- NUR Inhalt ohne DOCTYPE, html, head, body Tags (wird in Bootstrap-Card eingefügt)
- Verwende diese CSS-Klassen: .header, .meta-info, .section, .exercise, .tip, .important, .success-box, .checklist
- Professionelle Farbgebung bereits über CSS definiert (Naturmacher-Grün: #28a745, #20c997)
- Responsive Design durch Bootstrap gewährleistet
- Keine externen Abhängigkeiten oder CDN-Links
- Keine <style> Tags verwenden (CSS ist bereits definiert)

BEISPIEL-STRUKTUR:
<div class="header">
    <h1>Titel der Schulung</h1>
    <p>Untertitel oder kurze Beschreibung</p>
</div>

<div class="meta-info">
    <strong>Schwierigkeitsgrad:</strong> Fortgeschritten<br>
    <strong>Dauer:</strong> 2 Stunden
</div>

<div class="section">
    <h2>Kapitel 1: Titel</h2>
    <p>Ausführlicher Text...</p>
    
    <div class="exercise">
        <h3>Übung 1: Titel</h3>
        <p>Anleitung...</p>
    </div>
</div>

WICHTIG: Antworte NUR mit HTML-Inhalt (ohne DOCTYPE, html, head, body). Keine CSS-Styles, keine Erklärungen!
"""
        
        # KI-API-Call durchführen
        api_status = "fallback"
        api_used = "Demo-Version"
        
        try:
            print(f"Starte KI-Generierung für Schulung: {training_title} mit {ai_provider}")
            result = call_ai_api(ai_prompt, ai_provider, request.user)
            
            if result[0]:  # html_content verfügbar
                html_content, api_used = result
                api_status = "success"
                print(f"KI-Generierung erfolgreich mit {api_used} - {len(html_content)} Zeichen generiert")
                
                # Protokolliere API-Nutzung für Kostentracking
                log_api_usage(
                    user=request.user,
                    model_name=api_used,
                    prompt_text=ai_prompt,
                    response_text=html_content,
                    training=None  # Training wird später erstellt
                )
                
                # Qualitätskontrolle: Prüfe Mindestlänge
                if len(html_content) < 15000:
                    print(f"WARNUNG: Generierter Inhalt zu kurz ({len(html_content)} Zeichen). Mindestens 15.000 erwartet.")
                    print("Versuche erneut mit verstärktem Prompt...")
                    
                    # Verstärkter Prompt für zweiten Versuch
                    enhanced_prompt = f"""
KRITISCH: Der vorherige Versuch war ZU KURZ! 

ABSOLUTE MINDESTANFORDERUNG: 15.000+ Zeichen HTML-Code!

{ai_prompt}

NOCHMAL ZUR ERINNERUNG:
- JEDES Kapitel muss 800-1200 Wörter haben
- JEDE Übung muss mindestens 200-300 Wörter Anleitung haben
- Verwende viele konkrete Naturmacher-Beispiele
- Füge detaillierte Erklärungen ein
- Mache ALLES ausführlicher!

ANTWORTE NUR MIT VOLLSTÄNDIGEM HTML - MINIMUM 15.000 ZEICHEN!
"""
                    second_result = call_ai_api(enhanced_prompt, ai_provider, request.user)
                    if second_result[0] and len(second_result[0]) > len(html_content):
                        html_content = second_result[0]
                        print(f"Zweiter Versuch besser: {len(html_content)} Zeichen")
                        
                        # Protokolliere auch den zweiten Versuch
                        log_api_usage(
                            user=request.user,
                            model_name=api_used,
                            prompt_text=enhanced_prompt,
                            response_text=html_content,
                            training=None
                        )
                
                # Verwende den generierten Inhalt auch wenn er kürzer ist
                print(f"Verwende generierten Inhalt mit {len(html_content)} Zeichen")
                    
            else:
                print("❌ Keine KI-API verfügbar oder alle APIs fehlgeschlagen")
                return JsonResponse({
                    'success': False,
                    'error': 'Schulung konnte nicht erstellt werden. Alle KI-APIs sind nicht verfügbar oder haben Fehler.'
                })
                
        except Exception as e:
            print(f"❌ KI-API Fehler: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Schulung konnte nicht erstellt werden. Fehler: {str(e)}'
            })
        
        # Nächste verfügbare Nummer für Training finden
        trainings_base_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        thema_folder = None
        
        # Suche den passenden Thema-Ordner
        if os.path.exists(trainings_base_path):
            for folder in os.listdir(trainings_base_path):
                folder_path = os.path.join(trainings_base_path, folder)
                if os.path.isdir(folder_path) and thema_name.lower() in folder.lower():
                    thema_folder = folder_path
                    break
        
        if not thema_folder:
            return JsonResponse({'success': False, 'error': f'Thema-Ordner für "{thema_name}" nicht gefunden'})
        
        # Nächste verfügbare Nummer für Training finden
        existing_files = [f for f in os.listdir(thema_folder) if f.endswith('.html')]
        next_number = len(existing_files) + 1
        
        # Dateiname erstellen
        safe_title = "".join(c for c in training_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        filename = f"{next_number} - Schulung_zum_{safe_title}.html"
        file_path = os.path.join(thema_folder, filename)
        
        # HTML-Datei speichern
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Inhaltsverzeichnis aktualisieren
        inhaltsverzeichnis_path = os.path.join(thema_folder, 'inhaltsverzeichnis.txt')
        if os.path.exists(inhaltsverzeichnis_path):
            with open(inhaltsverzeichnis_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{next_number}. {training_title}")
        
        # Training in Datenbank erstellen
        new_training = Training.objects.create(
            thema=thema,
            titel=training_title,
            beschreibung=training_description,
            schwierigkeit=training_level,
            dauer_minuten=120,  # Standard 2 Stunden
            inhalt=f"KI-generierte Schulung: {training_description}\n\nHTML-Datei: {filename}"
        )
        
        # Automatisch YouTube-Videos zu AI-generiertem Training hinzufügen
        try:
            youtube_urls = get_youtube_videos_for_training(
                training_title=training_title,
                training_description=training_description,
                thema_name=thema.name,
                user=request.user if request.user.is_authenticated else None
            )
            if youtube_urls:
                new_training.youtube_links = '\n'.join(youtube_urls)
                new_training.save()
        except Exception as e:
            # Fehler bei YouTube-Suche nicht kritisch - Training wurde trotzdem erstellt
            pass
        
        # API-Status für Benutzer-Feedback
        api_display_names = {
            'claude-opus-4': 'Claude Opus 4',
            'claude-sonnet-4': 'Claude Sonnet 4',
            'claude-sonnet-3.7': 'Claude Sonnet 3.7',
            'claude-sonnet-3.5': 'Claude Sonnet 3.5',
            'claude-haiku-3.5': 'Claude Haiku 3.5',
            'openai': 'OpenAI GPT-4', 
            'gemini': 'Google Gemini'
        }
        
        api_message = f"✅ Schulung erfolgreich mit {api_display_names.get(api_used, api_used)} erstellt!"
        if len(html_content) < 15000:
            api_message += f" (Inhalt: {len(html_content)} Zeichen)"
        
        return JsonResponse({
            'success': True,
            'message': 'Schulung erfolgreich erstellt',
            'training_id': new_training.id,
            'filename': filename,
            'api_status': api_status,
            'api_used': api_used,
            'api_message': api_message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Erstellen der Schulung: {str(e)}'
        })


def call_ai_api(prompt, ai_provider='auto', user=None):
    """Ruft verschiedene KI-APIs auf, um HTML-Schulungsinhalte zu generieren"""
    
    # Spezifische KI-API verwenden
    if ai_provider.startswith('claude'):
        claude_result = try_claude_api(prompt, ai_provider, user)
        if claude_result:
            return clean_html_response(claude_result), ai_provider
    elif ai_provider.startswith('gpt-') or ai_provider.startswith('o'):
        # OpenAI-Modelle (gpt-4.1, gpt-4o, o3, o4-mini, etc.)
        openai_result = try_openai_api(prompt, ai_provider, user)
        if openai_result:
            return clean_html_response(openai_result), ai_provider
    elif ai_provider.startswith('gemini-'):
        # Gemini-Modelle (gemini-2.5-flash, gemini-2.0-flash, gemini-2.0-pro, gemini-1.5-flash, gemini-1.5-pro)
        gemini_result = try_gemini_api(prompt, ai_provider, user)
        if gemini_result:
            return clean_html_response(gemini_result), ai_provider
    elif ai_provider == 'gemini':
        # Gemini Standard (kostenlose Option) - verwendet bewährtes Modell
        gemini_result = try_gemini_api(prompt, 'gemini-1.5-flash', user)
        if gemini_result:
            return clean_html_response(gemini_result), 'gemini'
    elif ai_provider == 'auto':
        # Fallback-System: Alle APIs der Reihe nach versuchen (neueste Modelle)
        # Zuerst versuchen wir Claude API (Anthropic) - weltbestes Coding-Modell
        claude_result = try_claude_api(prompt, 'claude-opus-4', user)
        if claude_result:
            return clean_html_response(claude_result), 'claude-opus-4'
        
        # Dann versuchen wir OpenAI API (neuestes Flaggschiff)
        openai_result = try_openai_api(prompt, 'gpt-4.1', user)
        if openai_result:
            return clean_html_response(openai_result), 'gpt-4.1'
        
        # Dann versuchen wir Google Gemini API (höchste Leistung)
        gemini_result = try_gemini_api(prompt, 'gemini-2.5-pro', user)
        if gemini_result:
            return clean_html_response(gemini_result), 'gemini-2.5-pro'
    
    # Keine API verfügbar oder gewählte API funktioniert nicht
    return None, None


def clean_html_response(response):
    """Bereinigt die HTML-Antwort von der KI"""
    if not response:
        return None
    
    import re
    
    # Entferne markdown code blocks falls vorhanden
    response = re.sub(r'```html\s*', '', response, flags=re.IGNORECASE)
    response = re.sub(r'```\s*$', '', response, flags=re.MULTILINE)
    response = re.sub(r'^```\s*', '', response, flags=re.MULTILINE)
    
    # Entferne führende/nachfolgende Leerzeichen und Anführungszeichen
    response = response.strip().strip('"').strip("'")
    
    # Prüfe ob es vollständiges HTML ist
    has_doctype = '<!DOCTYPE html>' in response.upper()
    has_html_tag = '<html' in response.lower()
    has_head = '<head>' in response.lower() or '<head ' in response.lower()
    has_body = '<body>' in response.lower() or '<body ' in response.lower()
    
    # Entferne style und title tags (nicht in Card-Content benötigt)
    response = re.sub(r'<title[^>]*>.*?</title>', '', response, flags=re.IGNORECASE | re.DOTALL)
    response = re.sub(r'<style[^>]*>.*?</style>', '', response, flags=re.IGNORECASE | re.DOTALL)
    
    # Wenn es vollständiges HTML ist, extrahiere nur den Body-Inhalt
    if has_doctype and has_html_tag and has_head and has_body:
        print("🔧 Extrahiere Body-Inhalt aus vollständigem HTML-Dokument")
        body_match = re.search(r'<body[^>]*>(.*?)</body>', response, re.IGNORECASE | re.DOTALL)
        if body_match:
            response = body_match.group(1).strip()
        else:
            # Fallback: entferne html/head/body tags manuell
            response = re.sub(r'<!DOCTYPE[^>]*>', '', response, flags=re.IGNORECASE)
            response = re.sub(r'<html[^>]*>', '', response, flags=re.IGNORECASE)
            response = re.sub(r'</html>', '', response, flags=re.IGNORECASE)
            response = re.sub(r'<head[^>]*>.*?</head>', '', response, flags=re.IGNORECASE | re.DOTALL)
            response = re.sub(r'<body[^>]*>', '', response, flags=re.IGNORECASE)
            response = re.sub(r'</body>', '', response, flags=re.IGNORECASE)
    
    print(f"🔧 HTML-Inhalt bereinigt für Bootstrap-Card ({len(response)} Zeichen)")
    
    return response.strip()


def try_claude_api(prompt, model_choice='claude-sonnet-3.5', user=None):
    """Versucht Claude API zu verwenden mit User-spezifischen API-Keys"""
    api_key = get_user_api_key(user, 'anthropic')
    if not api_key:
        print("❌ Claude API: Kein API-Key konfiguriert (weder in DB noch in .env)")
        return None
    
    # Modell-Mapping für API-Namen
    model_mapping = {
        'claude-opus-4': 'claude-opus-4-20250514',
        'claude-sonnet-4': 'claude-sonnet-4-20250514', 
        'claude-sonnet-3.7': 'claude-3-7-sonnet-20250219',
        'claude-sonnet-3.5-new': 'claude-3-5-sonnet-20241022',  # Neueste Version
        'claude-sonnet-3.5': 'claude-3-5-sonnet-20240620',      # Ältere Version
        'claude-haiku-3.5-new': 'claude-3-5-haiku-20241022',    # Neueste Version
        'claude-haiku-3.5': 'claude-3-5-haiku-20240307'         # Ältere Version
    }
    
    api_model = model_mapping.get(model_choice, 'claude-3-5-sonnet-20241022')
    print(f"🔄 Claude API: Sende Anfrage mit {api_model} ({len(prompt)} Zeichen)...")
        
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    
    data = {
        'model': api_model,
        'max_tokens': 8000,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }
    
    # Retry-Mechanismus für Timeouts
    for attempt in range(2):
        try:
            timeout = 180 if attempt == 0 else 360  # Erster Versuch 3min, zweiter 4min
            print(f"🔄 Claude API: Versuch {attempt + 1} mit {timeout}s Timeout...")
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            print(f"🔄 Claude API: Status Code {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'content' in result and len(result['content']) > 0:
                    content = result['content'][0]['text']
                    print(f"✅ Claude API: Erfolgreich {len(content)} Zeichen erhalten")
                    return content
                else:
                    print(f"❌ Claude API: Unerwartete Antwortstruktur: {result}")
            else:
                error_text = response.text
                print(f"❌ Claude API: HTTP {response.status_code} - {error_text}")
                return None  # Bei HTTP-Fehlern nicht wiederholen
                
        except requests.exceptions.Timeout as e:
            print(f"⏰ Claude API: Timeout nach {timeout}s bei Versuch {attempt + 1}")
            if attempt == 1:  # Letzter Versuch
                print(f"❌ Claude API: Endgültiger Timeout nach 2 Versuchen")
                return None
        except Exception as e:
            print(f"❌ Claude API Fehler: {e}")
            return None
    
    return None


def try_openai_api(prompt, model_name='gpt-4o-mini', user=None):
    """Versucht OpenAI API zu verwenden mit User-spezifischen API-Keys"""
    api_key = get_user_api_key(user, 'openai')
    if not api_key:
        print("❌ OpenAI API: Kein API-Key konfiguriert (weder in DB noch in .env)")
        return None
    
    print(f"🔄 OpenAI API ({model_name}): Sende Anfrage mit {len(prompt)} Zeichen...")
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    # Modell-spezifische Konfiguration
    max_tokens = 4000
    if model_name == 'gpt-4.1':
        max_tokens = 16000
    elif model_name in ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-4.1-mini']:
        max_tokens = 8000
    elif model_name in ['o3', 'o4-mini']:
        max_tokens = 8000
    
    data = {
        'model': model_name,
        'messages': [
            {
                'role': 'system',
                'content': 'Du bist ein Experte für die Erstellung von E-Learning Inhalten und HTML-Schulungen.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'max_tokens': max_tokens,
        'temperature': 0.7
    }
    
    # Retry-Mechanismus für Timeouts
    for attempt in range(2):
        try:
            timeout = 180 if attempt == 0 else 360
            print(f"🔄 OpenAI API ({model_name}): Versuch {attempt + 1} mit {timeout}s Timeout...")

            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            print(f"🔄 OpenAI API ({model_name}): Status Code {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    print(f"✅ OpenAI API ({model_name}): Erfolgreich {len(content)} Zeichen erhalten")
                    return content
                else:
                    print(f"❌ OpenAI API ({model_name}): Unerwartete Antwortstruktur: {result}")
                    return None
            else:
                error_text = response.text
                print(f"❌ OpenAI API ({model_name}): HTTP {response.status_code} - {error_text}")
                return None
        
        except requests.exceptions.Timeout:
            print(f"⏰ OpenAI API ({model_name}): Timeout nach {timeout}s bei Versuch {attempt + 1}")
            if attempt == 1:
                print(f"❌ OpenAI API ({model_name}): Endgültiger Timeout nach 2 Versuchen")
        except Exception as e:
            print(f"❌ OpenAI API ({model_name}) Fehler: {e}")
            return None
            
    return None


def try_gemini_api(prompt, model_name='gemini-1.5-flash', user=None):
    """Versucht Google Gemini API zu verwenden mit User-spezifischen API-Keys"""
    api_key = get_user_api_key(user, 'google')
    if not api_key:
        print("❌ Gemini API: Kein API-Key konfiguriert (weder in DB noch in .env)")
        return None
    
    print(f"🔄 Gemini API ({model_name}): Sende Anfrage mit {len(prompt)} Zeichen...")
        
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = {
        'contents': [
            {
                'parts': [
                    {
                        'text': prompt
                    }
                ]
            }
        ]
    }
    
    # Retry-Mechanismus für Timeouts
    for attempt in range(2):
        try:
            timeout = 180 if attempt == 0 else 360
            print(f"🔄 Gemini API ({model_name}): Versuch {attempt + 1} mit {timeout}s Timeout...")

            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}',
                headers=headers,
                json=data,
                timeout=timeout
            )
            
            print(f"🔄 Gemini API ({model_name}): Status Code {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    if 'finishReason' in candidate and candidate['finishReason'] == 'SAFETY':
                        print(f"❌ Gemini API ({model_name}): Inhalt wegen Sicherheitsrichtlinien blockiert. Details: {candidate.get('safetyRatings')}")
                        return None
                    if 'content' in candidate and 'parts' in candidate['content']:
                        content = candidate['content']['parts'][0]['text']
                        print(f"✅ Gemini API ({model_name}): Erfolgreich {len(content)} Zeichen erhalten")
                        return content
                    else:
                        print(f"❌ Gemini API ({model_name}): Unerwartete Antwortstruktur (kein content/parts): {result}")
                        return None
                else:
                    print(f"❌ Gemini API ({model_name}): Keine Kandidaten in Antwort. Möglicherweise wurde der Prompt blockiert. Antwort: {result}")
                    return None
            else:
                error_text = response.text
                print(f"❌ Gemini API ({model_name}): HTTP {response.status_code} - {error_text}")
                return None
        
        except requests.exceptions.Timeout:
            print(f"⏰ Gemini API ({model_name}): Timeout nach {timeout}s bei Versuch {attempt + 1}")
            if attempt == 1:
                print(f"❌ Gemini API ({model_name}): Endgültiger Timeout nach 2 Versuchen")
        except Exception as e:
            print(f"❌ Gemini API ({model_name}) Fehler: {e}")
            return None
            
    return None


# ===============================
# API Balance Management Views
# ===============================

@login_required
def get_api_balances(request):
    """AJAX-View zum Abrufen aller API-Kontostände eines Users"""
    try:
        from django.db import OperationalError, ProgrammingError
        
        balances = {}
        
        try:
            # Hole alle Kontostände für den aktuellen User
            user_balances = APIBalance.objects.filter(user=request.user)
            
            for balance in user_balances:
                balances[balance.provider] = {
                    'balance': float(balance.balance),
                    'currency': balance.currency,
                    'status': balance.get_balance_status(),
                    'is_low': balance.is_low_balance(),
                    'threshold': float(balance.auto_warning_threshold),
                    'last_updated': balance.last_updated.isoformat(),
                    'has_api_key': balance.has_api_key(),
                    'masked_api_key': balance.get_masked_api_key()
                }
            
            # Füge leere Einträge für nicht vorhandene Provider hinzu
            provider_choices = [
                ('openai', 'OpenAI (ChatGPT)'),
                ('anthropic', 'Anthropic (Claude)'),
                ('google', 'Google (Gemini)'),
            ]
            
            for provider_key, provider_name in provider_choices:
                if provider_key not in balances:
                    balances[provider_key] = {
                        'balance': 0.00,
                        'currency': 'USD',
                        'status': 'empty',
                        'is_low': True,
                        'threshold': 5.00,
                        'last_updated': None,
                        'has_api_key': False,
                        'masked_api_key': 'Nicht konfiguriert'
                    }
            
            return JsonResponse({
                'success': True,
                'balances': balances
            })
            
        except (OperationalError, ProgrammingError) as db_error:
            if "no such table" in str(db_error).lower():
                # Gib Standard-Einträge zurück wenn Tabelle nicht existiert
                default_balances = {}
                provider_choices = [
                    ('openai', 'OpenAI (ChatGPT)'),
                    ('anthropic', 'Anthropic (Claude)'),
                    ('google', 'Google (Gemini)'),
                ]
                
                for provider_key, provider_name in provider_choices:
                    default_balances[provider_key] = {
                        'balance': 0.00,
                        'currency': 'USD',
                        'status': 'empty',
                        'is_low': True,
                        'threshold': 5.00,
                        'last_updated': None,
                        'has_api_key': False,
                        'masked_api_key': 'Datenbank nicht initialisiert'
                    }
                
                return JsonResponse({
                    'success': True,
                    'balances': default_balances,
                    'warning': 'API-Datenbank nicht initialisiert. Führen Sie "python manage.py migrate" aus.'
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': f'Datenbank-Fehler: {str(db_error)}'
                })
                
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def update_api_balance(request):
    """AJAX-View zum Aktualisieren eines API-Kontostands"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    try:
        from django.db import OperationalError, ProgrammingError
        
        provider = request.POST.get('provider')
        balance = request.POST.get('balance')
        currency = request.POST.get('currency', 'USD')
        threshold = request.POST.get('threshold', '5.00')
        api_key = request.POST.get('api_key', '').strip()
        quota_limit = request.POST.get('quota_limit')  # Für YouTube
        
        # YouTube verwendet Quota statt Balance
        if provider == 'youtube':
            if not api_key and not quota_limit:
                return JsonResponse({'success': False, 'error': 'API-Key oder Quota-Limit ist erforderlich'})
            # Für YouTube: quota_limit als balance verwenden, wenn balance nicht gesetzt
            if balance is None and quota_limit:
                balance = quota_limit
                currency = 'QUOTA'  # Spezielle Währung für YouTube
        elif not provider or balance is None:
            return JsonResponse({'success': False, 'error': 'Provider und Balance sind erforderlich'})
        
        # Validiere Provider
        valid_providers = [choice[0] for choice in APIBalance.PROVIDER_CHOICES]
        if provider not in valid_providers:
            return JsonResponse({'success': False, 'error': 'Ungültiger Provider'})
        
        # Konvertiere zu Decimal
        from decimal import Decimal, InvalidOperation
        try:
            balance_decimal = Decimal(str(balance))
            threshold_decimal = Decimal(str(threshold))
        except (InvalidOperation, ValueError):
            return JsonResponse({'success': False, 'error': 'Ungültiger Zahlenwert'})
        
        # Versuche Kontostand zu erstellen/aktualisieren
        try:
            api_balance, created = APIBalance.objects.get_or_create(
                user=request.user,
                provider=provider,
                defaults={
                    'balance': balance_decimal,
                    'currency': currency,
                    'auto_warning_threshold': threshold_decimal,
                    'api_key': api_key
                }
            )
            
            if not created:
                api_balance.balance = balance_decimal
                api_balance.currency = currency
                api_balance.auto_warning_threshold = threshold_decimal
                # Nur API-Key aktualisieren wenn er angegeben wurde
                if api_key:
                    api_balance.api_key = api_key
                api_balance.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Kontostand für {APIBalance.PROVIDER_CHOICES[next(i for i, (k, v) in enumerate(APIBalance.PROVIDER_CHOICES) if k == provider)][1]} aktualisiert',
                'masked_api_key': api_balance.get_masked_api_key(),
                'balance': {
                    'balance': float(api_balance.balance),
                    'currency': api_balance.currency,
                    'status': api_balance.get_balance_status(),
                    'is_low': api_balance.is_low_balance(),
                    'threshold': float(api_balance.auto_warning_threshold),
                    'last_updated': api_balance.last_updated.isoformat(),
                    'has_api_key': api_balance.has_api_key(),
                    'masked_api_key': api_balance.get_masked_api_key()
                }
            })
            
        except (OperationalError, ProgrammingError) as db_error:
            if "no such table" in str(db_error).lower():
                return JsonResponse({
                    'success': False, 
                    'error': 'API-Datenbank nicht initialisiert. Führen Sie "python manage.py migrate" aus.'
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': f'Datenbank-Fehler: {str(db_error)}'
                })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def remove_api_key(request):
    """AJAX-View zum Entfernen eines API-Keys"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    try:
        from django.db import OperationalError, ProgrammingError
        
        provider = request.POST.get('provider')
        
        if not provider:
            return JsonResponse({'success': False, 'error': 'Provider ist erforderlich'})
        
        # Validiere Provider
        valid_providers = [choice[0] for choice in APIBalance.PROVIDER_CHOICES]
        if provider not in valid_providers:
            return JsonResponse({'success': False, 'error': 'Ungültiger Provider'})
        
        try:
            # Versuche API-Balance zu finden und Key zu entfernen
            api_balance = APIBalance.objects.get(user=request.user, provider=provider)
            api_balance.api_key = ''  # Leeren Key setzen
            api_balance.save()
            
            provider_name = dict(APIBalance.PROVIDER_CHOICES)[provider]
            
            return JsonResponse({
                'success': True,
                'message': f'API-Key für {provider_name} wurde entfernt'
            })
            
        except APIBalance.DoesNotExist:
            return JsonResponse({
                'success': True,  # Kein Fehler, Key war bereits nicht vorhanden
                'message': 'Kein API-Key zum Entfernen vorhanden'
            })
            
        except (OperationalError, ProgrammingError) as db_error:
            if "no such table" in str(db_error).lower():
                return JsonResponse({
                    'success': False, 
                    'error': 'API-Datenbank nicht initialisiert. Führen Sie "python manage.py migrate" aus.'
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': f'Datenbank-Fehler: {str(db_error)}'
                })
                
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_usage_statistics(request):
    """AJAX-View für Nutzungsstatistiken der letzten 30 Tage"""
    from django.utils import timezone
    from datetime import timedelta
    
    # Datum vor 30 Tagen
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Hole Nutzungsstatistiken
    usage_logs = APIUsageLog.objects.filter(
        user=request.user,
        created_at__gte=thirty_days_ago
    ).order_by('-created_at')
    
    # Gruppiere nach Provider
    stats = {}
    total_cost = 0
    
    for provider_key, provider_name in APIBalance.PROVIDER_CHOICES:
        provider_logs = usage_logs.filter(provider=provider_key)
        provider_cost = sum(float(log.estimated_cost) for log in provider_logs)
        provider_tokens = sum(log.total_tokens for log in provider_logs)
        
        stats[provider_key] = {
            'name': provider_name,
            'total_cost': provider_cost,
            'total_tokens': provider_tokens,
            'request_count': provider_logs.count(),
            'last_used': provider_logs.first().created_at.isoformat() if provider_logs.exists() else None
        }
        
        total_cost += provider_cost
    
    return JsonResponse({
        'success': True,
        'period': '30 Tage',
        'total_cost': total_cost,
        'stats': stats
    })


def log_api_usage(user, model_name, prompt_text, response_text, training=None):
    """Protokolliert API-Nutzung für Kostentracking"""
    try:
        from django.db import OperationalError, ProgrammingError
        
        # Schätze Token-Anzahl
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens
        
        # Berechne Kosten
        estimated_cost = calculate_cost(model_name, prompt_tokens, completion_tokens)
        
        # Ermittle Provider
        provider = get_provider_from_model(model_name)
        
        if provider:
            try:
                # Erstelle Log-Eintrag
                APIUsageLog.objects.create(
                    user=user,
                    provider=provider,
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=estimated_cost,
                    training=training
                )
                
                # Aktualisiere Kontostand (falls vorhanden)
                try:
                    api_balance = APIBalance.objects.get(user=user, provider=provider)
                    api_balance.balance -= estimated_cost
                    api_balance.save()
                    
                    print(f"💰 Kostentracking: {model_name} - ${estimated_cost} (Neuer Kontostand: ${api_balance.balance})")
                    
                except APIBalance.DoesNotExist:
                    print(f"💰 Kostentracking: {model_name} - ${estimated_cost} (Kein Kontostand konfiguriert)")
                    
            except (OperationalError, ProgrammingError) as db_error:
                if "no such table" in str(db_error).lower():
                    print(f"⚠️  API-Tabellen nicht vorhanden - Führen Sie 'python manage.py migrate' aus")
                    print(f"💰 Kostentracking (offline): {model_name} - ${estimated_cost} für {user.username}")
                else:
                    print(f"❌ Datenbank-Fehler beim API-Logging: {db_error}")
                
    except Exception as e:
        print(f"❌ Fehler beim Protokollieren der API-Nutzung: {e}")


@login_required
def estimate_training_cost(request):
    """AJAX-View zur Kostenschätzung für eine Schulungserstellung"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Requests erlaubt'})
    
    try:
        model_name = request.POST.get('model_name')
        company_info = request.POST.get('company_info', '')
        learning_goals = request.POST.get('learning_goals', '')
        training_description = request.POST.get('training_description', '')
        
        if not model_name:
            return JsonResponse({'success': False, 'error': 'Modellname erforderlich'})
        
        # Schätze Prompt-Länge (Firmeninfos + Lernziele + Beschreibung + Template)
        template_length = 8000  # Grobe Schätzung für den Template-Prompt
        prompt_text = company_info + learning_goals + training_description
        estimated_prompt_tokens = estimate_tokens(prompt_text) + template_length
        
        # Schätze Response-Länge (ca. 15.000 Zeichen für eine vollständige Schulung)
        estimated_response_tokens = estimate_tokens("x" * 15000)
        
        # Berechne geschätzte Kosten
        estimated_cost = calculate_cost(model_name, estimated_prompt_tokens, estimated_response_tokens)
        
        # Hole Modellinformationen
        model_info = get_model_info(model_name)
        
        return JsonResponse({
            'success': True,
            'model_name': model_name,
            'estimated_cost': float(estimated_cost),
            'estimated_prompt_tokens': estimated_prompt_tokens,
            'estimated_response_tokens': estimated_response_tokens,
            'model_info': model_info
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_settings_view(request):
    """Zeigt die API-Einstellungsseite an"""
    return render(request, 'accounts/api_settings.html')


@login_required
def validate_api_key(request):
    """AJAX-View zum Validieren eines API-Schlüssels"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    provider = request.POST.get('provider')
    api_key = request.POST.get('api_key', '').strip()
    
    if not provider or not api_key:
        return JsonResponse({'success': False, 'error': 'Provider und API-Key sind erforderlich'})
    
    # Validiere API-Key je nach Provider
    is_valid, error_message = test_api_key(provider, api_key)
    
    return JsonResponse({
        'success': True,
        'is_valid': is_valid,
        'provider': provider,
        'error_message': error_message
    })


def test_api_key(provider, api_key):
    """
    Testet einen API-Schlüssel durch einen einfachen API-Aufruf
    
    Args:
        provider: str - 'openai', 'anthropic', 'google', oder 'youtube'
        api_key: str - Der zu testende API-Schlüssel
    
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    try:
        if provider == 'openai':
            return test_openai_key(api_key)
        elif provider == 'anthropic':
            return test_anthropic_key(api_key)
        elif provider == 'google':
            return test_google_key(api_key)
        elif provider == 'youtube':
            return test_youtube_key(api_key)
        else:
            return False, f"Unbekannter Provider: {provider}"
    except Exception as e:
        return False, f"Validierungsfehler: {str(e)}"


def test_openai_key(api_key):
    """Testet OpenAI API-Schlüssel"""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # Einfacher Test-Call zu Models-Endpoint
        response = client.models.list()
        if response and hasattr(response, 'data'):
            return True, "API-Schlüssel ist gültig"
        else:
            return False, "Ungültige API-Antwort"
    except Exception as e:
        error_msg = str(e)
        if "Incorrect API key" in error_msg or "invalid api key" in error_msg.lower():
            return False, "Ungültiger API-Schlüssel"
        elif "exceeded your current quota" in error_msg.lower():
            return True, "API-Schlüssel gültig (Quota überschritten)"
        else:
            return False, f"API-Fehler: {error_msg}"


def test_anthropic_key(api_key):
    """Testet Anthropic API-Schlüssel"""
    try:
        import requests
        
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        # Test mit einer minimalen Nachricht
        data = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 10,
            'messages': [
                {'role': 'user', 'content': 'Hi'}
            ]
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "API-Schlüssel ist gültig"
        elif response.status_code == 401:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 429:
            return True, "API-Schlüssel gültig (Rate Limit erreicht)"
        else:
            return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


def test_google_key(api_key):
    """Testet Google AI API-Schlüssel"""
    try:
        import requests
        
        # Test mit Gemini-API
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'models' in data:
                return True, "API-Schlüssel ist gültig"
            else:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 400:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 403:
            return False, "API-Schlüssel ohne Berechtigung"
        else:
            return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


def test_youtube_key(api_key):
    """Testet YouTube Data API-Schlüssel"""
    try:
        import requests
        
        # Test mit YouTube API
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=1&q=test&key={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data:
                return True, "API-Schlüssel ist gültig"
            else:
                return False, "Ungültige API-Antwort"
        elif response.status_code == 400:
            return False, "Ungültiger API-Schlüssel"
        elif response.status_code == 403:
            return False, "API-Schlüssel gesperrt oder ohne Berechtigung"
        else:
            return False, f"API-Fehler: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Verbindungsfehler: {str(e)}"


@login_required
def save_inhaltsverzeichnis(request, thema_id):
    """Speichert das bearbeitete Inhaltsverzeichnis"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST-Anfragen erlaubt'})
    
    try:
        thema = get_object_or_404(Thema, id=thema_id)
        content = request.POST.get('content', '').strip()
        
        # Finde den passenden Ordner im Trainings-Verzeichnis
        trainings_path = os.path.join(settings.MEDIA_ROOT, 'naturmacher', 'trainings')
        if not os.path.exists(trainings_path):
            return JsonResponse({'success': False, 'error': 'Trainings-Verzeichnis nicht gefunden'})
        
        # Suche nach einem Ordner, der den Thema-Namen enthält
        target_folder = None
        for folder_name in os.listdir(trainings_path):
            folder_path = os.path.join(trainings_path, folder_name)
            if os.path.isdir(folder_path) and thema.name in folder_name:
                target_folder = folder_path
                break
        
        if not target_folder:
            return JsonResponse({'success': False, 'error': 'Ordner für dieses Thema nicht gefunden'})
        
        # Inhaltsverzeichnis-Datei speichern
        inhaltsverzeichnis_path = os.path.join(target_folder, 'inhaltsverzeichnis.txt')
        
        # Backup erstellen falls die Datei bereits existiert
        if os.path.exists(inhaltsverzeichnis_path):
            backup_path = inhaltsverzeichnis_path + '.backup'
            import shutil
            shutil.copy2(inhaltsverzeichnis_path, backup_path)
        
        # Neue Inhalte schreiben
        with open(inhaltsverzeichnis_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return JsonResponse({
            'success': True, 
            'message': 'Inhaltsverzeichnis erfolgreich gespeichert'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


