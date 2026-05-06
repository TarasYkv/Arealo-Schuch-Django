"""Lasergravur-App: Auto-Workflow für personalisierte Topf-Bestellungen.

Workflow:
1. Polling alle 2 Min holt neue Shopify-Orders mit Topf-Produkten
2. Properties werden geparst → automatisch ein LaserDesign erstellt
3. Mitarbeiter öffnet UI, prüft + ändert via Editor (Live-Preview)
4. Bestätigt → PNG (300 DPI, schwarz auf transparent) wird generiert
5. Browser-Download triggert
6. Status zurück nach Shopify als Tag

Topf-Modelle:
- designer (Natural Cream Designer-Topf, 10×10 cm)
- glossy (Designer Glossy Edition, 10×10 cm)
- birthtree (Birthtree-Edition, 10×10 cm)
- fotogravur (Fotogravur, 10×10 cm)
- hochzeit (Hochzeits-Edition, 10×10 cm)
- minipalm (Mini Palm, 6,5×6,5 cm)
- minisolo (Mini Solo, 6,5×6,5 cm)
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


# Topf-Modell-Definitionen — erweiterbar
TOPF_MODELS = [
    ('designer', 'Designer (Natural Cream)'),
    ('glossy', 'Designer Glossy (Hochglanz)'),
    ('glossywhite', 'Glossywhite (Geburtstag)'),
    ('birthtree', 'Birthtree'),
    ('fotogravur', 'Fotogravur (Bild-Upload)'),
    ('hochzeit', 'Hochzeit'),
    ('hochzeit_glossy', 'Hochzeit Glossy'),
    ('glossy_geburt', 'Glossy Geburt (Babygeschenk)'),
    ('minipalm', 'Mini Palm'),
    ('minisolo', 'Mini Solo'),
    ('unknown', 'Unbekanntes Topf-Modell — manuell'),
]

# Gravur-Größe pro Modell-Familie
GRAVUR_SIZES_CM = {
    'designer': (10.0, 10.0),
    'glossy': (10.0, 10.0),
    'glossywhite': (10.0, 10.0),
    'birthtree': (10.0, 10.0),
    'fotogravur': (10.0, 10.0),
    'hochzeit': (10.0, 10.0),
    'hochzeit_glossy': (10.0, 10.0),
    'glossy_geburt': (10.0, 10.0),
    'minipalm': (6.5, 6.5),
    'minisolo': (6.5, 6.5),
}

# Schriftarten — Naturmacher-Designer-Topf bietet diese 6 zur Auswahl
FONT_CHOICES = [
    ('Pixie Ring', 'Pixie Ring'),
    ('Dreaming Outloud', 'Dreaming Outloud'),
    ('Montserrat', 'Montserrat'),
    ('Allura', 'Allura'),
    ('Bebas Neue', 'Bebas Neue'),
    ('Amatic SC', 'Amatic SC'),
]

ALIGN_H_CHOICES = [
    ('left', 'Links'),
    ('center', 'Mitte'),
    ('right', 'Rechts'),
]
ALIGN_V_CHOICES = [
    ('top', 'Oben'),
    ('center', 'Mitte'),
    ('bottom', 'Unten'),
]


class LaserSettings(models.Model):
    """Pro User: welche Shopify-Produkte gepollt werden + welcher Store."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lasergravur_settings',
    )
    # FK auf bestehenden Shopify-Store (aus shopify_manager-App)
    shopify_store = models.ForeignKey(
        'shopify_manager.ShopifyStore', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_constraint=False,
    )
    # Welche Produkt-Handles werden gepollt — initial nur designer-Topf,
    # erweiterbar pro User um weitere Modelle (glossy, mini, etc.).
    relevant_product_handles = models.JSONField(
        default=list, blank=True,
        help_text=(
            'Liste der Shopify-Produkt-Handles, die als Lasergravur-Aufträge '
            'erkannt werden sollen, z.B. ["mein-blumentopf-designer-..."].'
        ),
    )
    # Mapping: Produkt-Handle → Topf-Modell-Slug. Wird bei der Auto-Erkennung
    # genutzt, um das richtige Renderer-Template zu wählen.
    handle_to_model = models.JSONField(
        default=dict, blank=True,
        help_text=(
            'Mapping {handle: model_slug}, z.B. '
            '{"mein-blumentopf-designer-...": "designer"}.'
        ),
    )
    # Shopify gibt product_handle in line_items leer zurück, daher zusätzlich
    # die product_ids cachen (handle → product_id Mapping). Wird beim Speichern
    # von relevant_product_handles automatisch aufgefüllt.
    product_id_to_model = models.JSONField(
        default=dict, blank=True,
        help_text=(
            'Mapping {shopify_product_id: model_slug} — wird automatisch aus '
            'handle_to_model durch Shopify-API-Lookup beim Speichern befüllt.'
        ),
    )
    last_polled_at = models.DateTimeField(null=True, blank=True)
    poll_interval_minutes = models.IntegerField(default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lasergravur-Einstellungen'
        verbose_name_plural = 'Lasergravur-Einstellungen'

    def __str__(self):
        return f'Lasergravur-Settings {self.user}'


class LaserOrder(models.Model):
    """Eine Bestellung die graviert werden muss."""
    STATUS_PENDING = 'pending'
    STATUS_AUTO_DESIGNED = 'auto_designed'
    STATUS_NEEDS_MANUAL = 'needs_manual'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_DOWNLOADED = 'downloaded'
    STATUS_ENGRAVED = 'engraved'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Eingegangen'),
        (STATUS_AUTO_DESIGNED, 'Auto-Design erstellt'),
        (STATUS_NEEDS_MANUAL, 'Manuelle Konfiguration nötig'),
        (STATUS_CONFIRMED, 'Bestätigt'),
        (STATUS_DOWNLOADED, 'PNG heruntergeladen'),
        (STATUS_ENGRAVED, 'Graviert'),
        (STATUS_FAILED, 'Fehler'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lasergravur_orders',
    )

    # Shopify-Daten
    shopify_order_id = models.CharField(max_length=64, db_index=True)
    shopify_order_number = models.CharField(max_length=32, blank=True)
    shopify_customer_name = models.CharField(max_length=255, blank=True)
    shopify_customer_email = models.EmailField(blank=True)
    shopify_product_handle = models.CharField(max_length=255, blank=True)
    shopify_product_title = models.CharField(max_length=255, blank=True)
    shopify_line_item_id = models.CharField(max_length=64, blank=True)
    shopify_line_item_quantity = models.IntegerField(default=1)
    raw_properties = models.JSONField(default=dict, blank=True,
                                       help_text='Original Shopify line_item.properties.')

    topf_model = models.CharField(max_length=32, choices=TOPF_MODELS, default='designer')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)

    # Zeitstempel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    engraved_at = models.DateTimeField(null=True, blank=True)
    shopify_order_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['shopify_order_id']),
        ]
        verbose_name = 'Lasergravur-Auftrag'
        verbose_name_plural = 'Lasergravur-Aufträge'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'shopify_order_id', 'shopify_line_item_id'],
                name='unique_order_lineitem_per_user',
            ),
        ]

    def __str__(self):
        return f'#{self.shopify_order_number} {self.shopify_customer_name} ({self.topf_model})'

    @property
    def gravur_size_cm(self) -> tuple:
        return GRAVUR_SIZES_CM.get(self.topf_model, (10.0, 10.0))

    @property
    def gravur_size_px(self) -> tuple:
        """Pixel-Größe @ 300 DPI für PNG-Render."""
        cm_w, cm_h = self.gravur_size_cm
        return (int(cm_w / 2.54 * 300), int(cm_h / 2.54 * 300))


class LaserDesign(models.Model):
    """Editierbares Design pro Auftrag — Mitarbeiter ändert hier Text/Icon/Position."""
    order = models.OneToOneField(
        LaserOrder, on_delete=models.CASCADE, related_name='design',
    )

    # Text-Zeilen (4 verfügbar, aber nicht alle müssen gefüllt sein)
    text_1 = models.CharField(max_length=200, blank=True)
    text_2 = models.CharField(max_length=200, blank=True)
    text_3 = models.CharField(max_length=200, blank=True)
    text_4 = models.CharField(max_length=200, blank=True)

    # Schrift
    font = models.CharField(max_length=32, choices=FONT_CHOICES, default='Allura')
    font_size_pt = models.IntegerField(
        default=48,
        help_text='Schriftgröße in pt (300 DPI Render).',
    )

    # Icon (1-108, oder null = kein Icon)
    icon_id = models.IntegerField(null=True, blank=True,
                                   help_text='Icon-Nummer aus Naturmacher-Library (1-108).')
    icon_size_mm = models.FloatField(default=20.0,
                                      help_text='Icon-Höhe in mm.')

    # Layout
    alignment_h = models.CharField(max_length=8, choices=ALIGN_H_CHOICES, default='center')
    alignment_v = models.CharField(max_length=8, choices=ALIGN_V_CHOICES, default='center')
    offset_x_mm = models.FloatField(default=0.0)
    offset_y_mm = models.FloatField(default=0.0)

    # Render-Cache
    last_rendered_png = models.CharField(max_length=500, blank=True,
                                          help_text='Pfad zur zuletzt gerenderten PNG (relativ zu MEDIA_ROOT).')
    last_rendered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lasergravur-Design'
        verbose_name_plural = 'Lasergravur-Designs'

    def __str__(self):
        return f'Design für {self.order}'

    @property
    def texts(self) -> list:
        """Liefert nicht-leere Text-Zeilen als Liste."""
        return [t for t in [self.text_1, self.text_2, self.text_3, self.text_4] if t]
