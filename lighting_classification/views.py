from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from .models import (
    RoadType, LightingClassification, ClassificationCriteria, ClassificationScoring,
    DINRoadCategory, DINLightingClassification, DINClassificationParameter,
    DINParameterChoice, DINSelectedParameterChoice
)
import json
import weasyprint
from io import BytesIO


@login_required
def index(view):
    """Hauptseite der Beleuchtungsklassifizierung"""
    recent_classifications = LightingClassification.objects.filter(
        user=view.user
    ).order_by('-created_at')[:5]

    context = {
        'recent_classifications': recent_classifications,
        'total_classifications': LightingClassification.objects.filter(user=view.user).count(),
    }
    return render(view, 'lighting_classification/index.html', context)


@login_required
def select_road_type(request):
    """Schritt 1: Straßentyp auswählen (DIN-konform)"""

    # Verwende DIN-konforme Kategorien
    din_categories = DINRoadCategory.objects.filter(is_active=True).order_by('table_number')

    # Icons für DIN-Kategorien
    category_icons = {
        'AS_3': 'fas fa-highway',
        'LS_4': 'fas fa-road',
        'HS_5': 'fas fa-road',
        'ES_6': 'fas fa-home',
        'ES_7': 'fas fa-home',
        'ES_8': 'fas fa-home',
        'RADWEG_9': 'fas fa-bicycle',
        'GEHWEG_10': 'fas fa-walking',
        'PLATZ_11': 'fas fa-square',
    }

    context = {
        'din_categories': din_categories,
        'category_icons': category_icons,
        'step': 1,
        'step_title': 'Straßentyp auswählen',
        'step_description': 'Wählen Sie den Straßentyp gemäß DIN 13201-1 aus',
    }

    return render(request, 'lighting_classification/select_road_type.html', context)


@login_required
@require_http_methods(["POST"])
def start_classification(request):
    """Startet eine neue DIN-konforme Klassifizierung"""

    print(f"POST data: {request.POST}")  # Debug
    din_category_id = request.POST.get('din_category_id')
    project_name = request.POST.get('project_name', '').strip()

    print(f"DIN Category ID: {din_category_id}")  # Debug
    print(f"Project Name: {project_name}")  # Debug

    if not din_category_id:
        messages.error(request, 'Bitte wählen Sie einen Straßentyp aus.')
        print("Error: No DIN category ID provided")  # Debug
        return redirect('lighting_classification:select_road_type')

    if not project_name:
        messages.error(request, 'Bitte geben Sie einen Projektnamen an.')
        print("Error: No project name provided")  # Debug
        return redirect('lighting_classification:select_road_type')

    try:
        din_category = DINRoadCategory.objects.get(id=din_category_id, is_active=True)
    except DINRoadCategory.DoesNotExist:
        messages.error(request, 'Der ausgewählte Straßentyp ist nicht gültig.')
        return redirect('lighting_classification:select_road_type')

    # Neue DIN-konforme Klassifizierung erstellen
    classification = DINLightingClassification.objects.create(
        user=request.user,
        project_name=project_name,
        road_category=din_category,
        status='draft'
    )

    messages.success(request, f'Klassifizierung "{project_name}" wurde gestartet.')
    return redirect('lighting_classification:configure_parameters', classification_id=classification.id)


@login_required
def configure_parameters(request, classification_id):
    """Schritt 2: DIN-konforme Parameter konfigurieren"""

    classification = get_object_or_404(
        DINLightingClassification,
        id=classification_id,
        user=request.user
    )

    if request.method == 'POST':
        try:
            # Parse selected parameter choices
            selected_choices_data = {}
            for key, value in request.POST.items():
                if key.startswith('param_'):
                    param_id = key.replace('param_', '')
                    choice_id = value
                    if param_id and choice_id:
                        selected_choices_data[int(param_id)] = int(choice_id)

            # Clear existing choices
            DINSelectedParameterChoice.objects.filter(classification=classification).delete()

            # Save selected choices
            total_vws = 0
            for param_id, choice_id in selected_choices_data.items():
                try:
                    parameter = DINClassificationParameter.objects.get(id=param_id)
                    choice = DINParameterChoice.objects.get(id=choice_id)

                    DINSelectedParameterChoice.objects.create(
                        classification=classification,
                        parameter=parameter,
                        choice=choice
                    )
                    total_vws += choice.weighting_value
                except (DINClassificationParameter.DoesNotExist, DINParameterChoice.DoesNotExist):
                    continue

            # Calculate lighting class using DIN formula
            calculated_class = classification.calculate_lighting_class()
            classification.status = 'completed'
            classification.save()

            messages.success(request, f'Parameter wurden gespeichert. VWS: {classification.total_weighting_value} → Beleuchtungsklasse: {classification.calculated_lighting_class}')
            return redirect('lighting_classification:view_result', classification_id=classification.id)

        except Exception as e:
            print(f"Error in configure_parameters: {e}")
            messages.error(request, f'Fehler beim Speichern der Parameter: {str(e)}')
            return redirect('lighting_classification:configure_parameters', classification_id=classification.id)

    # DIN-konforme Parameter für die gewählte Straßenkategorie laden
    parameters = classification.road_category.parameters.filter(is_active=True).order_by('order')

    context = {
        'classification': classification,
        'parameters': parameters,
        'step': 2,
        'step_title': 'Parameter konfigurieren',
        'step_description': f'Bewerten Sie die Parameter für {classification.road_category.name} nach DIN 13201-1',
    }

    return render(request, 'lighting_classification/configure_parameters.html', context)


@login_required
def view_result(request, classification_id):
    """Schritt 3: DIN-konformes Ergebnis anzeigen"""

    classification = get_object_or_404(
        DINLightingClassification,
        id=classification_id,
        user=request.user
    )

    # Zusätzliche Informationen zur Beleuchtungsklasse
    lighting_info = get_lighting_class_info(classification.calculated_lighting_class)

    # Ausgewählte Parameter laden
    selected_choices = classification.selected_choices.all()

    context = {
        'classification': classification,
        'lighting_info': lighting_info,
        'selected_choices': selected_choices,
        'step': 3,
        'step_title': 'Beleuchtungsklasse',
        'step_description': 'Empfohlene Beleuchtungsklasse nach DIN 13201-1',
    }

    return render(request, 'lighting_classification/view_result.html', context)


def get_lighting_class_info(lighting_class):
    """Zusätzliche Informationen zu Beleuchtungsklassen"""

    lighting_info_map = {
        'M1': {
            'description': 'Höchste Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Autobahnen mit hoher Verkehrsdichte',
            'requirements': 'Leuchtdichte: 2,0 cd/m², Gleichmäßigkeit: 0,4'
        },
        'M2': {
            'description': 'Hohe Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Kraftfahrstraßen, überörtliche Hauptstraßen',
            'requirements': 'Leuchtdichte: 1,5 cd/m², Gleichmäßigkeit: 0,4'
        },
        'M3': {
            'description': 'Mittlere Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Hauptverkehrsstraßen in Ortschaften',
            'requirements': 'Leuchtdichte: 1,0 cd/m², Gleichmäßigkeit: 0,4'
        },
        'M4': {
            'description': 'Standard Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Sammelstraßen, Verbindungsstraßen',
            'requirements': 'Leuchtdichte: 0,75 cd/m², Gleichmäßigkeit: 0,4'
        },
        'M5': {
            'description': 'Niedrige Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Erschließungsstraßen, Wohngebiete',
            'requirements': 'Leuchtdichte: 0,5 cd/m², Gleichmäßigkeit: 0,4'
        },
        'M6': {
            'description': 'Niedrigste Beleuchtungsklasse für Kraftfahrzeugverkehr',
            'application': 'Anliegerstraßen, verkehrsberuhigte Bereiche',
            'requirements': 'Leuchtdichte: 0,3 cd/m², Gleichmäßigkeit: 0,4'
        },
        'P1': {
            'description': 'Höchste Beleuchtungsklasse für Fußgänger/Radfahrer',
            'application': 'Hauptfußgängerwege, wichtige Radrouten',
            'requirements': 'Beleuchtungsstärke: 15 lx, Gleichmäßigkeit: 0,4'
        },
        'P3': {
            'description': 'Mittlere Beleuchtungsklasse für Fußgänger/Radfahrer',
            'application': 'Normale Fußgänger- und Radwege',
            'requirements': 'Beleuchtungsstärke: 7,5 lx, Gleichmäßigkeit: 0,4'
        },
        'P5': {
            'description': 'Niedrige Beleuchtungsklasse für Fußgänger/Radfahrer',
            'application': 'Wenig genutzte Wege',
            'requirements': 'Beleuchtungsstärke: 3 lx, Gleichmäßigkeit: 0,4'
        },
        'A1': {
            'description': 'Höchste Beleuchtungsklasse für Konfliktbereiche',
            'application': 'Zebrastreifen, wichtige Kreuzungen',
            'requirements': 'Beleuchtungsstärke: 15 lx, Gleichmäßigkeit: 0,4'
        },
        'A3': {
            'description': 'Mittlere Beleuchtungsklasse für Konfliktbereiche',
            'application': 'Normale Konfliktbereiche',
            'requirements': 'Beleuchtungsstärke: 7,5 lx, Gleichmäßigkeit: 0,4'
        },
    }

    return lighting_info_map.get(lighting_class, {
        'description': 'Unbekannte Beleuchtungsklasse',
        'application': 'Siehe DIN EN 13201',
        'requirements': 'Siehe Norm'
    })


@login_required
def download_pdf(request, classification_id):
    """PDF-Download der Klassifizierungsergebnisse"""

    classification = get_object_or_404(
        LightingClassification,
        id=classification_id,
        user=request.user
    )

    # Zusätzliche Informationen zur Beleuchtungsklasse
    lighting_info = get_lighting_class_info(classification.recommended_class)

    # Parse selected criteria from notes
    selected_criteria = []
    if classification.notes:
        try:
            notes_data = json.loads(classification.notes)
            selected_criteria = list(notes_data.get('selected_criteria', {}).keys())
        except (json.JSONDecodeError, AttributeError):
            selected_criteria = []

    # Context für PDF-Template
    context = {
        'classification': classification,
        'lighting_info': lighting_info,
        'selected_criteria': selected_criteria,
    }

    # HTML-Template rendern
    html_string = render_to_string('lighting_classification/pdf_report.html', context)

    # PDF generieren
    try:
        # WeasyPrint HTML zu PDF konvertieren
        html = weasyprint.HTML(string=html_string)
        pdf_file = BytesIO()
        html.write_pdf(pdf_file)

        # PDF als Download-Response zurückgeben
        pdf_file.seek(0)
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')

        # Dateiname generieren
        filename = f'DIN_EN_13201_Klassifizierung_{classification.project_name}_{classification.created_at.strftime("%Y%m%d")}.pdf'
        # Sonderzeichen für Dateinamen entfernen
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ").replace(" ", "_")

        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Fehler beim Generieren der PDF: {str(e)}')
        return redirect('lighting_classification:view_result', classification_id=classification.id)
