"""
Ad Creation Wizard Views
Schritt-für-Schritt Assistent für die Erstellung von Werbekampagnen
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    AdWizardDraft, AppCampaign, AppAdvertisement, AdZone,
    AutoCampaignFormat
)
from accounts.models import UserAppPermission


@login_required
def wizard_start(request):
    """
    Startpunkt des Wizards
    Erstellt oder lädt einen Draft
    """
    # Prüfe ob es bereits einen aktiven Draft gibt
    active_draft = AdWizardDraft.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    if active_draft and not active_draft.is_expired():
        # Weiter mit bestehendem Draft
        return redirect('loomads:wizard_step',
                       draft_id=active_draft.id,
                       step=active_draft.current_step)

    # Neuen Draft erstellen
    expires_at = timezone.now() + timedelta(days=7)  # 7 Tage Gültigkeit
    draft = AdWizardDraft.objects.create(
        user=request.user,
        current_step='app_selection',
        expires_at=expires_at
    )

    return redirect('loomads:wizard_step', draft_id=draft.id, step='app_selection')


@login_required
def wizard_step(request, draft_id, step):
    """
    Haupt-View für alle Wizard-Schritte
    """
    draft = get_object_or_404(AdWizardDraft, id=draft_id, user=request.user)

    # Prüfe ob Draft abgelaufen ist
    if draft.is_expired():
        messages.error(request, 'Dieser Entwurf ist abgelaufen. Bitte starten Sie neu.')
        return redirect('loomads:wizard_start')

    # Route zu entsprechendem Step-Handler
    step_handlers = {
        'app_selection': handle_app_selection,
        'campaign_details': handle_campaign_details,
        'format_selection': handle_format_selection,
        'creative_upload': handle_creative_upload,
        'review': handle_review,
    }

    handler = step_handlers.get(step)
    if not handler:
        messages.error(request, 'Ungültiger Schritt. Der Wizard wurde zurückgesetzt.')
        # Setze current_step auf gültigen Wert zurück
        draft.current_step = 'app_selection'
        draft.save(update_fields=['current_step'])
        return redirect('loomads:wizard_step', draft_id=draft.id, step='app_selection')

    return handler(request, draft)


def handle_app_selection(request, draft):
    """
    Schritt 1: App-Auswahl
    """
    # Filtere Apps basierend auf User-Berechtigungen
    # Nur Apps anzeigen, die für normale User sichtbar sind
    allowed_app_choices = [
        (app_code, app_name)
        for app_code, app_name in AppCampaign.APP_CHOICES
        if UserAppPermission.user_can_see_app_in_frontend(app_code, request.user)
    ]

    if request.method == 'POST':
        selected_app = request.POST.get('selected_app')

        if not selected_app:
            messages.error(request, 'Bitte wählen Sie eine App aus.')
            return render(request, 'loomads/wizard/step_app_selection.html', {
                'draft': draft,
                'app_choices': allowed_app_choices,
            })

        # Speichere Auswahl
        draft.selected_app = selected_app
        draft.save(update_fields=['selected_app'])  # ← WICHTIG: Feld speichern!

        step_data = {
            'app': selected_app,
            'app_display': dict(AppCampaign.APP_CHOICES).get(selected_app, selected_app)
        }
        draft.update_wizard_data(step_data)

        # Weiter zum nächsten Schritt
        draft.advance_to_next_step()
        return redirect('loomads:wizard_step', draft_id=draft.id, step=draft.current_step)

    # GET: Zeige App-Auswahl
    # Lade verfügbare Zonen pro App für Info (nur für erlaubte Apps)
    app_zone_counts = {}
    for app_code, app_name in allowed_app_choices:
        zones = AdZone.objects.filter(
            is_active=True,
            code__icontains=app_code
        )
        app_zone_counts[app_code] = zones.count()

    context = {
        'draft': draft,
        'app_choices': allowed_app_choices,
        'app_zone_counts': app_zone_counts,
        'progress': draft.get_progress_percentage(),
    }

    return render(request, 'loomads/wizard/step_app_selection.html', context)


def handle_campaign_details(request, draft):
    """
    Schritt 2: Kampagnen-Details (Name, Beschreibung, Zeitraum, Budget)
    """
    if request.method == 'POST':
        campaign_name = request.POST.get('campaign_name', '').strip()
        campaign_description = request.POST.get('campaign_description', '').strip()
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        priority = request.POST.get('priority', 3)
        daily_impression_limit = request.POST.get('daily_impression_limit', '')

        # Validierung
        errors = []
        if not campaign_name:
            errors.append('Kampagnenname ist erforderlich.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'loomads/wizard/step_campaign_details.html', {
                'draft': draft,
                'progress': draft.get_progress_percentage(),
                'priority_choices': AppCampaign.PRIORITY_CHOICES,
            })

        # Speichere Daten
        draft.campaign_name = campaign_name
        draft.campaign_description = campaign_description
        draft.save(update_fields=['campaign_name', 'campaign_description'])  # ← WICHTIG: Felder speichern!

        step_data = {
            'name': campaign_name,
            'description': campaign_description,
            'start_date': start_date,
            'end_date': end_date,
            'priority': int(priority),
            'daily_impression_limit': int(daily_impression_limit) if daily_impression_limit else None,
        }
        draft.update_wizard_data(step_data)

        # Weiter
        draft.advance_to_next_step()
        return redirect('loomads:wizard_step', draft_id=draft.id, step=draft.current_step)

    # GET
    # Lade bereits gespeicherte Daten falls vorhanden
    saved_data = draft.get_step_data('campaign_details')

    context = {
        'draft': draft,
        'saved_data': saved_data,
        'progress': draft.get_progress_percentage(),
        'priority_choices': AppCampaign.PRIORITY_CHOICES,
    }

    return render(request, 'loomads/wizard/step_campaign_details.html', context)


def handle_format_selection(request, draft):
    """
    Schritt 3: Format-Auswahl
    Zeigt verfügbare Formate für die gewählte App
    """
    app_code = draft.selected_app
    if not app_code:
        messages.error(request, 'App-Auswahl fehlt.')
        return redirect('loomads:wizard_step', draft_id=draft.id, step='app_selection')

    # Lade alle Zonen für diese App
    zones = AdZone.objects.filter(
        is_active=True,
        code__icontains=app_code
    ).order_by('zone_type', 'width', 'height')

    # Gruppiere nach Dimensionen
    format_groups = {}
    for zone in zones:
        dimension_key = f"{zone.width}x{zone.height}"
        if dimension_key not in format_groups:
            format_groups[dimension_key] = {
                'dimension': dimension_key,
                'width': zone.width,
                'height': zone.height,
                'zones': [],
                'zone_types': set(),
            }
        format_groups[dimension_key]['zones'].append(zone)
        format_groups[dimension_key]['zone_types'].add(zone.get_zone_type_display())

    # Konvertiere zu Liste
    formats = list(format_groups.values())
    for fmt in formats:
        fmt['zone_types'] = ', '.join(sorted(fmt['zone_types']))
        fmt['zone_count'] = len(fmt['zones'])

    if request.method == 'POST':
        selected_formats = request.POST.getlist('selected_formats')

        if not selected_formats:
            messages.error(request, 'Bitte wählen Sie mindestens ein Format aus.')
            return render(request, 'loomads/wizard/step_format_selection.html', {
                'draft': draft,
                'formats': formats,
                'progress': draft.get_progress_percentage(),
            })

        # Speichere ausgewählte Formate
        selected_formats_data = []
        for dim_key in selected_formats:
            if dim_key in format_groups:
                fmt = format_groups[dim_key]
                selected_formats_data.append({
                    'dimension': dim_key,
                    'width': fmt['width'],
                    'height': fmt['height'],
                    'zone_count': len(fmt['zones']),
                    'zone_codes': [z.code for z in fmt['zones']],
                })

        step_data = {
            'selected_formats': selected_formats_data
        }
        draft.update_wizard_data(step_data)

        # Weiter
        draft.advance_to_next_step()
        return redirect('loomads:wizard_step', draft_id=draft.id, step=draft.current_step)

    # GET
    saved_data = draft.get_step_data('format_selection')
    selected_dimensions = []
    if saved_data and 'selected_formats' in saved_data:
        selected_dimensions = [fmt['dimension'] for fmt in saved_data['selected_formats']]

    context = {
        'draft': draft,
        'formats': formats,
        'selected_dimensions': selected_dimensions,
        'progress': draft.get_progress_percentage(),
        'app_display': dict(AppCampaign.APP_CHOICES).get(app_code, app_code),
    }

    return render(request, 'loomads/wizard/step_format_selection.html', context)


def handle_creative_upload(request, draft):
    """
    Schritt 4: Creative-Upload
    Upload von Bildern/Videos für jedes gewählte Format
    """
    format_data = draft.get_step_data('format_selection')
    if not format_data or 'selected_formats' not in format_data:
        messages.error(request, 'Format-Auswahl fehlt.')
        return redirect('loomads:wizard_step', draft_id=draft.id, step='format_selection')

    selected_formats = format_data['selected_formats']

    if request.method == 'POST':
        # Speichere hochgeladene Creatives
        uploaded_creatives = {}

        for fmt in selected_formats:
            dim = fmt['dimension']
            field_name = f'creative_{dim}'

            # Prüfe ob Datei hochgeladen wurde
            if field_name in request.FILES:
                uploaded_file = request.FILES[field_name]

                # Speichere Datei (temporär in Draft-Daten)
                # In Production würde man hier die Datei speichern und URL zurückgeben
                uploaded_creatives[dim] = {
                    'filename': uploaded_file.name,
                    'size': uploaded_file.size,
                    'content_type': uploaded_file.content_type,
                    # TODO: Speichere tatsächliche Datei
                }

            # Alternativ: URL eingegeben
            url_field = f'creative_url_{dim}'
            if url_field in request.POST and request.POST[url_field]:
                uploaded_creatives[dim] = {
                    'type': 'url',
                    'url': request.POST[url_field]
                }

        # Validierung: Mindestens ein Creative muss vorhanden sein
        if not uploaded_creatives:
            messages.error(request, 'Bitte laden Sie mindestens ein Creative hoch.')
            return render(request, 'loomads/wizard/step_creative_upload.html', {
                'draft': draft,
                'formats': selected_formats,
                'progress': draft.get_progress_percentage(),
            })

        # Speichere
        step_data = {
            'creatives': uploaded_creatives
        }
        draft.update_wizard_data(step_data)

        # Weiter zur Review
        draft.advance_to_next_step()
        return redirect('loomads:wizard_step', draft_id=draft.id, step=draft.current_step)

    # GET
    saved_data = draft.get_step_data('creative_upload')
    uploaded_creatives = saved_data.get('creatives', {}) if saved_data else {}

    context = {
        'draft': draft,
        'formats': selected_formats,
        'uploaded_creatives': uploaded_creatives,
        'progress': draft.get_progress_percentage(),
    }

    return render(request, 'loomads/wizard/step_creative_upload.html', context)


def handle_review(request, draft):
    """
    Schritt 5: Review & Publish
    Zeigt Zusammenfassung und erstellt finale Kampagne
    """
    # Sammle alle Daten
    app_data = draft.get_step_data('app_selection')
    campaign_data = draft.get_step_data('campaign_details')
    format_data = draft.get_step_data('format_selection')
    creative_data = draft.get_step_data('creative_upload')

    # Validiere dass alle Daten vorhanden sind
    if not all([app_data, campaign_data, format_data, creative_data]):
        messages.error(request, 'Einige Schritte sind unvollständig. Bitte überprüfen Sie Ihre Eingaben.')
        return redirect('loomads:wizard_step', draft_id=draft.id, step='app_selection')

    if request.method == 'POST':
        # Erstelle finale Kampagne
        try:
            # Setze start_date auf "jetzt" wenn leer
            start_date = campaign_data.get('start_date')
            if not start_date:
                start_date = timezone.now()

            # end_date kann NULL bleiben für "unbegrenzt"
            end_date = campaign_data.get('end_date') or None

            # 1. Erstelle App-Campaign
            campaign = AppCampaign.objects.create(
                name=campaign_data['name'],
                description=campaign_data['description'],
                app_target=draft.selected_app,
                created_by=request.user,
                status='draft',  # Startet als Entwurf
                priority=campaign_data['priority'],
                start_date=start_date,
                end_date=end_date,
                daily_impression_limit=campaign_data.get('daily_impression_limit'),
            )

            # 2. Erstelle App-Advertisements für jedes Format
            for fmt in format_data['selected_formats']:
                dim = fmt['dimension']
                creative_info = creative_data['creatives'].get(dim)

                if not creative_info:
                    continue

                # Erstelle Advertisement
                ad = AppAdvertisement.objects.create(
                    app_campaign=campaign,
                    name=f"{campaign.name} - {dim}",
                    description=f"Creative für Format {dim}",
                    ad_type='image',  # Default, kann später angepasst werden
                    link_url='#',  # TODO: Aus Formular holen
                    is_active=True,
                )

                # Weise Zonen zu
                zone_codes = fmt['zone_codes']
                zones = AdZone.objects.filter(code__in=zone_codes)
                ad.zones.set(zones)

            # 3. Draft als abgeschlossen markieren
            draft.is_active = False
            draft.save()

            messages.success(request, f'Kampagne "{campaign.name}" wurde erfolgreich erstellt!')
            return redirect('loomads:app_campaign_detail', campaign_id=campaign.id)

        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen der Kampagne: {str(e)}')

    # GET: Zeige Review
    context = {
        'draft': draft,
        'app_data': app_data,
        'campaign_data': campaign_data,
        'format_data': format_data,
        'creative_data': creative_data,
        'progress': 100,  # Review ist letzter Schritt
    }

    return render(request, 'loomads/wizard/step_review.html', context)


@login_required
def wizard_cancel(request, draft_id):
    """
    Wizard abbrechen und Draft löschen
    Nur via POST erlaubt
    """
    draft = get_object_or_404(AdWizardDraft, id=draft_id, user=request.user)

    # Nur bei POST löschen
    if request.method == 'POST':
        draft.delete()
        messages.info(request, 'Wizard wurde abgebrochen.')
        return redirect('loomads:dashboard')

    # Bei GET: Zurück zum Dashboard (verhindert Redirect-Loop bei ungültigem current_step)
    messages.warning(request, 'Bitte verwenden Sie den Abbrechen-Button im Wizard.')
    return redirect('loomads:dashboard')


@login_required
def wizard_list_drafts(request):
    """
    Zeigt alle aktiven Drafts des Users
    """
    drafts = AdWizardDraft.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-updated_at')

    context = {
        'drafts': drafts,
    }

    return render(request, 'loomads/wizard/draft_list.html', context)
