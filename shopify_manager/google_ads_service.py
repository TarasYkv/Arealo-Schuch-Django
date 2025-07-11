import os
from datetime import datetime, timedelta
from decimal import Decimal
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from django.utils import timezone
from .models import GoogleAdsProductData, ShopifyProduct


class GoogleAdsService:
    """Service für Google Ads API Integration"""
    
    def __init__(self, store):
        self.store = store
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialisiert den Google Ads API Client"""
        if not all([
            self.store.google_ads_customer_id,
            self.store.google_ads_developer_token,
            self.store.google_ads_refresh_token,
            self.store.google_ads_client_id,
            self.store.google_ads_client_secret
        ]):
            raise ValueError("Google Ads API Zugangsdaten nicht vollständig konfiguriert")
        
        # Konfiguration für Google Ads Client
        config = {
            'developer_token': self.store.google_ads_developer_token,
            'refresh_token': self.store.google_ads_refresh_token,
            'client_id': self.store.google_ads_client_id,
            'client_secret': self.store.google_ads_client_secret,
            'login_customer_id': self.store.google_ads_customer_id.replace('-', ''),
        }
        
        try:
            self.client = GoogleAdsClient.load_from_dict(config)
        except Exception as e:
            raise ValueError(f"Fehler beim Initialisieren des Google Ads Clients: {str(e)}")
    
    def get_shopping_performance_report(self, start_date, end_date):
        """
        Holt Shopping Performance Report für Produkte
        """
        if not self.client:
            return False, "Google Ads Client nicht initialisiert"
        
        customer_id = self.store.google_ads_customer_id.replace('-', '')
        ga_service = self.client.get_service("GoogleAdsService")
        
        # Query für Shopping Performance
        query = """
            SELECT
                shopping_performance_view.merchant_id,
                shopping_performance_view.offer_id,
                shopping_performance_view.product_title,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                segments.date
            FROM shopping_performance_view
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status = 'ENABLED'
            ORDER BY segments.date DESC
        """.format(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            imported_count = 0
            for batch in response:
                for row in batch.results:
                    # Versuche Produkt zu matchen
                    product = self._match_product(row.shopping_performance_view.offer_id)
                    if not product:
                        continue
                    
                    # Konvertiere Mikro-Werte
                    cost = Decimal(str(row.metrics.cost_micros / 1_000_000))
                    
                    # Erstelle oder aktualisiere Daten
                    GoogleAdsProductData.objects.update_or_create(
                        store=self.store,
                        product=product,
                        campaign_id=str(row.campaign.id),
                        date=row.segments.date,
                        defaults={
                            'campaign_name': row.campaign.name,
                            'ad_group_id': str(row.ad_group.id) if row.ad_group.id else None,
                            'ad_group_name': row.ad_group.name if row.ad_group.name else None,
                            'impressions': row.metrics.impressions,
                            'clicks': row.metrics.clicks,
                            'cost': cost,
                            'conversions': Decimal(str(row.metrics.conversions)),
                            'conversion_value': Decimal(str(row.metrics.conversions_value)),
                        }
                    )
                    imported_count += 1
            
            return True, f"{imported_count} Google Ads Produktdaten importiert"
            
        except GoogleAdsException as ex:
            error_messages = []
            for error in ex.failure.errors:
                error_messages.append(f'{error.error_code}: {error.message}')
            return False, f"Google Ads API Fehler: {'; '.join(error_messages)}"
        except Exception as e:
            return False, f"Fehler beim Abrufen der Google Ads Daten: {str(e)}"
    
    def _match_product(self, offer_id):
        """
        Versucht ein Produkt anhand der Offer ID zu matchen
        Google Shopping verwendet oft SKU oder Produkt-ID als Offer ID
        """
        # Versuche verschiedene Matching-Strategien
        
        # 1. Direkte Shopify ID
        product = ShopifyProduct.objects.filter(
            store=self.store,
            shopify_id=offer_id
        ).first()
        
        if product:
            return product
        
        # 2. SKU in Varianten suchen (falls in raw_shopify_data gespeichert)
        for product in ShopifyProduct.objects.filter(store=self.store):
            variants = product.raw_shopify_data.get('variants', [])
            for variant in variants:
                if variant.get('sku') == offer_id:
                    return product
        
        # 3. Handle matchen
        product = ShopifyProduct.objects.filter(
            store=self.store,
            handle=offer_id
        ).first()
        
        return product
    
    def get_campaign_performance(self, start_date, end_date):
        """
        Holt allgemeine Campaign Performance Daten
        """
        if not self.client:
            return []
        
        customer_id = self.store.google_ads_customer_id.replace('-', '')
        ga_service = self.client.get_service("GoogleAdsService")
        
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                segments.date
            FROM campaign
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.advertising_channel_type = 'SHOPPING'
            ORDER BY metrics.cost_micros DESC
        """.format(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            campaigns = []
            for batch in response:
                for row in batch.results:
                    campaigns.append({
                        'campaign_id': row.campaign.id,
                        'campaign_name': row.campaign.name,
                        'status': row.campaign.status.name,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'cost': Decimal(str(row.metrics.cost_micros / 1_000_000)),
                        'conversions': row.metrics.conversions,
                        'conversion_value': Decimal(str(row.metrics.conversions_value)),
                        'date': row.segments.date,
                    })
            
            return campaigns
            
        except Exception as e:
            print(f"Fehler beim Abrufen der Campaign-Daten: {str(e)}")
            return []
    
    def sync_product_ads_data(self, days_back=30):
        """
        Synchronisiert Google Ads Daten für alle Produkte
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        return self.get_shopping_performance_report(start_date, end_date)