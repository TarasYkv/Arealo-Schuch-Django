import secrets
from django.db import models
from django.conf import settings


def _new_uid():
    """Kurze, nicht-erratbare ID fuer die oeffentliche QR-/Abspiel-URL."""
    return secrets.token_urlsafe(9)


class VoiceRecording(models.Model):
    """Eine Sprachnachricht fuer einen gravierten Blumentopf (Sprachtopf).

    Der Kunde nimmt sie auf der Shopify-Produktseite auf/laedt sie hoch; der
    Beschenkte scannt den auf den Topf gravierten QR-Code -> oeffentliche
    Abspielseite. Aufnahme wird erst nach Admin-Freigabe (`is_approved`)
    oeffentlich hoerbar.
    """
    unique_id = models.CharField(max_length=24, unique=True, db_index=True, default=_new_uid)
    audio_file = models.FileField(upload_to='voice/%Y/%m/')
    duration_sec = models.PositiveIntegerField(default=0)
    file_size = models.PositiveIntegerField(default=0, help_text='Bytes')

    # Verknuepfung mit der Shopify-Bestellung (per Webhook nachgetragen)
    shopify_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    shopify_product_id = models.CharField(max_length=100, blank=True)
    order_name = models.CharField(max_length=60, blank=True, help_text='z.B. #1234')

    # Begleitende Texte (optional)
    gift_message = models.CharField(max_length=300, blank=True, help_text='Gravur-/Begleittext')
    sender_name = models.CharField(max_length=120, blank=True)
    recipient_name = models.CharField(max_length=120, blank=True)

    consent = models.BooleanField(default=False, help_text='Nutzungsrechte bestaetigt')
    is_approved = models.BooleanField(default=False, help_text='Vom Admin freigegeben (oeffentlich hoerbar)')
    is_active = models.BooleanField(default=True, help_text='Deaktiviert = nicht mehr abrufbar')

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    play_count = models.PositiveIntegerField(default=0)
    last_played_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='voice_recordings')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['shopify_order_id']),
        ]

    def __str__(self):
        who = self.order_name or self.shopify_order_id or self.unique_id
        return f'Sprachtopf {who} ({self.created_at:%d.%m.%Y %H:%M})'

    @property
    def is_public(self):
        return self.is_approved and self.is_active
