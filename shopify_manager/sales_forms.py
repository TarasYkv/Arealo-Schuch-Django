from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ShippingProfile, RecurringCost, AdsCost, SalesData


class DateRangeForm(forms.Form):
    """Form für Zeitraum-Auswahl"""
    PERIOD_CHOICES = [
        ('custom', 'Benutzerdefiniert'),
        ('1_day', '1 Tag'),
        ('7_days', '7 Tage'),
        ('30_days', '30 Tage'),
        ('3_months', '3 Monate'),
        ('6_months', '6 Monate'),
        ('12_months', '12 Monate'),
        ('24_months', '24 Monate'),
    ]
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial='30_days',
        widget=forms.Select(attrs={'class': 'form-control', 'onchange': 'updateDateRange()'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setze Standard-Datumsbereich
        if not self.initial.get('start_date'):
            self.initial['start_date'] = timezone.now().date() - timedelta(days=30)
        if not self.initial.get('end_date'):
            self.initial['end_date'] = timezone.now().date()
    
    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get('period')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if period == 'custom':
            if not start_date or not end_date:
                raise forms.ValidationError("Für benutzerdefinierte Zeiträume müssen Start- und Enddatum angegeben werden.")
            if start_date > end_date:
                raise forms.ValidationError("Startdatum muss vor dem Enddatum liegen.")
        else:
            # Berechne Datumsbereich basierend auf Auswahl
            today = timezone.now().date()
            if period == '1_day':
                start_date = today - timedelta(days=1)
                end_date = today
            elif period == '7_days':
                start_date = today - timedelta(days=7)
                end_date = today
            elif period == '30_days':
                start_date = today - timedelta(days=30)
                end_date = today
            elif period == '3_months':
                start_date = today - timedelta(days=90)
                end_date = today
            elif period == '6_months':
                start_date = today - timedelta(days=180)
                end_date = today
            elif period == '12_months':
                start_date = today - timedelta(days=365)
                end_date = today
            elif period == '24_months':
                start_date = today - timedelta(days=730)
                end_date = today
            
            cleaned_data['start_date'] = start_date
            cleaned_data['end_date'] = end_date
        
        return cleaned_data


class ShippingProfileForm(forms.ModelForm):
    """Form für Versandprofile"""
    
    class Meta:
        model = ShippingProfile
        fields = ['name', 'shipping_cost', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name des Versandprofils'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Name',
            'shipping_cost': 'Versandkosten (€)',
            'is_active': 'Aktiv',
        }


class RecurringCostForm(forms.ModelForm):
    """Form für laufende Kosten"""
    
    class Meta:
        model = RecurringCost
        fields = ['name', 'description', 'amount', 'frequency', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name der laufenden Kosten'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optionale Beschreibung'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Name',
            'description': 'Beschreibung',
            'amount': 'Betrag (€)',
            'frequency': 'Häufigkeit',
            'start_date': 'Startdatum',
            'end_date': 'Enddatum (optional)',
            'is_active': 'Aktiv',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Startdatum muss vor dem Enddatum liegen.")
        
        return cleaned_data


class AdsCostForm(forms.ModelForm):
    """Form für Werbekosten"""
    
    class Meta:
        model = AdsCost
        fields = ['platform', 'campaign_name', 'cost', 'clicks', 'impressions', 'conversions', 'revenue', 'date']
        widgets = {
            'platform': forms.Select(attrs={'class': 'form-control'}),
            'campaign_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name der Kampagne'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'clicks': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'impressions': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'conversions': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'revenue': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'platform': 'Plattform',
            'campaign_name': 'Kampagnenname',
            'cost': 'Kosten (€)',
            'clicks': 'Klicks',
            'impressions': 'Impressionen',
            'conversions': 'Conversions',
            'revenue': 'Umsatz (€)',
            'date': 'Datum',
        }


class SalesDataImportForm(forms.Form):
    """Form für Verkaufsdaten-Import"""
    
    start_date = forms.DateField(
        label='Startdatum',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=lambda: timezone.now().date() - timedelta(days=30)
    )
    
    end_date = forms.DateField(
        label='Enddatum',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        initial=lambda: timezone.now().date()
    )
    
    limit = forms.IntegerField(
        label='Limit',
        initial=250,
        min_value=1,
        max_value=250,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '250'}),
        help_text='Maximale Anzahl der Bestellungen pro Import (max. 250)'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Startdatum muss vor dem Enddatum liegen.")
        
        return cleaned_data


class ProductCostForm(forms.Form):
    """Form für Produkteinkaufspreise"""
    
    product_id = forms.IntegerField(widget=forms.HiddenInput())
    cost_price = forms.DecimalField(
        label='Einkaufspreis',
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
    )


class BulkProductCostForm(forms.Form):
    """Form für Bulk-Update von Produkteinkaufspreisen"""
    
    def __init__(self, *args, products=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if products:
            for product in products:
                field_name = f'product_{product.id}'
                self.fields[field_name] = forms.DecimalField(
                    label=f'{product.title}',
                    max_digits=10,
                    decimal_places=2,
                    required=False,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
                )


class SalesFilterForm(forms.Form):
    """Form für Verkaufsdaten-Filter"""
    
    start_date = forms.DateField(
        required=False,
        label='Von',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    end_date = forms.DateField(
        required=False,
        label='Bis',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    product = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Produkt',
        empty_label='Alle Produkte',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if store:
            from .models import ShopifyProduct
            self.fields['product'].queryset = ShopifyProduct.objects.filter(store=store)


class StatisticsExportForm(forms.Form):
    """Form für Statistiken-Export"""
    
    EXPORT_FORMATS = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
    ]
    
    format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Diagramme einschließen'
    )
    
    include_detailed_data = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Detaillierte Daten einschließen'
    )