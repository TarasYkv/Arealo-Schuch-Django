from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
import uuid
import os
from datetime import timedelta

User = get_user_model()

class Transfer(models.Model):
    """Haupt-Transfer-Modell, das Dateien zusammenfasst"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_transfers')
    sender_email = models.EmailField(blank=True, help_text="E-Mail des Absenders, falls nicht registriert")

    title = models.CharField(max_length=255, blank=True, help_text="Optionaler Titel für den Transfer")
    message = models.TextField(blank=True, help_text="Optionale Nachricht an Empfänger")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Wann dieser Transfer abläuft")

    download_limit = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Maximale Anzahl erlaubter Downloads. 0 = unbegrenzt"
    )
    total_downloads = models.IntegerField(default=0)

    password_hash = models.CharField(max_length=255, blank=True, help_text="Optionaler Passwortschutz")

    total_size = models.BigIntegerField(default=0, help_text="Gesamtgröße aller Dateien in Bytes")

    is_active = models.BooleanField(default=True)

    # Transfer type
    TRANSFER_TYPE_CHOICES = [
        ('email', 'E-Mail-Transfer'),
        ('link', 'Link-Transfer'),
    ]
    transfer_type = models.CharField(max_length=10, choices=TRANSFER_TYPE_CHOICES, default='link')

    # Analytics
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Transfer {self.id} - {self.title or 'Ohne Titel'}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Standard-Ablauf: 7 Tage für kostenlose Nutzer
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_download_limit_reached(self):
        if self.download_limit == 0:
            return False
        return self.total_downloads >= self.download_limit

    @property
    def can_download(self):
        return self.is_active and not self.is_expired and not self.is_download_limit_reached

    def get_download_url(self):
        from django.urls import reverse
        return reverse('fileshare:download', kwargs={'transfer_id': str(self.id)})


def upload_to_transfer(instance, filename):
    """Generiert Upload-Pfad für Transfer-Dateien"""
    # Store files in transfer-specific folders
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"transfers/{instance.transfer.id}/{filename}"


class TransferFile(models.Model):
    """Einzelne Dateien innerhalb eines Transfers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='files')

    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_to_transfer, max_length=500)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Virus scan status
    SCAN_STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('clean', 'Sauber'),
        ('infected', 'Infiziert'),
        ('error', 'Scan-Fehler'),
    ]
    scan_status = models.CharField(max_length=10, choices=SCAN_STATUS_CHOICES, default='pending')
    scan_message = models.TextField(blank=True)

    class Meta:
        ordering = ['original_filename']

    def __str__(self):
        return f"{self.original_filename} ({self.transfer.id})"

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Lösche die tatsächliche Datei, wenn das Modell gelöscht wird
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)


class TransferRecipient(models.Model):
    """Empfänger für E-Mail-Transfers"""
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='recipients')
    email = models.EmailField()

    # Tracking
    notified_at = models.DateTimeField(null=True, blank=True)
    first_download_at = models.DateTimeField(null=True, blank=True)
    download_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['transfer', 'email']

    def __str__(self):
        return f"{self.email} - {self.transfer.id}"


class DownloadLog(models.Model):
    """Protokolliert jeden Download für Analysen"""
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='download_logs')
    file = models.ForeignKey(TransferFile, on_delete=models.CASCADE, null=True, blank=True)

    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    # Falls von einem Empfänger heruntergeladen
    recipient = models.ForeignKey(TransferRecipient, on_delete=models.SET_NULL, null=True, blank=True)

    # Download info
    bytes_downloaded = models.BigIntegerField(default=0)
    download_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['-downloaded_at']),
        ]


class TransferStatistics(models.Model):
    """Tägliche Statistiken für Transfers"""
    date = models.DateField(unique=True)

    total_transfers = models.IntegerField(default=0)
    total_files = models.IntegerField(default=0)
    total_size = models.BigIntegerField(default=0)
    total_downloads = models.IntegerField(default=0)

    unique_senders = models.IntegerField(default=0)
    unique_recipients = models.IntegerField(default=0)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Transfer-Statistiken"
