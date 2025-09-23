from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from accounts.decorators import require_app_permission
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


@require_app_permission('din_13201')
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


@require_app_permission('din_13201')
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


@require_app_permission('din_13201')
def configure_parameters(request, classification_id):
    """Schritt 2: DIN-konforme Parameter konfigurieren"""

    classification = get_object_or_404(
        DINLightingClassification,
        id=classification_id,
        user=request.user
    )

    if request.method == 'POST':
        try:
            # Parse time period data if available
            time_period_data_json = request.POST.get('time_period_data')
            current_period = request.POST.get('current_period', 'dt0')

            if time_period_data_json:
                # Handle new time period format
                time_period_data = json.loads(time_period_data_json)
                print(f"Received time period data: {time_period_data}")

                # Process all time periods
                created_classifications = []

                for period, choices_data in time_period_data.items():
                    if not choices_data:  # Skip empty periods
                        continue

                    # Create or update classification for this time period
                    if period == 'dt0':
                        # Update the main classification
                        current_classification = classification
                        current_classification.time_period = period
                    else:
                        # Create adaptive classification for dt1/dt2
                        current_classification = DINLightingClassification.objects.create(
                            user=request.user,
                            project_name=f"{classification.project_name} ({period.upper()})",
                            road_category=classification.road_category,
                            time_period=period,
                            status='draft'
                        )
                        created_classifications.append(current_classification)

                    # Clear existing choices for this classification
                    DINSelectedParameterChoice.objects.filter(classification=current_classification).delete()

                    # Save selected choices for this period
                    for param_id_str, choice_id_str in choices_data.items():
                        try:
                            param_id = int(param_id_str)
                            choice_id = int(choice_id_str)

                            parameter = DINClassificationParameter.objects.get(id=param_id)
                            choice = DINParameterChoice.objects.get(id=choice_id)

                            DINSelectedParameterChoice.objects.create(
                                classification=current_classification,
                                parameter=parameter,
                                choice=choice
                            )
                        except (DINClassificationParameter.DoesNotExist, DINParameterChoice.DoesNotExist, ValueError):
                            continue

                    # Calculate lighting class for this period
                    current_classification.calculate_lighting_class()
                    current_classification.status = 'completed'
                    current_classification.save()

                # Main classification is now the base (dt0)
                classification.status = 'completed'
                classification.save()

                success_msg = f'Beleuchtungsklassen berechnet: {classification.calculated_lighting_class}'
                if created_classifications:
                    adaptive_classes = [c.calculated_lighting_class for c in created_classifications]
                    success_msg += f' (Adaptiv: {", ".join(adaptive_classes)})'

                messages.success(request, success_msg)

            else:
                # Fallback to old single-period format
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
                for param_id, choice_id in selected_choices_data.items():
                    try:
                        parameter = DINClassificationParameter.objects.get(id=param_id)
                        choice = DINParameterChoice.objects.get(id=choice_id)

                        DINSelectedParameterChoice.objects.create(
                            classification=classification,
                            parameter=parameter,
                            choice=choice
                        )
                    except (DINClassificationParameter.DoesNotExist, DINParameterChoice.DoesNotExist):
                        continue

                # Calculate lighting class using DIN formula
                classification.calculate_lighting_class()
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


@require_app_permission('din_13201')
def view_result(request, classification_id):
    """Schritt 3: DIN-konformes Ergebnis anzeigen"""

    classification = get_object_or_404(
        DINLightingClassification,
        id=classification_id,
        user=request.user
    )

    # Find related adaptive classifications
    base_project_name = classification.project_name.split(' (')[0]  # Remove (DT1), (DT2) suffixes
    related_classifications = DINLightingClassification.objects.filter(
        user=request.user,
        project_name__startswith=base_project_name,
        road_category=classification.road_category
    ).order_by('time_period')

    # Group classifications by time period
    time_period_classifications = {}
    for related_class in related_classifications:
        time_period_classifications[related_class.time_period] = related_class

    # Ensure we have the base classification (dt0)
    if classification.time_period != 'dt0' and 'dt0' in time_period_classifications:
        # If we're viewing a non-base classification, switch to base
        base_classification = time_period_classifications['dt0']
        classification = base_classification

    # Zusätzliche Informationen zur Beleuchtungsklasse
    lighting_info = get_lighting_class_info(classification.calculated_lighting_class)

    # Ausgewählte Parameter laden
    selected_choices = classification.selected_choices.all()

    # Calculate energy savings if adaptive classifications exist
    energy_savings = None
    if len(time_period_classifications) > 1:
        base_class_num = int(classification.calculated_lighting_class[1:])  # Extract number from M3, P2, etc.
        adaptive_classes = []
        for period in ['dt1', 'dt2']:
            if period in time_period_classifications:
                adaptive_class = time_period_classifications[period]
                adaptive_class_num = int(adaptive_class.calculated_lighting_class[1:])
                adaptive_classes.append(adaptive_class_num)

        if adaptive_classes:
            # Rough energy savings calculation: each class step = ~20% savings
            max_adaptive_class = max(adaptive_classes)
            class_difference = max_adaptive_class - base_class_num
            if class_difference > 0:
                energy_savings = min(class_difference * 20, 70)  # Max 70% savings

    context = {
        'classification': classification,
        'lighting_info': lighting_info,
        'selected_choices': selected_choices,
        'time_period_classifications': time_period_classifications,
        'energy_savings': energy_savings,
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

    # Fallback für nicht explizit definierte Klassen
    if lighting_class not in lighting_info_map:
        # Versuche, Klasse zu parsen (z.B. M7, P6, etc.)
        if len(lighting_class) >= 2:
            class_type = lighting_class[0]  # M, P, A, etc.
            class_number = lighting_class[1:]

            if class_type == 'M':
                return {
                    'description': f'Beleuchtungsklasse {lighting_class} für Kraftfahrzeugverkehr',
                    'application': 'Straßenbeleuchtung nach DIN 13201-1:2021-09',
                    'requirements': 'Siehe DIN 13201-2:2015-11 für spezifische Werte'
                }
            elif class_type == 'P':
                return {
                    'description': f'Beleuchtungsklasse {lighting_class} für Fußgänger/Radfahrer',
                    'application': 'Wege für Fußgänger und Radfahrer',
                    'requirements': 'Siehe DIN 13201-2:2015-11 für spezifische Werte'
                }
            elif class_type == 'A':
                return {
                    'description': f'Beleuchtungsklasse {lighting_class} für Konfliktbereiche',
                    'application': 'Kreuzungen und Konfliktpunkte',
                    'requirements': 'Siehe DIN 13201-2:2015-11 für spezifische Werte'
                }
            elif class_type == 'C':
                return {
                    'description': f'Beleuchtungsklasse {lighting_class} für Konfliktbereiche',
                    'application': 'Verkehrskonfliktzonen nach DIN 13201-1:2021-09',
                    'requirements': 'Siehe DIN 13201-2:2015-11 für spezifische Werte'
                }

    return lighting_info_map.get(lighting_class, {
        'description': f'Beleuchtungsklasse {lighting_class}',
        'application': 'Nach DIN 13201-1:2021-09 klassifiziert',
        'requirements': 'Siehe DIN 13201-2:2015-11 für Wartungswerte'
    })


@require_app_permission('din_13201')
def download_pdf(request, classification_id):
    """PDF-Download der DIN 13201-1 Klassifizierungsergebnisse"""

    # DIN-konformes Modell verwenden
    classification = get_object_or_404(
        DINLightingClassification,
        id=classification_id,
        user=request.user
    )

    # Zusätzliche Informationen zur Beleuchtungsklasse
    lighting_info = get_lighting_class_info(classification.calculated_lighting_class)

    # Gesammelte Parameter für die Klassifizierung
    selected_parameters = []
    if classification.selected_choices.exists():
        for selected_choice in classification.selected_choices.all():
            param_info = {
                'parameter_name': selected_choice.parameter.name,
                'choice_text': selected_choice.choice.choice_text,
                'weighting_value': selected_choice.choice.weighting_value
            }
            selected_parameters.append(param_info)

    # Zeit-bezogene Klassifizierungen (wenn adaptive Beleuchtung)
    time_period_classifications = {}
    energy_savings = None

    # Alle verwandten Zeitraum-Klassifizierungen laden (basierend auf Projektname)
    base_project_name = classification.project_name.split(' (')[0]  # Remove time period suffix
    related_classifications = DINLightingClassification.objects.filter(
        user=request.user,
        project_name__startswith=base_project_name,
        road_category=classification.road_category
    ).order_by('time_period')

    for rel_class in related_classifications:
        period = rel_class.time_period or 'dt0'
        time_period_classifications[period] = rel_class

    # Energieeinsparung berechnen (wenn mehrere Zeiträume)
    if len(time_period_classifications) > 1:
        dt0_class = time_period_classifications.get('dt0')
        if dt0_class and dt0_class.calculated_lighting_class:
            base_class_num = int(dt0_class.calculated_lighting_class[1:]) if dt0_class.calculated_lighting_class[1:].isdigit() else 3
            energy_savings = min(70, max(30, (len(time_period_classifications) - 1) * 20 + base_class_num * 5))

    # Context für PDF-Template
    context = {
        'classification': classification,
        'lighting_info': lighting_info,
        'selected_parameters': selected_parameters,
        'time_period_classifications': time_period_classifications,
        'energy_savings': energy_savings,
        'is_adaptive': len(time_period_classifications) > 1,
    }

    # HTML-Template rendern
    html_string = render_to_string('lighting_classification/din_pdf_report.html', context)

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
        project_name = classification.project_name.split(' (')[0]  # Remove time period suffix
        filename = f'DIN_EN_13201_Klassifizierung_{project_name}_{classification.created_at.strftime("%Y%m%d")}.pdf'
        # Sonderzeichen für Dateinamen entfernen
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ").replace(" ", "_")

        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        messages.error(request, f'Fehler beim Generieren der PDF: {str(e)}')
        return redirect('lighting_classification:din_view_result', classification_id=classification.id)


def get_maintenance_values(lighting_class):
    """
    Wartungswerte nach DIN 13201-2:2015-11 basierend auf Beleuchtungsklasse
    """
    if not lighting_class:
        return {}

    # Wartungswerte nach DIN 13201-2:2015-11
    maintenance_values = {
        # M-Klassen (Motorisierter Verkehr)
        'M1': {
            'luminance': '2.0 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': '≥ 0.7',
            'threshold_increment': '≤ 10%',
            'surroundings_ratio': '≥ 0.5'
        },
        'M2': {
            'luminance': '1.5 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': '≥ 0.7',
            'threshold_increment': '≤ 10%',
            'surroundings_ratio': '≥ 0.5'
        },
        'M3': {
            'luminance': '1.0 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': '≥ 0.6',
            'threshold_increment': '≤ 15%',
            'surroundings_ratio': '≥ 0.5'
        },
        'M4': {
            'luminance': '0.75 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': '≥ 0.6',
            'threshold_increment': '≤ 15%',
            'surroundings_ratio': '≥ 0.5'
        },
        'M5': {
            'luminance': '0.5 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.35',
            'longitudinal_uniformity': '≥ 0.5',
            'threshold_increment': '≤ 15%',
            'surroundings_ratio': '≥ 0.5'
        },
        'M6': {
            'luminance': '0.3 cd/m²',
            'illuminance': None,
            'overall_uniformity': '≥ 0.35',
            'longitudinal_uniformity': '≥ 0.5',
            'threshold_increment': '≤ 15%',
            'surroundings_ratio': '≥ 0.5'
        },

        # P-Klassen (Fußgänger- und Radverkehr)
        'P1': {
            'luminance': None,
            'illuminance': '15 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'P2': {
            'luminance': None,
            'illuminance': '10 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'P3': {
            'luminance': None,
            'illuminance': '7.5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'P4': {
            'luminance': None,
            'illuminance': '5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'P5': {
            'luminance': None,
            'illuminance': '3 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'P6': {
            'luminance': None,
            'illuminance': '2 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },

        # A-Klassen (Konfliktbereiche)
        'A1': {
            'luminance': None,
            'illuminance': '30 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'A2': {
            'luminance': None,
            'illuminance': '20 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'A3': {
            'luminance': None,
            'illuminance': '15 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'A4': {
            'luminance': None,
            'illuminance': '10 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'A5': {
            'luminance': None,
            'illuminance': '7.5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'A6': {
            'luminance': None,
            'illuminance': '5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },

        # C-Klassen (Nebenstraßen)
        'C1': {
            'luminance': None,
            'illuminance': '15 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'C2': {
            'luminance': None,
            'illuminance': '10 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'C3': {
            'luminance': None,
            'illuminance': '7.5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'C4': {
            'luminance': None,
            'illuminance': '5 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'C5': {
            'luminance': None,
            'illuminance': '3 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        },
        'C6': {
            'luminance': None,
            'illuminance': '2 lx',
            'overall_uniformity': '≥ 0.4',
            'longitudinal_uniformity': None,
            'threshold_increment': None,
            'surroundings_ratio': None
        }
    }

    return maintenance_values.get(lighting_class, {})
