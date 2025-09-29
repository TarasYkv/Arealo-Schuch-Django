"""
PDF Generator für Wirtschaftlichkeitsberechnungen
Basiert auf der Qt-Vorlage mit modernem Design und integrierten Charts
"""

import io
import os
import tempfile
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
import base64
from decimal import Decimal
from amortization_calculator.calculation_service import LightingCalculationService


class AmortizationChartGenerator:
    """Generate charts for the amortization PDF"""

    # Color scheme from Qt template
    COLORS = {
        'bestand': '#dc3545',     # Red for legacy systems
        'led': '#0075BE',         # Blue
        'lms': '#28a745',       # Green for LIMAS
        'combined': '#8E44AD',    # Purple for combined
        'accent': '#ffc107'       # Yellow accent
    }

    def __init__(self, calculation):
        self.calculation = calculation
        if MATPLOTLIB_AVAILABLE:
            plt.style.use('default')

    def _setup_chart_style(self, fig, ax):
        """Apply consistent styling to charts"""
        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Set grid
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_axisbelow(True)

        # Set figure background
        fig.patch.set_facecolor('white')

    def _save_chart_as_base64(self, fig):
        """Save chart as base64 string for embedding"""
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        buffer.close()
        plt.close(fig)
        return f"data:image/png;base64,{image_base64}"

    def generate_cost_comparison_chart(self):
        """Generate cost comparison bar chart"""
        fig, ax = plt.subplots(figsize=(10, 6))
        self._setup_chart_style(fig, ax)

        # Data
        labels = []
        values = []
        colors = []

        if self.calculation.neue_anlage_vorhanden:
            labels.extend(['Bestandsanlage', 'LED-Leuchten', 'LED + LIMAS'])
            values.extend([
                float(self.calculation.kosten_alt_jahr or 0),
                float(self.calculation.kosten_neu_ohne_lms_jahr or 0),
                float(self.calculation.kosten_neu_mit_lms_jahr or 0)
            ])
            colors.extend([self.COLORS['bestand'], self.COLORS['led'], self.COLORS['lms']])
        else:
            labels.extend(['LED-Leuchten', 'LED + LIMAS'])
            values.extend([
                float(self.calculation.kosten_neu_ohne_lms_jahr or 0),
                float(self.calculation.kosten_neu_mit_lms_jahr or 0)
            ])
            colors.extend([self.COLORS['led'], self.COLORS['lms']])

        # Create bars
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='white', linewidth=1)

        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                   f'{value:,.0f} €', ha='center', va='bottom', fontweight='bold')

        # Styling
        ax.set_ylabel('Jährliche Kosten (€)', fontsize=12, fontweight='bold')
        ax.set_title('Kostenvergleich pro Jahr', fontsize=14, fontweight='bold', pad=20)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f} €'))

        # Rotate labels if needed
        if len(labels) > 2:
            plt.xticks(rotation=15)

        plt.tight_layout()
        return self._save_chart_as_base64(fig)

    def generate_amortization_chart(self):
        """Generate amortization times chart"""
        fig, ax = plt.subplots(figsize=(10, 6))
        self._setup_chart_style(fig, ax)

        # Data
        labels = ['LED-Leuchten', 'Nur LIMAS', 'LED + LIMAS']
        values = [
            float(self.calculation.amortisation_neu_jahre or 0),
            float(self.calculation.amortisation_lms_jahre or 0),
            float(self.calculation.amortisation_gesamt_jahre or 0)
        ]
        colors = [self.COLORS['led'], self.COLORS['accent'], self.COLORS['lms']]

        # Create bars
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='white', linewidth=1)

        # Add value labels
        for bar, value in zip(bars, values):
            if value > 0:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                       f'{value:.1f} Jahre', ha='center', va='bottom', fontweight='bold')

        # Styling
        ax.set_ylabel('Amortisationszeit (Jahre)', fontsize=12, fontweight='bold')
        ax.set_title('Amortisationszeiten', fontsize=14, fontweight='bold', pad=20)
        ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 5)

        plt.xticks(rotation=15)
        plt.tight_layout()
        return self._save_chart_as_base64(fig)

    def generate_energy_consumption_chart(self):
        """Generate energy consumption comparison chart"""
        fig, ax = plt.subplots(figsize=(10, 6))
        self._setup_chart_style(fig, ax)

        # Calculate consumption
        alt_verbrauch = 0
        if self.calculation.neue_anlage_vorhanden:
            alt_verbrauch = (
                (self.calculation.alt_leistung or 0) *
                (self.calculation.alt_anzahl or 0) *
                (self.calculation.alt_stunden_pro_tag or 0) *
                (self.calculation.alt_tage_pro_jahr or 0)
            ) / 1000

        neu_verbrauch = (
            (self.calculation.neu_leistung or 0) *
            (self.calculation.neu_anzahl or 0) *
            (self.calculation.neu_stunden_pro_tag or 0) *
            (self.calculation.neu_tage_pro_jahr or 0)
        ) / 1000

        # Estimate LIMAS savings (30% reduction)
        neu_verbrauch_lms = neu_verbrauch * 0.7

        # Data
        labels = []
        values = []
        colors = []

        if self.calculation.neue_anlage_vorhanden and alt_verbrauch > 0:
            labels.extend(['Bestandsanlage', 'LED-Leuchten', 'LED + LIMAS'])
            values.extend([alt_verbrauch, neu_verbrauch, neu_verbrauch_lms])
            colors.extend([self.COLORS['bestand'], self.COLORS['led'], self.COLORS['lms']])
        else:
            labels.extend(['LED-Leuchten', 'LED + LIMAS'])
            values.extend([neu_verbrauch, neu_verbrauch_lms])
            colors.extend([self.COLORS['led'], self.COLORS['lms']])

        # Create bars
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='white', linewidth=1)

        # Add value labels
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                   f'{value:,.0f} kWh', ha='center', va='bottom', fontweight='bold')

        # Styling
        ax.set_ylabel('Energieverbrauch (kWh/Jahr)', fontsize=12, fontweight='bold')
        ax.set_title('Energieverbrauch pro Jahr', fontsize=14, fontweight='bold', pad=20)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        if len(labels) > 2:
            plt.xticks(rotation=15)

        plt.tight_layout()
        return self._save_chart_as_base64(fig)

    def generate_co2_emissions_chart(self):
        """Generate CO2 emissions comparison chart"""
        fig, ax = plt.subplots(figsize=(10, 6))
        self._setup_chart_style(fig, ax)

        # Data
        labels = []
        values = []
        colors = []

        if self.calculation.neue_anlage_vorhanden:
            labels.extend(['Bestandsanlage', 'LED-Leuchten', 'LED + LIMAS'])
            values.extend([
                float(self.calculation.co2_emission_alt_kg_jahr or 0),
                float(self.calculation.co2_emission_neu_ohne_lms_kg_jahr or 0),
                float(self.calculation.co2_emission_neu_mit_lms_kg_jahr or 0)
            ])
            colors.extend([self.COLORS['bestand'], self.COLORS['led'], self.COLORS['lms']])
        else:
            labels.extend(['LED-Leuchten', 'LED + LIMAS'])
            values.extend([
                float(self.calculation.co2_emission_neu_ohne_lms_kg_jahr or 0),
                float(self.calculation.co2_emission_neu_mit_lms_kg_jahr or 0)
            ])
            colors.extend([self.COLORS['led'], self.COLORS['lms']])

        # Create bars
        bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='white', linewidth=1)

        # Add value labels
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + max(values)*0.01,
                   f'{value:,.0f} kg', ha='center', va='bottom', fontweight='bold')

        # Styling
        ax.set_ylabel('CO₂-Emissionen (kg/Jahr)', fontsize=12, fontweight='bold')
        ax.set_title('CO₂-Emissionen pro Jahr', fontsize=14, fontweight='bold', pad=20)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        if len(labels) > 2:
            plt.xticks(rotation=15)

        plt.tight_layout()
        return self._save_chart_as_base64(fig)

    def generate_all_charts(self):
        """Generate all charts and return as dictionary"""
        if not MATPLOTLIB_AVAILABLE:
            # Return empty placeholders when matplotlib is not available
            return {
                'cost_chart': None,
                'amortization_chart': None,
                'energy_chart': None,
                'co2_chart': None,
            }

        return {
            'cost_chart': self.generate_cost_comparison_chart(),
            'amortization_chart': self.generate_amortization_chart(),
            'energy_chart': self.generate_energy_consumption_chart(),
            'co2_chart': self.generate_co2_emissions_chart(),
        }


def calculate_savings_data(calculation):
    """Calculate various savings metrics"""
    data = {}

    # Energy consumption calculations
    alt_verbrauch = 0
    if calculation.neue_anlage_vorhanden:
        alt_verbrauch = (
            (calculation.alt_leistung or 0) *
            (calculation.alt_anzahl or 0) *
            (calculation.alt_stunden_pro_tag or 0) *
            (calculation.alt_tage_pro_jahr or 0)
        ) / 1000

    neu_verbrauch = (
        (calculation.neu_leistung or 0) *
        (calculation.neu_anzahl or 0) *
        (calculation.neu_stunden_pro_tag or 0) *
        (calculation.neu_tage_pro_jahr or 0)
    ) / 1000

    neu_verbrauch_lms = neu_verbrauch * 0.7  # 30% LIMAS savings

    # Store calculated consumption values
    data['alt_verbrauch'] = alt_verbrauch
    data['neu_verbrauch'] = neu_verbrauch
    data['neu_verbrauch_lms'] = neu_verbrauch_lms

    # Cost savings
    alt_kosten = float(calculation.kosten_alt_jahr or 0)
    neu_kosten = float(calculation.kosten_neu_ohne_lms_jahr or 0)
    neu_kosten_lms = float(calculation.kosten_neu_mit_lms_jahr or 0)

    # Annual savings
    data['energy_savings_led'] = max(0, alt_verbrauch - neu_verbrauch)
    data['energy_savings_lms'] = max(0, alt_verbrauch - neu_verbrauch_lms)
    data['cost_savings_led'] = max(0, alt_kosten - neu_kosten)
    data['cost_savings_lms'] = max(0, alt_kosten - neu_kosten_lms)

    # Percentage savings
    if alt_kosten > 0:
        data['cost_savings_percent_led'] = (data['cost_savings_led'] / alt_kosten) * 100
        data['cost_savings_percent_lms'] = (data['cost_savings_lms'] / alt_kosten) * 100
    else:
        data['cost_savings_percent_led'] = 0
        data['cost_savings_percent_lms'] = 0

    if alt_verbrauch > 0:
        data['energy_savings_percent_led'] = (data['energy_savings_led'] / alt_verbrauch) * 100
        data['energy_savings_percent_lms'] = (data['energy_savings_lms'] / alt_verbrauch) * 100
    else:
        data['energy_savings_percent_led'] = 0
        data['energy_savings_percent_lms'] = 0

    # CO2 savings and percentages
    co2_alt = float(calculation.co2_emission_alt_kg_jahr or 0)
    co2_neu = float(calculation.co2_emission_neu_ohne_lms_kg_jahr or 0)
    co2_lms = float(calculation.co2_emission_neu_mit_lms_kg_jahr or 0)

    data['co2_savings_led'] = max(0, co2_alt - co2_neu)
    data['co2_savings_lms'] = max(0, co2_alt - co2_lms)

    if co2_alt > 0:
        data['co2_savings_percent_led'] = (data['co2_savings_led'] / co2_alt) * 100
        data['co2_savings_percent_lms'] = (data['co2_savings_lms'] / co2_alt) * 100
    else:
        data['co2_savings_percent_led'] = 0
        data['co2_savings_percent_lms'] = 0

    # Investment data
    data['investment_total'] = float(calculation.investitionskosten_gesamt or 0)
    data['investment_lms'] = float(calculation.investitionskosten_lms or 0)
    data['investment_led'] = data['investment_total'] - data['investment_lms']

    # LED equipment cost calculation
    data['led_equipment_cost'] = (calculation.neu_anzahl or 0) * (calculation.neu_anschaffungskosten_pro_stueck or 0)

    # Investment percentages
    if data['investment_total'] > 0:
        data['led_equipment_percent'] = (data['led_equipment_cost'] / data['investment_total']) * 100
        data['installation_percent'] = ((calculation.neu_installationskosten or 0) / data['investment_total']) * 100
        data['lms_percent'] = (data['investment_lms'] / data['investment_total']) * 100
    else:
        data['led_equipment_percent'] = 0
        data['installation_percent'] = 0
        data['lms_percent'] = 0

    # Environmental equivalents
    data['trees_equivalent'] = max(0, data['co2_savings_lms'] / 22)  # 22 kg CO2 per tree per year

    # Financing calculations
    if data['investment_total'] > 0 and data['cost_savings_lms'] > 0:
        data['monthly_financing_5y'] = data['investment_total'] / 60  # 5 years
        data['monthly_savings'] = data['cost_savings_lms'] / 12

    return data


def generate_amortization_pdf(calculation):
    """Generate comprehensive PDF report"""

    # Update todo status
    from django.apps import apps
    TodoWrite = apps.get_model('amortization_calculator', 'LightingCalculation')

    # Generate charts
    chart_generator = AmortizationChartGenerator(calculation)
    charts = chart_generator.generate_all_charts()

    # Calculate additional metrics
    savings_data = calculate_savings_data(calculation)

    # Prepare context for template
    context = {
        'calculation': calculation,
        'charts': charts,
        'savings_data': savings_data,
        'generated_date': datetime.now(),
        'report_title': f'Wirtschaftlichkeitsanalyse - {calculation.projektname}',
        'company': calculation.firmenname or 'Unbekanntes Unternehmen',
        'matplotlib_available': MATPLOTLIB_AVAILABLE,
    }

    # Render HTML template
    html_string = render_to_string('amortization_calculator/pdf_template.html', context)

    # CSS for styling
    css_string = """
    @page {
        margin: 2cm;
        size: A4;
        @top-center {
            content: "Wirtschaftlichkeitsrechner";
            font-family: Arial, sans-serif;
            font-size: 10pt;
            color: #666;
        }
        @bottom-center {
            content: "Seite " counter(page) " von " counter(pages);
            font-family: Arial, sans-serif;
            font-size: 10pt;
            color: #666;
        }
    }

    body {
        font-family: 'Arial', sans-serif;
        line-height: 1.4;
        color: #333;
        font-size: 11pt;
    }

    .header {
        border-bottom: 3px solid #0075BE;
        padding-bottom: 20px;
        margin-bottom: 30px;
    }

    .logo-section {
        text-align: center;
        margin-bottom: 20px;
    }

    .company-info {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-left: 4px solid #0075BE;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 30px;
    }

    .section {
        margin-bottom: 40px;
        page-break-inside: avoid;
    }

    .section-title {
        background: #0075BE;
        color: white;
        padding: 10px 15px;
        font-size: 14pt;
        font-weight: bold;
        border-radius: 5px;
        margin-bottom: 20px;
    }

    .chart-container {
        text-align: center;
        margin: 30px 0;
        page-break-inside: avoid;
    }

    .chart-container img {
        max-width: 100%;
        height: auto;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-radius: 8px;
    }

    .chart-caption {
        font-style: italic;
        color: #666;
        margin-top: 10px;
        font-size: 10pt;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin: 20px 0;
    }

    .metric-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
    }

    .metric-value {
        font-size: 18pt;
        font-weight: bold;
        color: #0075BE;
    }

    .metric-label {
        font-size: 10pt;
        color: #666;
        margin-top: 5px;
    }

    .highlight-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border: 1px solid #2196f3;
        border-radius: 8px;
        padding: 20px;
        margin: 20px 0;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }

    th, td {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: left;
    }

    th {
        background: #0075BE;
        color: white;
        font-weight: bold;
    }

    tr:nth-child(even) {
        background: #f9f9f9;
    }

    .page-break {
        page-break-before: always;
    }

    .no-break {
        page-break-inside: avoid;
    }

    .text-center {
        text-align: center;
    }

    .text-right {
        text-align: right;
    }

    .text-primary {
        color: #0075BE;
    }

    .text-success {
        color: #28a745;
    }

    .text-muted {
        color: #666;
    }

    .mt-4 {
        margin-top: 40px;
    }

    .mb-4 {
        margin-bottom: 40px;
    }
    """

    # Generate PDF
    html_doc = HTML(string=html_string)
    css_doc = CSS(string=css_string)

    # Create response
    response = HttpResponse(content_type='application/pdf')
    pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
    response.write(pdf_bytes)

    return response


class DetailedCalculationReport:
    """Prepare context for the detailed explanation PDF"""

    def __init__(self, calculation):
        self.calculation = calculation

    def get_context(self):
        calc = self.calculation
        co2_factor = LightingCalculationService.EMISSION_FACTORS['co2'] / 1000  # kg/kWh

        consumption_old = calc.verbrauch_alt_kwh_jahr or 0
        consumption_led = calc.verbrauch_neu_ohne_lms_kwh_jahr or 0
        consumption_lightmanagement = calc.verbrauch_neu_mit_lms_kwh_jahr or consumption_led

        cost_old = calc.kosten_alt_jahr or 0
        cost_led = calc.kosten_neu_ohne_lms_jahr or 0
        cost_lightmanagement = calc.kosten_neu_mit_lms_jahr or cost_led

        annual_savings_led = max(0, cost_old - cost_led)
        annual_savings_lightmgmt = max(0, cost_old - cost_lightmanagement)
        annual_savings_total = annual_savings_lightmgmt

        energy_savings_led = max(0, consumption_old - consumption_led)
        energy_savings_lightmgmt = max(0, consumption_old - consumption_lightmanagement)

        co2_old = calc.co2_emission_alt_kg_jahr or (consumption_old * co2_factor)
        co2_led = calc.co2_emission_neu_ohne_lms_kg_jahr or (consumption_led * co2_factor)
        co2_lightmanagement = calc.co2_emission_neu_mit_lms_kg_jahr or (consumption_lightmanagement * co2_factor)
        co2_savings = co2_old - co2_lightmanagement

        context = {
            'project_name': calc.projektname,
            'company_name': calc.firmenname,
            'creation_date': calc.created_at,
            'energy_price': calc.strompreis,
            'anlage_typ': calc.get_anlagen_typ_display(),
            'usage_hours_new': calc.neu_stunden_pro_tag,
            'usage_days_new': calc.neu_tage_pro_jahr,
            'usage_hours_old': calc.alt_stunden_pro_tag,
            'usage_days_old': calc.alt_tage_pro_jahr,
            'movement_enabled': calc.bewegungsmelder_aktiviert,
            'movement_count': calc.bewegungsmelder_anzahl,
            'movement_presence_level': calc.bewegungsmelder_anwesenheit_niveau,
            'movement_absence_level': calc.bewegungsmelder_abwesenheit_niveau,
            'daylight_enabled': calc.tageslicht_aktiviert,
            'daylight_count': calc.tageslicht_anzahl,
            'daylight_reduction': calc.tageslicht_reduzierung_niveau,
            'daylight_hours': calc.tageslicht_nutzung_stunden,
            'calendar_enabled': calc.kalender_aktiviert,
            'calendar_off_days': calc.kalender_anzahl_ausschalttage,
            'investment_led': calc.investitionskosten_gesamt or 0,
            'investment_lightmanagement': calc.investitionskosten_lms or 0,
            'amort_led': calc.amortisation_neu_jahre,
            'amort_lightmanagement': calc.amortisation_lms_jahre,
            'amort_total': calc.amortisation_gesamt_jahre,
            'cost_old': cost_old,
            'cost_led': cost_led,
            'cost_lightmanagement': cost_lightmanagement,
            'cost_savings_led': annual_savings_led,
            'cost_savings_lightmanagement': annual_savings_lightmgmt,
            'cost_savings_total': annual_savings_total,
            'energy_savings_led': energy_savings_led,
            'energy_savings_lightmanagement': energy_savings_lightmgmt,
            'consumption_old': consumption_old,
            'consumption_led': consumption_led,
            'consumption_lightmanagement': consumption_lightmanagement,
            'co2_old': co2_old,
            'co2_led': co2_led,
            'co2_lightmanagement': co2_lightmanagement,
            'co2_factor': co2_factor,
            'co2_savings': co2_savings,
        }

        context['formulas'] = {
            'verbrauch_alt': "Bestandsverbrauch = Leistung_alt/1000 × Anzahl × Stunden/Tag × Tage/Jahr",
            'verbrauch_neu': "LED-Verbrauch = Leistung_neu/1000 × Anzahl × Stunden/Tag × Tage/Jahr",
            'bewegungsmelder': "Bewegungsmelder: Kombination aus Anwesenheits- und Abwesenheitsniveau je nach Frequentierung",
            'tageslicht': "Tageslichtregelung: Reduzierter Verbrauch während Tageslichtnutzung plus Vollleistung in Restzeit",
            'kosten': "Kosten = Stromkosten + Wartung + laufende Kosten",
            'amortisation': "Amortisation = Investitionskosten / jährliche Einsparung",
            'co2': "CO₂ = Verbrauch × Emissionsfaktor (489 g/kWh)",
        }

        context['explanations'] = {
            'consumption': (
                "Der jährliche Verbrauch der Bestandsanlage beträgt {old:.0f} kWh. "
                "Die neue LED-Anlage reduziert ihn auf {led:.0f} kWh und in Kombination mit Lichtmanagement auf {lm:.0f} kWh."
            ).format(old=consumption_old, led=consumption_led, lm=consumption_lightmanagement),
            'costs': (
                "Die Betriebskosten setzen sich aus Strom-, Wartungs- und laufenden Kosten zusammen. "
                "Im Bestand ergeben sich {old:.0f} €. Mit LED sinkt dieser Betrag auf {led:.0f} €, "
                "und das Lichtmanagement führt zu jährlichen Kosten von {lm:.0f} €, wodurch {sav:.0f} € pro Jahr gespart werden."
            ).format(old=cost_old, led=cost_led, lm=cost_lightmanagement, sav=annual_savings_total),
            'amortisation': (
                "Die Amortisation errechnet sich aus Investition geteilt durch jährliche Einsparung. "
                "Für die LED-Investition von {inv_led:.0f} € mit einer Einsparung von {save_led:.0f} €/Jahr ergibt sich {am_led:.1f} Jahre. "
                "Das Lichtmanagement kostet {inv_lm:.0f} € und spart {save_lm:.0f} €/Jahr, somit {am_lm:.1f} Jahre. "
                "Zusammen amortisiert sich das Gesamtpaket in {am_tot:.1f} Jahren."
            ).format(
                inv_led=context['investment_led'],
                save_led=annual_savings_led,
                am_led=context['amort_led'] or 0,
                inv_lm=context['investment_lightmanagement'],
                save_lm=annual_savings_lightmgmt,
                am_lm=context['amort_lightmanagement'] or 0,
                am_tot=context['amort_total'] or 0
            ),
            'co2': (
                "Für jede Kilowattstunde setzen wir {factor:.3f} kg CO₂ an. "
                "Die Bestandsanlage verursacht {old:.0f} kg/Jahr, LED {led:.0f} kg/Jahr und LED mit Lichtmanagement {lm:.0f} kg/Jahr. "
                "Die Einsparung beträgt somit {sav:.0f} kg CO₂ jährlich."
            ).format(factor=co2_factor, old=co2_old, led=co2_led, lm=co2_lightmanagement, sav=co2_savings)
        }

        return context


def generate_detailed_pdf(calculation):
    """Generate detailed PDF explaining calculation logic"""

    charts = AmortizationChartGenerator(calculation).generate_all_charts()
    detail_context = DetailedCalculationReport(calculation).get_context()

    html_string = render_to_string('amortization_calculator/pdf_detailed_template.html', {
        'calculation': calculation,
        'charts': charts,
        'context': detail_context,
        'generated_date': datetime.now(),
        'matplotlib_available': MATPLOTLIB_AVAILABLE,
    })

    html_doc = HTML(string=html_string)
    css_doc = CSS(string="""
    body { font-family: 'Helvetica', 'Arial', sans-serif; color: #333; margin: 40px; }
    h1, h2, h3 { color: #0075BE; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { padding: 8px 12px; border-bottom: 1px solid #ddd; }
    th { background-color: #f5f9ff; }
    .section { margin-bottom: 40px; }
    .formula-box { background: #f9f9f9; border-left: 4px solid #0075BE; padding: 12px 16px; margin-bottom: 12px; }
    .highlight { background: #e8f5e8; border-left: 4px solid #28a745; padding: 12px 16px; }
    .chart { margin: 20px 0; text-align: center; }
    .chart img { max-width: 100%; height: auto; }
    """)

    response = HttpResponse(content_type='application/pdf')
    pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
    response.write(pdf_bytes)
    return response
