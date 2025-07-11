from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q
import requests
import json
from .models import (
    ShopifyStore, SalesData, ShopifyProduct, 
    SalesStatistics, RecurringCost, AdsCost, ShippingProfile
)
from .shopify_api import ShopifyAPIClient


class SalesDataImportService:
    """Service zum Importieren von Verkaufsdaten aus Shopify"""
    
    def __init__(self, store):
        self.store = store
        self.api_client = ShopifyAPIClient(store)
    
    def import_orders(self, start_date=None, end_date=None, limit=250):
        """
        Importiert Bestellungen aus Shopify mit Pagination
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=90)
        if not end_date:
            end_date = timezone.now()
        
        # Formatiere Daten für Shopify API
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S')
        end_date_str = end_date.strftime('%Y-%m-%dT%H:%M:%S')
        
        imported_count = 0
        page_info = None
        
        while True:
            # Shopify Orders API mit Pagination
            url = f"{self.store.get_api_url()}/orders.json"
            params = {
                'status': 'any',
                'financial_status': 'paid',  # Nur bezahlte Bestellungen
                'created_at_min': start_date_str,
                'created_at_max': end_date_str,
                'limit': min(limit, 250),  # Shopify max limit
                'fields': 'id,created_at,total_price,currency,financial_status,gateway,line_items,tax_lines,shipping_lines,total_tax,shipping_address,billing_address'
            }
            
            if page_info:
                params['page_info'] = page_info
            
            headers = {
                'X-Shopify-Access-Token': self.store.access_token,
                'Content-Type': 'application/json'
            }
            
            try:
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                
                orders_data = response.json()
                orders = orders_data.get('orders', [])
                
                if not orders:
                    break
                
                for order in orders:
                    imported_count += self._process_order(order)
                
                # Prüfe auf weitere Seiten
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extrahiere page_info aus Link header
                    import re
                    match = re.search(r'page_info=([^&">]+)', link_header)
                    if match:
                        page_info = match.group(1)
                    else:
                        break
                else:
                    break
                    
            except requests.exceptions.RequestException as e:
                return False, f"Fehler beim Importieren: {str(e)}"
            except Exception as e:
                return False, f"Unerwarteter Fehler: {str(e)}"
        
        return True, f"Erfolgreich {imported_count} Verkaufsdaten importiert"
    
    def _process_order(self, order):
        """
        Verarbeitet eine einzelne Bestellung und extrahiert alle verfügbaren Shopify-Daten
        """
        order_id = order.get('id')
        order_date = datetime.fromisoformat(order.get('created_at').replace('Z', '+00:00'))
        
        # Gesamtpreise und Steuern direkt aus Shopify
        total_price = Decimal(str(order.get('total_price', '0.00')))
        order_total_tax = Decimal(str(order.get('total_tax', '0.00')))
        
        # Berechne Shopify und PayPal Gebühren für die gesamte Bestellung
        shopify_fee = self._calculate_shopify_fee(order)
        paypal_fee = self._calculate_paypal_fee(order)
        
        # Versandkosten aus der Bestellung (was der Kunde bezahlt hat)
        shipping_lines = order.get('shipping_lines', [])
        order_shipping_cost = sum(Decimal(str(line.get('price', '0.00'))) for line in shipping_lines)
        
        # Extrahiere detaillierte Versandinformationen
        shipping_details = self._extract_shipping_details(order)
        
        # Steuerdetails aus tax_lines
        tax_lines = order.get('tax_lines', [])
        total_tax_from_lines = sum(Decimal(str(tax.get('price', '0.00'))) for tax in tax_lines)
        
        # Verwende die detaillierten Steuerdaten falls verfügbar
        final_tax_amount = total_tax_from_lines if total_tax_from_lines > 0 else order_total_tax
        
        line_items = order.get('line_items', [])
        imported_count = 0
        total_line_items = len(line_items)
        
        for line_item in line_items:
            line_item_id = line_item.get('id')
            product_id = line_item.get('product_id')
            variant_id = line_item.get('variant_id')
            
            # Finde das lokale Produkt
            product = None
            if product_id:
                try:
                    product = ShopifyProduct.objects.get(
                        shopify_id=str(product_id),
                        store=self.store
                    )
                except ShopifyProduct.DoesNotExist:
                    # Versuche Import des Produkts falls noch nicht vorhanden
                    self._try_import_product(product_id)
                    try:
                        product = ShopifyProduct.objects.get(
                            shopify_id=str(product_id),
                            store=self.store
                        )
                    except ShopifyProduct.DoesNotExist:
                        continue
            
            # Berechne anteilige Kosten basierend auf Artikelwert
            item_total = Decimal(str(line_item.get('price', '0.00'))) * line_item.get('quantity', 1)
            item_percentage = item_total / total_price if total_price > 0 else Decimal('0')
            
            # Verteilte Kosten
            item_shopify_fee = shopify_fee * item_percentage
            item_paypal_fee = paypal_fee * item_percentage
            item_shipping_cost = order_shipping_cost * item_percentage
            
            # Einkaufskosten aus Shopify line_item extrahieren
            cost_price = None
            
            # 1. Versuche cost_per_item direkt aus line_item (falls verfügbar)
            if line_item.get('cost_per_item'):
                cost_price = Decimal(str(line_item.get('cost_per_item', '0.00')))
            
            # 2. Falls nicht verfügbar, versuche über Variant API
            if not cost_price and variant_id:
                cost_price = self._get_variant_cost(variant_id)
            
            # 3. Fallback: Versuche über Inventory Item API
            if not cost_price and variant_id:
                cost_price = self._get_inventory_cost(variant_id)
            
            # Steuern für diesen Line Item berechnen
            line_item_tax = self._calculate_line_item_tax(line_item, final_tax_amount, item_total, total_price)
            
            # Berechne Versandkosten basierend auf Versandprofil (falls gesetzt)
            profile_shipping_cost = self._calculate_shipping_cost(product, order)
            actual_shipping_cost = profile_shipping_cost if profile_shipping_cost > 0 else None
            
            # Erstelle oder aktualisiere Verkaufsdaten
            sales_data, created = SalesData.objects.get_or_create(
                shopify_order_id=str(order_id),
                shopify_line_item_id=str(line_item_id),
                defaults={
                    'store': self.store,
                    'product': product,
                    'order_date': order_date,
                    'quantity': line_item.get('quantity', 1),
                    'unit_price': Decimal(str(line_item.get('price', '0.00'))),
                    'total_price': item_total,
                    'cost_price': cost_price,  # Einkaufskosten aus Shopify
                    'shop_shipping_cost': item_shipping_cost,  # Was der Kunde bezahlt hat
                    'actual_shipping_cost': actual_shipping_cost,  # Tatsächliche Versandkosten
                    'shipping_cost': item_shipping_cost,  # Legacy-Feld
                    'shopify_fee': item_shopify_fee,
                    'paypal_fee': item_paypal_fee,
                    'payment_gateway_fee': self._calculate_payment_gateway_fee(order, item_percentage),
                    'tax_amount': line_item_tax,
                    'payment_gateway': order.get('gateway', ''),  # Payment Gateway Information
                }
            )
            
            if created:
                imported_count += 1
        
        return imported_count
    
    def _try_import_product(self, product_id):
        """
        Versucht ein Produkt zu importieren falls es noch nicht existiert
        """
        try:
            url = f"{self.store.get_api_url()}/products/{product_id}.json"
            headers = {
                'X-Shopify-Access-Token': self.store.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                product_data = response.json().get('product', {})
                
                # Erstelle Produkt
                ShopifyProduct.objects.create(
                    shopify_id=str(product_id),
                    store=self.store,
                    title=product_data.get('title', 'Unknown Product'),
                    handle=product_data.get('handle', ''),
                    body_html=product_data.get('body_html', ''),
                    vendor=product_data.get('vendor', ''),
                    product_type=product_data.get('product_type', ''),
                    status=product_data.get('status', 'active'),
                    tags=product_data.get('tags', ''),
                    raw_shopify_data=product_data,
                    shopify_created_at=datetime.fromisoformat(product_data.get('created_at', '').replace('Z', '+00:00')) if product_data.get('created_at') else None,
                    shopify_updated_at=datetime.fromisoformat(product_data.get('updated_at', '').replace('Z', '+00:00')) if product_data.get('updated_at') else None,
                )
                
        except Exception as e:
            print(f"Fehler beim Importieren des Produkts {product_id}: {str(e)}")
    
    def _calculate_shopify_fee(self, order):
        """
        Berechnet Shopify Gebühren (Standard: 2.9% + 0.30€)
        """
        total_price = Decimal(str(order.get('total_price', '0.00')))
        return (total_price * Decimal('0.029')) + Decimal('0.30')
    
    def _calculate_paypal_fee(self, order):
        """
        Berechnet PayPal Gebühren basierend auf Account-Typ und Transaktionsvolumen
        """
        gateway = order.get('gateway', '')
        if 'paypal' not in gateway.lower():
            return Decimal('0.00')
        
        total_price = Decimal(str(order.get('total_price', '0.00')))
        currency = order.get('currency', 'EUR')
        
        # PayPal-Gebührenstruktur für verschiedene Account-Typen
        paypal_config = self._get_paypal_config()
        
        if paypal_config['account_type'] == 'business':
            # Business Account Gebühren
            return self._calculate_business_paypal_fee(total_price, currency, paypal_config)
        elif paypal_config['account_type'] == 'handler':
            # Handler Account Gebühren (reduzierte Gebühren)
            return self._calculate_handler_paypal_fee(total_price, currency, paypal_config)
        else:
            # Standard PayPal Gebühren
            return self._calculate_standard_paypal_fee(total_price, currency)
    
    def _get_paypal_config(self):
        """
        Holt PayPal-Konfiguration für den Store
        """
        # Fallback auf Standard-Werte falls keine Konfiguration vorhanden
        return {
            'account_type': getattr(self.store, 'paypal_account_type', 'standard'),
            'monthly_volume': getattr(self.store, 'paypal_monthly_volume', 0),
            'handler_fee_rate': getattr(self.store, 'paypal_handler_rate', Decimal('0.0199')),  # 1.99%
            'handler_fixed_fee': getattr(self.store, 'paypal_handler_fixed_fee', Decimal('0.35')),
        }
    
    def _calculate_standard_paypal_fee(self, amount, currency):
        """
        Standard PayPal Gebühren (2.49% + 0.35€)
        """
        if currency == 'EUR':
            return (amount * Decimal('0.0249')) + Decimal('0.35')
        elif currency == 'USD':
            return (amount * Decimal('0.0249')) + Decimal('0.49')
        elif currency == 'GBP':
            return (amount * Decimal('0.0249')) + Decimal('0.30')
        else:
            # Fallback für andere Währungen
            return (amount * Decimal('0.0249')) + Decimal('0.35')
    
    def _calculate_business_paypal_fee(self, amount, currency, config):
        """
        Business Account PayPal Gebühren (gestaffelt nach Volumen)
        """
        monthly_volume = config.get('monthly_volume', 0)
        
        if currency == 'EUR':
            if monthly_volume >= 25000:  # Ab 25.000€ monatlich
                return (amount * Decimal('0.0199')) + Decimal('0.35')  # 1.99%
            elif monthly_volume >= 5000:  # Ab 5.000€ monatlich
                return (amount * Decimal('0.0229')) + Decimal('0.35')  # 2.29%
            else:
                return (amount * Decimal('0.0249')) + Decimal('0.35')  # 2.49%
        else:
            return self._calculate_standard_paypal_fee(amount, currency)
    
    def _calculate_handler_paypal_fee(self, amount, currency, config):
        """
        Handler Account PayPal Gebühren (reduzierte Gebühren für zertifizierte Handler)
        """
        rate = config.get('handler_fee_rate', Decimal('0.0199'))
        fixed_fee = config.get('handler_fixed_fee', Decimal('0.35'))
        
        if currency == 'EUR':
            return (amount * rate) + fixed_fee
        elif currency == 'USD':
            return (amount * rate) + Decimal('0.49')
        elif currency == 'GBP':
            return (amount * rate) + Decimal('0.30')
        else:
            return (amount * rate) + fixed_fee
    
    def _calculate_payment_gateway_fee(self, order, item_percentage):
        """
        Berechnet andere Payment Gateway Gebühren (z.B. Stripe, Klarna)
        """
        gateway = order.get('gateway', '').lower()
        total_price = Decimal(str(order.get('total_price', '0.00')))
        
        # Stripe Gebühren
        if 'stripe' in gateway:
            fee = (total_price * Decimal('0.0149')) + Decimal('0.25')
            return fee * item_percentage
        
        # Klarna Gebühren
        elif 'klarna' in gateway:
            fee = total_price * Decimal('0.0329')
            return fee * item_percentage
        
        # Sofortüberweisung
        elif 'sofort' in gateway:
            fee = total_price * Decimal('0.009')
            return fee * item_percentage
        
        return Decimal('0.00')
    
    def _get_variant_cost(self, variant_id):
        """
        Holt die Einkaufskosten für eine Variante aus der Shopify API
        """
        try:
            url = f"{self.store.get_api_url()}/variants/{variant_id}.json"
            headers = {
                'X-Shopify-Access-Token': self.store.access_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                variant_data = response.json().get('variant', {})
                inventory_item_id = variant_data.get('inventory_item_id')
                
                if inventory_item_id:
                    # Hole Inventory Item für cost_per_item
                    inventory_url = f"{self.store.get_api_url()}/inventory_items/{inventory_item_id}.json"
                    inventory_response = requests.get(inventory_url, headers=headers)
                    
                    if inventory_response.status_code == 200:
                        inventory_data = inventory_response.json().get('inventory_item', {})
                        cost = inventory_data.get('cost')
                        if cost:
                            return Decimal(str(cost))
                            
        except Exception as e:
            print(f"Fehler beim Abrufen der Variant-Kosten {variant_id}: {str(e)}")
            
        return None
    
    def _get_inventory_cost(self, variant_id):
        """
        Alternative Methode um Inventory Item Kosten zu holen
        """
        try:
            # Erst die Variant-Daten holen um inventory_item_id zu bekommen
            variant_url = f"{self.store.get_api_url()}/variants/{variant_id}.json"
            headers = {
                'X-Shopify-Access-Token': self.store.access_token,
                'Content-Type': 'application/json'
            }
            
            variant_response = requests.get(variant_url, headers=headers)
            if variant_response.status_code == 200:
                variant_data = variant_response.json().get('variant', {})
                inventory_item_id = variant_data.get('inventory_item_id')
                
                if inventory_item_id:
                    # Jetzt die Inventory Item Daten holen
                    inventory_url = f"{self.store.get_api_url()}/inventory_items/{inventory_item_id}.json"
                    inventory_response = requests.get(inventory_url, headers=headers)
                    
                    if inventory_response.status_code == 200:
                        inventory_data = inventory_response.json().get('inventory_item', {})
                        cost = inventory_data.get('cost')
                        if cost and cost != '0.00':
                            return Decimal(str(cost))
                            
        except Exception as e:
            print(f"Fehler beim Abrufen der Inventory-Kosten {variant_id}: {str(e)}")
            
        return None
    
    def _calculate_line_item_tax(self, line_item, total_tax, item_total, order_total):
        """
        Berechnet die Steuern für einen Line Item basierend auf dem Verhältnis zum Gesamtpreis
        """
        if order_total == 0:
            return Decimal('0.00')
        
        # Prüfe ob es direkte Steuerdaten im Line Item gibt
        if line_item.get('tax_lines'):
            tax_lines = line_item.get('tax_lines', [])
            item_tax = sum(Decimal(str(tax.get('price', '0.00'))) for tax in tax_lines)
            return item_tax
        
        # Fallback: Proportionale Verteilung der Gesamtsteuern
        item_percentage = item_total / order_total
        return total_tax * item_percentage
    
    def _calculate_shipping_cost(self, product, order):
        """
        Berechnet Versandkosten basierend auf Versandprofil
        """
        if not product:
            return Decimal('0.00')
        
        try:
            shipping_profile = product.shipping_profile.shipping_profile
            return shipping_profile.shipping_cost
        except:
            return Decimal('0.00')
    
    def _extract_shipping_details(self, order):
        """
        Extrahiert detaillierte Versandinformationen aus der Shopify-Bestellung
        """
        shipping_lines = order.get('shipping_lines', [])
        shipping_details = {}
        
        for line in shipping_lines:
            shipping_details.update({
                'method': line.get('title', 'Unknown'),
                'carrier': line.get('carrier_identifier', 'Unknown'),
                'price': Decimal(str(line.get('price', '0.00'))),
                'discount': Decimal(str(line.get('discounted_price', '0.00'))),
                'tax': sum(Decimal(str(tax.get('price', '0.00'))) for tax in line.get('tax_lines', []))
            })
        
        return shipping_details
    
    def _calculate_tax_amount(self, line_item):
        """
        Berechnet Steuerbetrag aus Line Item
        """
        tax_lines = line_item.get('tax_lines', [])
        total_tax = Decimal('0.00')
        
        for tax_line in tax_lines:
            total_tax += Decimal(str(tax_line.get('price', '0.00')))
        
        return total_tax


class SalesStatisticsService:
    """Service zur Berechnung von Verkaufsstatistiken"""
    
    def __init__(self, store):
        self.store = store
    
    def calculate_statistics(self, start_date, end_date, period_type='daily'):
        """
        Berechnet Statistiken für einen bestimmten Zeitraum
        """
        # Hole Verkaufsdaten für den Zeitraum
        sales_data = SalesData.objects.filter(
            store=self.store,
            order_date__range=[start_date, end_date]
        )
        
        # Grundstatistiken
        total_orders = sales_data.values('shopify_order_id').distinct().count()
        total_revenue = sales_data.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0.00')
        total_cost = sales_data.aggregate(
            total_cost=Sum('cost_price') * Sum('quantity')
        )['total_cost'] or Decimal('0.00')
        
        # Einzelne Kostenarten
        total_shipping_costs = sales_data.aggregate(Sum('shipping_cost'))['shipping_cost__sum'] or Decimal('0.00')
        total_shopify_fees = sales_data.aggregate(Sum('shopify_fee'))['shopify_fee__sum'] or Decimal('0.00')
        total_paypal_fees = sales_data.aggregate(Sum('paypal_fee'))['paypal_fee__sum'] or Decimal('0.00')
        total_tax = sales_data.aggregate(Sum('tax_amount'))['tax_amount__sum'] or Decimal('0.00')
        
        # Werbekosten für den Zeitraum
        ads_costs = AdsCost.objects.filter(
            store=self.store,
            date__range=[start_date.date(), end_date.date()]
        ).aggregate(Sum('cost'))['cost__sum'] or Decimal('0.00')
        
        # Laufende Kosten für den Zeitraum
        recurring_costs = self._calculate_recurring_costs(start_date, end_date)
        
        # Gewinn berechnen
        total_profit = total_revenue - total_cost - total_shipping_costs - total_shopify_fees - total_paypal_fees
        
        return {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'total_tax': total_tax,
            'total_shipping_costs': total_shipping_costs,
            'total_shopify_fees': total_shopify_fees,
            'total_paypal_fees': total_paypal_fees,
            'total_ads_costs': ads_costs,
            'total_recurring_costs': recurring_costs,
            'contribution_margin': total_revenue - total_cost - recurring_costs,
            'margin_percentage': (total_profit / total_revenue * 100) if total_revenue > 0 else 0,
            'roas': (total_revenue / ads_costs) if ads_costs > 0 else 0,
        }
    
    def _calculate_recurring_costs(self, start_date, end_date):
        """
        Berechnet laufende Kosten für einen Zeitraum
        """
        recurring_costs = RecurringCost.objects.filter(
            store=self.store,
            is_active=True,
            start_date__lte=end_date.date()
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=start_date.date())
        )
        
        total_cost = Decimal('0.00')
        days_in_period = (end_date.date() - start_date.date()).days
        
        for cost in recurring_costs:
            if cost.frequency == 'monthly':
                months_in_period = days_in_period / 30.44  # Durchschnittliche Tage pro Monat
                total_cost += cost.amount * Decimal(str(months_in_period))
            elif cost.frequency == 'yearly':
                years_in_period = days_in_period / 365.25
                total_cost += cost.amount * Decimal(str(years_in_period))
            elif cost.frequency == 'one_time':
                # Prüfe ob das Datum im Zeitraum liegt
                if start_date.date() <= cost.start_date <= end_date.date():
                    total_cost += cost.amount
        
        return total_cost
    
    def get_bestsellers(self, start_date, end_date, limit=10):
        """
        Ermittelt die Bestseller für einen Zeitraum
        """
        bestsellers = SalesData.objects.filter(
            store=self.store,
            order_date__range=[start_date, end_date],
            product__isnull=False
        ).values(
            'product__title',
            'product__shopify_id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price'),
            total_orders=Count('shopify_order_id', distinct=True)
        ).order_by('-total_quantity')[:limit]
        
        return list(bestsellers)
    
    def get_time_series_data(self, start_date, end_date, period_type='daily'):
        """
        Erstellt Zeitreihen-Daten für Diagramme
        """
        if period_type == 'daily':
            date_format = '%Y-%m-%d'
            date_trunc = 'day'
        elif period_type == 'weekly':
            date_format = '%Y-%W'
            date_trunc = 'week'
        elif period_type == 'monthly':
            date_format = '%Y-%m'
            date_trunc = 'month'
        else:
            date_format = '%Y-%m-%d'
            date_trunc = 'day'
        
        from django.db.models import DateTimeField
        from django.db.models.functions import Trunc
        
        # Gruppiere Verkaufsdaten nach Zeitraum
        time_series = SalesData.objects.filter(
            store=self.store,
            order_date__range=[start_date, end_date]
        ).annotate(
            period=Trunc('order_date', date_trunc, output_field=DateTimeField())
        ).values('period').annotate(
            revenue=Sum('total_price'),
            orders=Count('shopify_order_id', distinct=True),
            quantity=Sum('quantity')
        ).order_by('period')
        
        return list(time_series)
    
    def save_daily_statistics(self, date=None):
        """
        Speichert tägliche Statistiken in der Datenbank
        """
        if not date:
            date = timezone.now().date()
        
        start_date = timezone.datetime.combine(date, timezone.datetime.min.time())
        end_date = timezone.datetime.combine(date, timezone.datetime.max.time())
        
        if timezone.is_aware(start_date):
            start_date = timezone.make_aware(start_date)
            end_date = timezone.make_aware(end_date)
        
        stats = self.calculate_statistics(start_date, end_date, 'daily')
        
        # Erstelle oder aktualisiere Statistik-Eintrag
        statistic, created = SalesStatistics.objects.get_or_create(
            store=self.store,
            date=date,
            period_type='daily',
            defaults=stats
        )
        
        if not created:
            for key, value in stats.items():
                setattr(statistic, key, value)
            statistic.save()
        
        return statistic