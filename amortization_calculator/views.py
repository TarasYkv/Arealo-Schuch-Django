# amortization_calculator/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from accounts.decorators import require_app_permission
from .models import LightingCalculation
from .forms import (
    Step1ProjectDataForm,
    Step2ExistingSystemForm,
    Step3NewSystemForm,
    Step4LimasForm,
    Step4MotionSensorForm,
    Step4DaylightForm,
    Step4CalendarForm
)
from .calculation_service import LightingCalculationService
import json


@require_app_permission('wirtschaftlichkeitsrechner')
def wizard_step1(request, calc_id=None):
    """
    Schritt 1: Projektdaten
    """
    calculation = None
    if calc_id:
        calculation = get_object_or_404(LightingCalculation, id=calc_id)

    if request.method == 'POST':
        form = Step1ProjectDataForm(request.POST, instance=calculation)
        if form.is_valid():
            calculation = form.save(commit=False)
            if request.user.is_authenticated:
                calculation.user = request.user
            calculation.save()

            # Session speichern für Navigation
            request.session['calc_id'] = calculation.id

            # Wenn Bestandsanlage vorhanden, zu Schritt 2
            if calculation.neue_anlage_vorhanden:
                return redirect('amortization_calculator:wizard_step2', calc_id=calculation.id)
            else:
                # Sonst direkt zu Schritt 3
                return redirect('amortization_calculator:wizard_step3', calc_id=calculation.id)
    else:
        form = Step1ProjectDataForm(instance=calculation)

    project_list = []
    if request.user.is_authenticated:
        project_list = (
            LightingCalculation.objects
            .filter(user=request.user)
            .order_by('-updated_at')
        )

    context = {
        'form': form,
        'step': 1,
        'total_steps': 5,
        'calculation': calculation,
        'page_title': 'Schritt 1: Projektdaten',
        'project_list': project_list,
    }
    return render(request, 'amortization_calculator/wizard/step1.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def wizard_step2(request, calc_id):
    """
    Schritt 2: Bestandsanlage
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    # Nur wenn Bestandsanlage vorhanden
    if not calculation.neue_anlage_vorhanden:
        return redirect('amortization_calculator:wizard_step3', calc_id=calc_id)

    if request.method == 'POST':
        form = Step2ExistingSystemForm(request.POST, instance=calculation)
        if form.is_valid():
            calculation = form.save()
            return redirect('amortization_calculator:wizard_step3', calc_id=calculation.id)
    else:
        form = Step2ExistingSystemForm(instance=calculation)

    context = {
        'form': form,
        'step': 2,
        'total_steps': 5,
        'calculation': calculation,
        'page_title': 'Schritt 2: Bestandsanlage'
    }
    return render(request, 'amortization_calculator/wizard/step2.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def wizard_step3(request, calc_id):
    """
    Schritt 3: Neue Anlage
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    if request.method == 'POST':
        form = Step3NewSystemForm(request.POST, instance=calculation)
        if form.is_valid():
            calculation = form.save()
            return redirect('amortization_calculator:wizard_step4', calc_id=calculation.id)
    else:
        form = Step3NewSystemForm(instance=calculation)

    context = {
        'form': form,
        'step': 3,
        'total_steps': 5,
        'calculation': calculation,
        'page_title': 'Schritt 3: Neue LED-Anlage'
    }
    return render(request, 'amortization_calculator/wizard/step3.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def wizard_step4(request, calc_id):
    """
    Schritt 4: Lichtmanagementsystem (LMS)
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    if request.method == 'POST':
        # Alle Forms gleichzeitig verarbeiten
        lms_form = Step4LimasForm(request.POST, instance=calculation, prefix='lms')
        motion_form = Step4MotionSensorForm(request.POST, instance=calculation, prefix='motion')
        daylight_form = Step4DaylightForm(request.POST, instance=calculation, prefix='daylight')
        calendar_form = Step4CalendarForm(request.POST, instance=calculation, prefix='calendar')

        all_valid = all([
            lms_form.is_valid(),
            motion_form.is_valid(),
            daylight_form.is_valid(),
            calendar_form.is_valid()
        ])

        if all_valid:
            # Speichern ohne Commit
            lms_form.save(commit=False)
            motion_form.save(commit=False)
            daylight_form.save(commit=False)
            calendar_form.save(commit=False)

            # Finale Speicherung mit Berechnungen
            calculation.save()

            return redirect('amortization_calculator:wizard_results', calc_id=calculation.id)
    else:
        lms_form = Step4LimasForm(instance=calculation, prefix='lms')
        motion_form = Step4MotionSensorForm(instance=calculation, prefix='motion')
        daylight_form = Step4DaylightForm(instance=calculation, prefix='daylight')
        calendar_form = Step4CalendarForm(instance=calculation, prefix='calendar')

    context = {
        'lms_form': lms_form,
        'motion_form': motion_form,
        'daylight_form': daylight_form,
        'calendar_form': calendar_form,
        'step': 4,
        'total_steps': 5,
        'calculation': calculation,
        'page_title': 'Schritt 4: Lichtmanagementsystem'
    }
    return render(request, 'amortization_calculator/wizard/step4.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def wizard_results(request, calc_id):
    """
    Schritt 5: Ergebnisse
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    # Berechnungsservice für erweiterte Auswertungen
    service = LightingCalculationService(calculation)

    # Validierung durchführen
    is_valid, errors = service.validate_input()

    # Alle Emissionen berechnen
    emissions = service.get_all_emissions()

    # Kontext für Template vorbereiten
    context = {
        'calculation': calculation,
        'step': 5,
        'total_steps': 5,
        'page_title': 'Ergebnisse',
        'emissions': emissions,
        'validation_errors': errors if not is_valid else None,

        # Zusammenfassung der wichtigsten Kennzahlen
        'summary': {
            'ersparnis_gesamt': (calculation.ersparnis_neu_zu_alt_jahr or 0) + (calculation.ersparnis_lms_jahr or 0),
            'amortisation_gesamt': calculation.amortisation_neu_monate or 0,
            'co2_reduzierung': calculation.co2_ersparnis_kg_jahr or 0,
            'energie_reduzierung': (
                (calculation.verbrauch_alt_kwh_jahr or 0) -
                (calculation.verbrauch_neu_mit_lms_kwh_jahr or calculation.verbrauch_neu_ohne_lms_kwh_jahr or 0)
            ),
            'prozent_ersparnis': (
                ((calculation.kosten_alt_jahr or 0) -
                (calculation.kosten_neu_mit_lms_jahr or calculation.kosten_neu_ohne_lms_jahr or 0)) /
                (calculation.kosten_alt_jahr or 1) * 100
            ) if calculation.kosten_alt_jahr else 0,
        }
    }

    return render(request, 'amortization_calculator/wizard/results.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def calculation_list(request):
    """
    Übersicht aller Berechnungen
    """
    if request.user.is_authenticated:
        calculations = LightingCalculation.objects.filter(user=request.user).order_by('-created_at')
    else:
        calculations = LightingCalculation.objects.none()

    context = {
        'calculations': calculations,
        'page_title': 'Meine Berechnungen'
    }
    return render(request, 'amortization_calculator/calculation_list.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def calculation_delete(request, calc_id):
    """
    Berechnung löschen
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    # Nur eigene Berechnungen können gelöscht werden
    if calculation.user != request.user and request.user.is_authenticated:
        messages.error(request, "Sie können nur Ihre eigenen Berechnungen löschen.")
        return redirect('amortization_calculator:calculation_list')

    if request.method == 'POST':
        calculation.delete()
        messages.success(request, "Die Berechnung wurde erfolgreich gelöscht.")
        return redirect('amortization_calculator:calculation_list')

    context = {
        'calculation': calculation,
        'page_title': 'Berechnung löschen'
    }
    return render(request, 'amortization_calculator/calculation_confirm_delete.html', context)


@require_app_permission('wirtschaftlichkeitsrechner')
def calculation_duplicate(request, calc_id):
    """
    Berechnung duplizieren
    """
    original = get_object_or_404(LightingCalculation, id=calc_id)

    # Neue Instanz erstellen (ohne ID)
    calculation = LightingCalculation()

    # Alle Felder kopieren außer id und timestamps
    for field in original._meta.fields:
        if field.name not in ['id', 'created_at', 'updated_at']:
            setattr(calculation, field.name, getattr(original, field.name))

    # Neuen Namen vergeben
    calculation.projektname = f"{original.projektname} (Kopie)"
    if request.user.is_authenticated:
        calculation.user = request.user

    calculation.save()

    messages.success(request, "Die Berechnung wurde erfolgreich dupliziert.")
    return redirect('amortization_calculator:wizard_step1_edit', calc_id=calculation.id)


@require_app_permission('wirtschaftlichkeitsrechner')
def export_pdf(request, calc_id):
    """
    PDF-Export der Berechnung mit Charts und modernem Design
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    try:
        # Generate charts and create PDF
        from .utils.pdf_generator import generate_amortization_pdf
        pdf_response = generate_amortization_pdf(calculation)

        # Set filename with project name and date
        filename = f"Wirtschaftlichkeitsrechner_{calculation.projektname}_{calculation.created_at.strftime('%Y-%m-%d')}.pdf"
        pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return pdf_response

    except Exception as e:
        messages.error(request, f"Fehler beim PDF-Export: {str(e)}")
        return redirect('amortization_calculator:wizard_results', calc_id=calc_id)


@require_app_permission('wirtschaftlichkeitsrechner')
def export_detailed_pdf(request, calc_id):
    """
    PDF-Export mit detaillierter Erläuterung der Berechnungen
    """
    calculation = get_object_or_404(LightingCalculation, id=calc_id)

    try:
        from .utils.pdf_generator import generate_detailed_pdf
        pdf_response = generate_detailed_pdf(calculation)

        filename = f"Wirtschaftlichkeitsrechner_Erlaeuterung_{calculation.projektname}_{calculation.created_at.strftime('%Y-%m-%d')}.pdf"
        pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return pdf_response

    except Exception as e:
        messages.error(request, f"Fehler beim PDF-Export: {str(e)}")
        return redirect('amortization_calculator:wizard_results', calc_id=calc_id)


@require_app_permission('wirtschaftlichkeitsrechner')
def api_validate(request):
    """
    AJAX API für Live-Validierung
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        calc_id = data.get('calc_id')

        if calc_id:
            calculation = get_object_or_404(LightingCalculation, id=calc_id)
            service = LightingCalculationService(calculation)
            is_valid, errors = service.validate_input()

            return JsonResponse({
                'valid': is_valid,
                'errors': errors
            })

    return JsonResponse({'error': 'Invalid request'}, status=400)


# Kompatibilität mit alter URL-Struktur
@require_app_permission('wirtschaftlichkeitsrechner')
def rechner_start_view(request):
    """
    Startseite des Wirtschaftlichkeitsrechners
    Leitet zum Wizard weiter
    """
    return redirect('amortization_calculator:wizard_step1')
