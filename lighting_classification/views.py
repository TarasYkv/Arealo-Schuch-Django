from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import RoadType, LightingClassification, ClassificationCriteria, ClassificationScoring
import json


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
    """Schritt 1: Straßentyp auswählen"""

    # Gruppierung der Straßentypen nach Kategorien
    road_types_by_category = {}
    road_types = RoadType.objects.filter(is_active=True).order_by('category', 'code')

    for road_type in road_types:
        category_name = dict(RoadType.CATEGORY_CHOICES).get(road_type.category, road_type.category)
        if category_name not in road_types_by_category:
            road_types_by_category[category_name] = []
        road_types_by_category[category_name].append(road_type)

    # Icons für Kategorien
    category_icons = {
        'Autobahnen und Kraftfahrstraßen': 'fas fa-highway',
        'Hauptverkehrsstraßen': 'fas fa-road',
        'Sammelstraßen': 'fas fa-route',
        'Erschließungsstraßen': 'fas fa-home',
        'Fußgängerwege': 'fas fa-walking',
        'Radwege': 'fas fa-bicycle',
        'Konfliktbereiche': 'fas fa-exclamation-triangle',
    }

    context = {
        'road_types_by_category': road_types_by_category,
        'category_icons': category_icons,
        'step': 1,
        'step_title': 'Straßentyp auswählen',
        'step_description': 'Wählen Sie den Straßentyp gemäß DIN EN 13201 aus',
    }

    return render(request, 'lighting_classification/select_road_type.html', context)


@login_required
@require_http_methods(["POST"])
def start_classification(request):
    """Startet eine neue Klassifizierung mit ausgewähltem Straßentyp"""

    road_type_id = request.POST.get('road_type_id')
    project_name = request.POST.get('project_name', '').strip()

    if not road_type_id:
        messages.error(request, 'Bitte wählen Sie einen Straßentyp aus.')
        return redirect('lighting_classification:select_road_type')

    if not project_name:
        messages.error(request, 'Bitte geben Sie einen Projektnamen an.')
        return redirect('lighting_classification:select_road_type')

    try:
        road_type = RoadType.objects.get(id=road_type_id, is_active=True)
    except RoadType.DoesNotExist:
        messages.error(request, 'Der ausgewählte Straßentyp ist nicht gültig.')
        return redirect('lighting_classification:select_road_type')

    # Neue Klassifizierung erstellen
    classification = LightingClassification.objects.create(
        user=request.user,
        project_name=project_name,
        road_type=road_type,
        status='draft'
    )

    messages.success(request, f'Klassifizierung "{project_name}" wurde gestartet.')
    return redirect('lighting_classification:configure_parameters', classification_id=classification.id)


@login_required
def configure_parameters(request, classification_id):
    """Schritt 2: Parameter konfigurieren mit Punktetabellen"""

    classification = get_object_or_404(
        LightingClassification,
        id=classification_id,
        user=request.user
    )

    if request.method == 'POST':
        try:
            # Parse selected criteria from JSON
            selected_criteria_json = request.POST.get('selected_criteria', '[]')
            selected_criteria_ids = json.loads(selected_criteria_json)

            # Create or get scoring object
            scoring, created = ClassificationScoring.objects.get_or_create(
                classification=classification
            )

            # Map criteria IDs to actual point values based on the criteria definitions
            criteria_points_map = {
                # Traffic Volume
                'traffic_very_high': 2,
                'traffic_high': 1,
                'traffic_medium': 0,
                'traffic_low': 0,

                # Speed
                'speed_very_high': 2,
                'speed_high': 1,
                'speed_medium': 0,
                'speed_low': 0,

                # Complexity
                'complexity_very_high': 2,
                'complexity_high': 1,
                'complexity_normal': 0,

                # Ambient Light
                'ambient_e2': 1,
                'ambient_e1': 0,
                'ambient_e0': 0,
            }

            # Calculate total points
            total_points = sum(criteria_points_map.get(criteria_id, 0) for criteria_id in selected_criteria_ids)

            # Update scoring
            scoring.total_points = total_points
            scoring.calculated_class = scoring.determine_lighting_class()
            scoring.save()

            # Update classification with results
            classification.recommended_class = scoring.calculated_class
            classification.status = 'completed'

            # Store the selected criteria for display
            selected_criteria_data = {}
            for criteria_id in selected_criteria_ids:
                if criteria_id in criteria_points_map:
                    selected_criteria_data[criteria_id] = criteria_points_map[criteria_id]

            classification.notes = json.dumps({
                'selected_criteria': selected_criteria_data,
                'total_points': total_points,
                'calculation_method': 'DIN_EN_13201_point_system'
            })

            classification.save()

            messages.success(request, f'Parameter wurden gespeichert. Erreichte Punktzahl: {total_points} → Beleuchtungsklasse: {scoring.calculated_class}')
            return redirect('lighting_classification:view_result', classification_id=classification.id)

        except (json.JSONDecodeError, ValueError) as e:
            messages.error(request, 'Fehler beim Verarbeiten der ausgewählten Parameter.')
            return redirect('lighting_classification:configure_parameters', classification_id=classification.id)

    context = {
        'classification': classification,
        'step': 2,
        'step_title': 'Parameter konfigurieren',
        'step_description': f'Bewerten Sie die Parameter für {classification.road_type.name} nach DIN EN 13201',
    }

    return render(request, 'lighting_classification/configure_parameters.html', context)


@login_required
def view_result(request, classification_id):
    """Schritt 3: Ergebnis anzeigen"""

    classification = get_object_or_404(
        LightingClassification,
        id=classification_id,
        user=request.user
    )

    # Zusätzliche Informationen zur Beleuchtungsklasse
    lighting_info = get_lighting_class_info(classification.recommended_class)

    context = {
        'classification': classification,
        'lighting_info': lighting_info,
        'step': 3,
        'step_title': 'Beleuchtungsklasse',
        'step_description': 'Empfohlene Beleuchtungsklasse nach DIN EN 13201',
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
