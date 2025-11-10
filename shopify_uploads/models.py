from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FotogravurImage(models.Model):
    """
    Model für konvertierte Fotogravur-Bilder von Shopify
    """
    # Eindeutige ID für das Bild
    unique_id = models.CharField(max_length=100, unique=True, db_index=True)

    # Das konvertierte S/W-Bild
    image = models.ImageField(upload_to='fotogravur/%Y/%m/')

    # Original-Dateiname (für Referenz)
    original_filename = models.CharField(max_length=255, blank=True)

    # Shopify-Bestellinformationen (optional)
    shopify_order_id = models.CharField(max_length=100, blank=True, null=True)
    shopify_product_id = models.CharField(max_length=100, blank=True, null=True)

    # Verarbeitungseinstellungen (als JSON gespeichert)
    processing_settings = models.JSONField(default=dict, blank=True)
    # Beispiel: {"brightness": 0, "contrast": 0, "threshold": 127, "bg_removed": true}

    # Wunschtext und Schriftart
    custom_text = models.TextField(blank=True)
    font_family = models.CharField(max_length=100, blank=True)

    # Metadaten
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fotogravur_uploads'
    )

    # Bildgröße in KB
    file_size = models.IntegerField(null=True, blank=True, help_text="Größe in Bytes")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fotogravur Bild'
        verbose_name_plural = 'Fotogravur Bilder'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['shopify_order_id']),
        ]

    def __str__(self):
        return f"Fotogravur {self.unique_id} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"

    @property
    def file_size_kb(self):
        """Dateigröße in KB"""
        if self.file_size:
            return round(self.file_size / 1024, 2)
        return 0
