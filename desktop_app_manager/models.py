"""
Desktop App Manager Models
Versionsverwaltung fuer Desktop-Anwendungen (EXE)
"""

import os
import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.db.models import Sum


def upload_to_app_icon(instance, filename):
    """Upload-Pfad fuer App-Icons"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"desktop_apps/icons/{filename}"


def upload_exe_to(instance, filename):
    """Upload-Pfad fuer EXE-Dateien"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"desktop_apps/exe/{instance.app.app_identifier}/{filename}"


def upload_to_app_screenshot(instance, filename):
    """Upload-Pfad fuer App-Screenshots"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"desktop_apps/screenshots/{instance.app.app_identifier}/{filename}"


class DesktopApp(models.Model):
    """Container fuer eine Desktop-Anwendung"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Basic Info
    name = models.CharField(
        max_length=200,
        verbose_name="App-Name"
    )
    app_identifier = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="App-Identifier",
        help_text="z.B. pdf-marker"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Beschreibung"
    )

    # Icon Upload
    icon = models.ImageField(
        upload_to=upload_to_app_icon,
        null=True,
        blank=True,
        verbose_name="App-Icon"
    )

    # Ownership
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='desktop_apps',
        verbose_name="Ersteller"
    )

    # Visibility
    is_public = models.BooleanField(
        default=False,
        verbose_name="Oeffentlich",
        help_text="App fuer alle sichtbar machen"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Desktop App"
        verbose_name_plural = "Desktop Apps"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['app_identifier']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.name} ({self.app_identifier})"

    @property
    def latest_version(self):
        """Gibt die neueste aktive Version zurueck"""
        return self.versions.filter(is_active=True).order_by('-version_code').first()

    @property
    def total_downloads(self):
        """Gesamtanzahl Downloads ueber alle Versionen"""
        result = self.versions.aggregate(total=Sum('download_count'))
        return result['total'] or 0


class AppVersion(models.Model):
    """Einzelne EXE-Version"""

    # Channel Choices
    CHANNEL_CHOICES = [
        ('alpha', 'Alpha (Interne Tests)'),
        ('beta', 'Beta (Oeffentliche Tests)'),
        ('production', 'Production (Stabile Version)'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Beziehung zur App
    app = models.ForeignKey(
        DesktopApp,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="App"
    )

    # Version Info
    version_name = models.CharField(
        max_length=50,
        verbose_name="Versionsname",
        help_text="z.B. 1.2.0"
    )
    version_code = models.IntegerField(
        verbose_name="Versionscode",
        help_text="Interne Versionsnummer (Integer)"
    )

    # EXE File
    exe_file = models.FileField(
        upload_to=upload_exe_to,
        max_length=500,
        verbose_name="EXE-Datei"
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name="Dateigroesse (Bytes)"
    )

    # File Hash for integrity
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="SHA256 Hash",
        help_text="Wird automatisch beim Upload berechnet"
    )

    # Release Info
    release_notes = models.TextField(
        blank=True,
        verbose_name="Release Notes / Changelog"
    )

    # Release Channel
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='production',
        verbose_name="Release Channel",
        db_index=True
    )

    # System Requirements
    min_windows_version = models.CharField(
        max_length=10,
        default="10",
        verbose_name="Min. Windows Version",
        help_text="z.B. 7, 10, 11"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Nur aktive Versionen werden fuer Updates angeboten"
    )
    is_current_for_channel = models.BooleanField(
        default=False,
        verbose_name="Aktuelle Version fuer Channel",
        help_text="Markiert als aktuelle/empfohlene Version fuer diesen Channel"
    )

    # Statistics
    download_count = models.IntegerField(
        default=0,
        verbose_name="Download-Zaehler"
    )

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App Version"
        verbose_name_plural = "App Versionen"
        ordering = ['-version_code']
        unique_together = [
            ['app', 'version_code'],
        ]
        indexes = [
            models.Index(fields=['app', 'channel', '-version_code']),
            models.Index(fields=['app', 'is_current_for_channel']),
            models.Index(fields=['-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.app.name} v{self.version_name} ({self.channel})"

    def save(self, *args, **kwargs):
        """Auto-populate file_size and file_hash"""
        if self.exe_file:
            if not self.file_size:
                self.file_size = self.exe_file.size
            if not self.file_hash:
                sha256 = hashlib.sha256()
                for chunk in self.exe_file.chunks():
                    sha256.update(chunk)
                self.file_hash = sha256.hexdigest()
                self.exe_file.seek(0)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Loesche EXE-Datei beim Loeschen des Models"""
        if self.exe_file:
            if os.path.isfile(self.exe_file.path):
                os.remove(self.exe_file.path)
        super().delete(*args, **kwargs)

    @property
    def file_size_mb(self):
        """Dateigroesse in MB"""
        return self.file_size / (1024 * 1024)


class DownloadLog(models.Model):
    """Protokolliert EXE-Downloads"""

    app_version = models.ForeignKey(
        AppVersion,
        on_delete=models.CASCADE,
        related_name='download_logs',
        verbose_name="App Version"
    )

    # Tracking Info
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    # System-spezifische Infos
    windows_version = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Windows Version"
    )

    # Optional: User-Referenz falls authentifiziert
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exe_downloads'
    )

    # Download Status
    download_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Download-Log"
        verbose_name_plural = "Download-Logs"
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['-downloaded_at']),
            models.Index(fields=['app_version', '-downloaded_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f"{self.app_version} - {self.downloaded_at.strftime('%Y-%m-%d %H:%M')}"


class AppScreenshot(models.Model):
    """Screenshots fuer Desktop Apps (max. 10 pro App)"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    app = models.ForeignKey(
        DesktopApp,
        on_delete=models.CASCADE,
        related_name='screenshots',
        verbose_name="App"
    )

    image = models.ImageField(
        upload_to=upload_to_app_screenshot,
        verbose_name="Screenshot"
    )

    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Bildunterschrift",
        help_text="Optionale Beschreibung des Screenshots"
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Reihenfolge",
        help_text="Kleinere Zahlen werden zuerst angezeigt"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "App Screenshot"
        verbose_name_plural = "App Screenshots"
        ordering = ['order', 'uploaded_at']
        indexes = [
            models.Index(fields=['app', 'order']),
        ]

    def __str__(self):
        return f"{self.app.name} - Screenshot {self.order + 1}"

    def delete(self, *args, **kwargs):
        """Loesche Bilddatei beim Loeschen des Models"""
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

    @classmethod
    def can_add_more(cls, app):
        """Prueft ob noch Screenshots hinzugefuegt werden koennen (max 10)"""
        return cls.objects.filter(app=app).count() < 10

    @classmethod
    def get_next_order(cls, app):
        """Gibt die naechste Ordnungsnummer zurueck"""
        last = cls.objects.filter(app=app).order_by('-order').first()
        return (last.order + 1) if last else 0
