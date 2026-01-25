"""
P-Loom Browser-basierte Tests
Aufrufbar unter /ploom/tests/ (nur für Superuser)
"""
import json
import time
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import (
    PLoomSettings, ProductTheme, PLoomProduct,
    PLoomProductImage, PLoomProductVariant, PLoomHistory, PLoomFavoritePrice
)

User = get_user_model()


class PLoomTestRunner:
    """
    Test-Runner für Browser-basierte Tests.
    Führt alle Tests aus und sammelt Ergebnisse.
    """

    def __init__(self, user):
        self.user = user
        self.results = []
        self.passed = 0
        self.failed = 0
        self.client = Client()
        self.client.force_login(user)

    def run_all_tests(self):
        """Führt alle Tests aus"""
        test_methods = [
            # Model Tests
            ('Model: PLoomSettings erstellen', self.test_create_settings),
            ('Model: ProductTheme erstellen', self.test_create_theme),
            ('Model: PLoomProduct erstellen', self.test_create_product),
            ('Model: PLoomProductVariant erstellen', self.test_create_variant),
            ('Model: PLoomProductImage erstellen', self.test_create_image),
            ('Model: PLoomHistory erstellen', self.test_create_history),
            ('Model: PLoomFavoritePrice erstellen', self.test_create_favorite_price),

            # View Tests
            ('View: Dashboard erreichbar', self.test_dashboard_view),
            ('View: Produktliste erreichbar', self.test_product_list_view),
            ('View: Produkt erstellen Seite', self.test_product_create_view),
            ('View: Theme-Liste erreichbar', self.test_theme_list_view),
            ('View: Einstellungen erreichbar', self.test_settings_view),

            # Form Tests
            ('Form: Produkt speichern', self.test_product_form_save),
            ('Form: Theme speichern', self.test_theme_form_save),

            # API Tests
            ('API: ImageForge Generations', self.test_api_imageforge_generations),
            ('API: ImageForge Mockups', self.test_api_imageforge_mockups),
            ('API: History abrufen', self.test_api_history),
            ('API: Shopify Collections', self.test_api_shopify_collections),

            # Business Logic Tests
            ('Logic: Theme Standard-Werte', self.test_theme_defaults),
            ('Logic: Produkt Status', self.test_product_status),
            ('Logic: Preis-Favoriten Zähler', self.test_favorite_price_counter),
            ('Logic: Varianten Options-String', self.test_variant_option_string),

            # Integration Tests
            ('Integration: Produkt duplizieren', self.test_product_duplicate),
            ('Integration: Bild als Hauptbild setzen', self.test_set_featured_image),
        ]

        for name, test_func in test_methods:
            self._run_test(name, test_func)

        return {
            'results': self.results,
            'passed': self.passed,
            'failed': self.failed,
            'total': len(self.results),
        }

    def _run_test(self, name, test_func):
        """Führt einen einzelnen Test aus"""
        start_time = time.time()
        try:
            test_func()
            duration = time.time() - start_time
            self.results.append({
                'name': name,
                'status': 'passed',
                'duration': f"{duration:.3f}s",
                'error': None
            })
            self.passed += 1
        except AssertionError as e:
            duration = time.time() - start_time
            self.results.append({
                'name': name,
                'status': 'failed',
                'duration': f"{duration:.3f}s",
                'error': str(e)
            })
            self.failed += 1
        except Exception as e:
            duration = time.time() - start_time
            self.results.append({
                'name': name,
                'status': 'error',
                'duration': f"{duration:.3f}s",
                'error': f"{type(e).__name__}: {str(e)}"
            })
            self.failed += 1

    # =========================================================================
    # Model Tests
    # =========================================================================

    def test_create_settings(self):
        """Testet PLoomSettings Erstellung"""
        settings, created = PLoomSettings.objects.get_or_create(
            user=self.user,
            defaults={
                'ai_provider': 'openai',
                'ai_model': 'gpt-4o-mini',
                'writing_style': 'du'
            }
        )
        assert settings.id is not None, "Settings sollte eine ID haben"
        assert settings.user == self.user, "Settings sollte dem User zugeordnet sein"

    def test_create_theme(self):
        """Testet ProductTheme Erstellung"""
        theme = ProductTheme.objects.create(
            user=self.user,
            name=f"Test Theme {time.time()}",
            title_template="{product_name} - Test",
            default_price=Decimal('29.99'),
            default_vendor='Test Vendor'
        )
        assert theme.id is not None, "Theme sollte eine ID haben"
        assert theme.name.startswith("Test Theme"), "Theme Name sollte gesetzt sein"

    def test_create_product(self):
        """Testet PLoomProduct Erstellung"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title=f"Test Produkt {time.time()}",
            description="<p>Test Beschreibung</p>",
            price=Decimal('49.99'),
            status='draft'
        )
        assert product.id is not None, "Produkt sollte eine UUID haben"
        assert product.status == 'draft', "Status sollte 'draft' sein"

    def test_create_variant(self):
        """Testet PLoomProductVariant Erstellung"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title="Varianten-Test Produkt"
        )
        variant = PLoomProductVariant.objects.create(
            product=product,
            option1_name='Größe',
            option1_value='M',
            price=Decimal('39.99'),
            sku='TEST-M-001'
        )
        assert variant.id is not None, "Variante sollte eine ID haben"
        assert variant.sku == 'TEST-M-001', "SKU sollte gesetzt sein"

    def test_create_image(self):
        """Testet PLoomProductImage Erstellung"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title="Bild-Test Produkt"
        )
        image = PLoomProductImage.objects.create(
            product=product,
            source='upload',
            alt_text='Test Alt Text',
            position=0
        )
        assert image.id is not None, "Bild sollte eine ID haben"
        assert image.source == 'upload', "Source sollte 'upload' sein"

    def test_create_history(self):
        """Testet PLoomHistory Erstellung"""
        history = PLoomHistory.objects.create(
            user=self.user,
            field_type='title',
            content='Test Titel für History',
            ai_model_used='gpt-4o-mini'
        )
        assert history.id is not None, "History sollte eine ID haben"
        assert history.field_type == 'title', "field_type sollte 'title' sein"

    def test_create_favorite_price(self):
        """Testet PLoomFavoritePrice Erstellung"""
        fav = PLoomFavoritePrice.objects.create(
            user=self.user,
            price=Decimal('19.99'),
            label='Standard'
        )
        assert fav.id is not None, "FavoritePrice sollte eine ID haben"
        assert fav.usage_count == 0, "usage_count sollte 0 sein"

    # =========================================================================
    # View Tests
    # =========================================================================

    def test_dashboard_view(self):
        """Testet Dashboard View"""
        response = self.client.get(reverse('ploom:dashboard'))
        assert response.status_code == 200, f"Dashboard sollte 200 zurückgeben, nicht {response.status_code}"

    def test_product_list_view(self):
        """Testet Produktliste View"""
        response = self.client.get(reverse('ploom:product_list'))
        assert response.status_code == 200, f"Produktliste sollte 200 zurückgeben, nicht {response.status_code}"

    def test_product_create_view(self):
        """Testet Produkt erstellen View"""
        response = self.client.get(reverse('ploom:product_create'))
        assert response.status_code == 200, f"Produkt erstellen sollte 200 zurückgeben, nicht {response.status_code}"

    def test_theme_list_view(self):
        """Testet Theme-Liste View"""
        response = self.client.get(reverse('ploom:theme_list'))
        assert response.status_code == 200, f"Theme-Liste sollte 200 zurückgeben, nicht {response.status_code}"

    def test_settings_view(self):
        """Testet Einstellungen View"""
        response = self.client.get(reverse('ploom:settings'))
        assert response.status_code == 200, f"Einstellungen sollte 200 zurückgeben, nicht {response.status_code}"

    # =========================================================================
    # Form Tests
    # =========================================================================

    def test_product_form_save(self):
        """Testet Produkt-Formular speichern"""
        response = self.client.post(reverse('ploom:product_create'), {
            'title': f'Form Test Produkt {time.time()}',
            'description': 'Test Beschreibung via Form',
            'price': '29.99',
            'status': 'draft'
        })
        # Sollte zu product_edit redirecten (302) oder Formular anzeigen (200)
        assert response.status_code in [200, 302], f"Form sollte 200 oder 302 zurückgeben, nicht {response.status_code}"

    def test_theme_form_save(self):
        """Testet Theme-Formular speichern"""
        response = self.client.post(reverse('ploom:theme_create'), {
            'name': f'Form Test Theme {time.time()}',
            'title_template': '{product_name}',
            'default_price': '19.99'
        })
        # Sollte zu theme_list redirecten (302) oder Formular anzeigen (200)
        assert response.status_code in [200, 302], f"Form sollte 200 oder 302 zurückgeben, nicht {response.status_code}"

    # =========================================================================
    # API Tests
    # =========================================================================

    def test_api_imageforge_generations(self):
        """Testet ImageForge Generations API"""
        response = self.client.get(reverse('ploom:api_imageforge_generations'))
        assert response.status_code == 200, f"API sollte 200 zurückgeben, nicht {response.status_code}"
        data = json.loads(response.content)
        assert 'success' in data, "Response sollte 'success' enthalten"

    def test_api_imageforge_mockups(self):
        """Testet ImageForge Mockups API"""
        response = self.client.get(reverse('ploom:api_imageforge_mockups'))
        assert response.status_code == 200, f"API sollte 200 zurückgeben, nicht {response.status_code}"
        data = json.loads(response.content)
        assert 'success' in data, "Response sollte 'success' enthalten"

    def test_api_history(self):
        """Testet History API"""
        # Erst einen History-Eintrag erstellen
        PLoomHistory.objects.create(
            user=self.user,
            field_type='title',
            content='API Test History'
        )
        response = self.client.get(reverse('ploom:api_history', args=['title']))
        assert response.status_code == 200, f"API sollte 200 zurückgeben, nicht {response.status_code}"
        data = json.loads(response.content)
        assert data.get('success') == True, "Response sollte success=True sein"

    def test_api_shopify_collections(self):
        """Testet Shopify Collections API"""
        response = self.client.get(reverse('ploom:api_shopify_collections'))
        # Ohne Store sollte ein Fehler zurückkommen, aber 200 Status
        assert response.status_code == 200, f"API sollte 200 zurückgeben, nicht {response.status_code}"

    # =========================================================================
    # Business Logic Tests
    # =========================================================================

    def test_theme_defaults(self):
        """Testet Theme Standard-Werte auf Produkt"""
        theme = ProductTheme.objects.create(
            user=self.user,
            name=f"Defaults Test Theme {time.time()}",
            default_price=Decimal('99.99'),
            default_vendor='Default Vendor',
            default_tags='tag1, tag2',
            is_default=True
        )
        # Das Theme sollte jetzt das Standard-Theme sein
        default_theme = ProductTheme.objects.filter(user=self.user, is_default=True).first()
        assert default_theme is not None, "Es sollte ein Standard-Theme geben"
        assert default_theme.default_price == Decimal('99.99'), "Standard-Preis sollte 99.99 sein"

    def test_product_status(self):
        """Testet Produkt-Status Werte"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title="Status Test Produkt",
            status='draft'
        )
        assert product.get_status_display() == 'Entwurf', "Status-Display sollte 'Entwurf' sein"

        product.status = 'ready'
        product.save()
        assert product.get_status_display() == 'Bereit zum Upload', "Status-Display sollte 'Bereit zum Upload' sein"

    def test_favorite_price_counter(self):
        """Testet Favoriten-Preis Zähler"""
        fav = PLoomFavoritePrice.objects.create(
            user=self.user,
            price=Decimal('14.99'),
            label='Counter Test'
        )
        assert fav.usage_count == 0, "Anfangs sollte usage_count 0 sein"

        fav.increment_usage()
        fav.refresh_from_db()
        assert fav.usage_count == 1, "Nach increment sollte usage_count 1 sein"

    def test_variant_option_string(self):
        """Testet Varianten option_string Property"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title="Option String Test"
        )
        variant = PLoomProductVariant.objects.create(
            product=product,
            option1_name='Größe',
            option1_value='L',
            option2_name='Farbe',
            option2_value='Blau'
        )
        expected = 'Größe: L, Farbe: Blau'
        assert variant.option_string == expected, f"option_string sollte '{expected}' sein, nicht '{variant.option_string}'"

    # =========================================================================
    # Integration Tests
    # =========================================================================

    def test_product_duplicate(self):
        """Testet Produkt-Duplizierung"""
        # Original-Produkt erstellen
        original = PLoomProduct.objects.create(
            user=self.user,
            title="Original Produkt",
            description="Original Beschreibung",
            price=Decimal('59.99'),
            tags='original, test'
        )
        # Variante hinzufügen
        PLoomProductVariant.objects.create(
            product=original,
            option1_name='Größe',
            option1_value='M',
            price=Decimal('59.99')
        )

        # Duplizieren via View
        response = self.client.get(reverse('ploom:product_duplicate', args=[original.id]))
        assert response.status_code == 302, "Duplicate sollte redirect (302) sein"

        # Prüfen ob Kopie existiert
        copies = PLoomProduct.objects.filter(
            user=self.user,
            title__contains='(Kopie)'
        )
        assert copies.exists(), "Es sollte eine Kopie geben"

    def test_set_featured_image(self):
        """Testet Hauptbild setzen"""
        product = PLoomProduct.objects.create(
            user=self.user,
            title="Featured Image Test"
        )
        img1 = PLoomProductImage.objects.create(
            product=product,
            source='upload',
            is_featured=True,
            position=0
        )
        img2 = PLoomProductImage.objects.create(
            product=product,
            source='upload',
            is_featured=False,
            position=1
        )

        # img2 als Hauptbild setzen
        response = self.client.post(
            reverse('ploom:api_image_set_featured', args=[product.id, img2.id])
        )
        assert response.status_code == 200, f"API sollte 200 zurückgeben, nicht {response.status_code}"

        img1.refresh_from_db()
        img2.refresh_from_db()
        assert img2.is_featured == True, "img2 sollte jetzt Hauptbild sein"
        assert img1.is_featured == False, "img1 sollte nicht mehr Hauptbild sein"


# Cleanup-Funktion für Test-Daten
def cleanup_test_data(user):
    """Löscht alle Test-Daten eines Users"""
    PLoomProduct.objects.filter(
        user=user,
        title__contains='Test'
    ).delete()
    ProductTheme.objects.filter(
        user=user,
        name__contains='Test'
    ).delete()
    PLoomHistory.objects.filter(
        user=user,
        content__contains='Test'
    ).delete()
    PLoomFavoritePrice.objects.filter(
        user=user,
        label__contains='Test'
    ).delete()
