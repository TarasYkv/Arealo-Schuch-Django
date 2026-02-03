"""
Android APK Manager Models
Versionsverwaltung für Android Apps
"""

import os
import uuid
from django.db import models
from django.conf import settings
from django.db.models import Sum


def upload_to_app_icon(instance, filename):
    """Upload-Pfad für App-Icons"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"android_apps/icons/{filename}"


def upload_to_app_screenshot(instance, filename):
    """Upload-Pfad für App-Screenshots"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"android_apps/screenshots/{instance.app.package_name}/{filename}"


def upload_apk_to(instance, filename):
    """Upload-Pfad für APK-Dateien"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"android_apps/apk/{instance.app.package_name}/{filename}"


class AndroidApp(models.Model):
    """Container für eine Android-Anwendung"""

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
    package_name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Package-Name",
        help_text="z.B. com.workloom.app"
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
        related_name='android_apps',
        verbose_name="Ersteller"
    )

    # Visibility
    is_public = models.BooleanField(
        default=False,
        verbose_name="Öffentlich",
        help_text="App für alle sichtbar machen"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Android App"
        verbose_name_plural = "Android Apps"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['package_name']),
            models.Index(fields=['is_public']),
        ]

    def __str__(self):
        return f"{self.name} ({self.package_name})"

    @property
    def latest_version(self):
        """Gibt die neueste aktive Version zurück"""
        return self.versions.filter(is_active=True).order_by('-version_code').first()

    @property
    def total_downloads(self):
        """Gesamtanzahl Downloads über alle Versionen"""
        result = self.versions.aggregate(total=Sum('download_count'))
        return result['total'] or 0


class AppVersion(models.Model):
    """Einzelne APK-Version"""

    # Channel Choices
    CHANNEL_CHOICES = [
        ('alpha', 'Alpha (Interne Tests)'),
        ('beta', 'Beta (Öffentliche Tests)'),
        ('production', 'Production (Stabile Version)'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # Beziehung zur App
    app = models.ForeignKey(
        AndroidApp,
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

    # APK File
    apk_file = models.FileField(
        upload_to=upload_apk_to,
        max_length=500,
        verbose_name="APK-Datei"
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name="Dateigröße (Bytes)"
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

    # Android Requirements
    min_android_version = models.CharField(
        max_length=10,
        default="5.0",
        verbose_name="Min. Android Version",
        help_text="z.B. 5.0, 8.0, 10.0"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Nur aktive Versionen werden für Updates angeboten"
    )
    is_current_for_channel = models.BooleanField(
        default=False,
        verbose_name="Aktuelle Version für Channel",
        help_text="Markiert als aktuelle/empfohlene Version für diesen Channel"
    )

    # Statistics
    download_count = models.IntegerField(
        default=0,
        verbose_name="Download-Zähler"
    )

    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App Version"
        verbose_name_plural = "App Versionen"
        ordering = ['-version_code']
        unique_together = [
            ['app', 'version_code'],  # Jeder Version-Code nur einmal pro App
        ]
        indexes = [
            models.Index(fields=['app', 'channel', '-version_code']),
            models.Index(fields=['app', 'is_current_for_channel']),
            models.Index(fields=['-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.app.name} v{self.version_name} ({self.channel})"

    def save(self, *args, **kwargs):
        """Auto-populate file_size"""
        if self.apk_file and not self.file_size:
            self.file_size = self.apk_file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Lösche APK-Datei beim Löschen des Models"""
        if self.apk_file:
            if os.path.isfile(self.apk_file.path):
                os.remove(self.apk_file.path)
        super().delete(*args, **kwargs)

    @property
    def file_size_mb(self):
        """Dateigröße in MB"""
        return self.file_size / (1024 * 1024)


class DownloadLog(models.Model):
    """Protokolliert APK-Downloads"""

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

    # Android-spezifische Infos
    android_version = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Android Version"
    )
    device_model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Gerätemodell"
    )

    # Optional: User-Referenz falls authentifiziert
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='apk_downloads'
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
    """Screenshots für Android Apps (max. 10 pro App)"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    app = models.ForeignKey(
        AndroidApp,
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
        """Lösche Bilddatei beim Löschen des Models"""
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

    @classmethod
    def can_add_more(cls, app):
        """Prüft ob noch Screenshots hinzugefügt werden können (max 10)"""
        return cls.objects.filter(app=app).count() < 10

    @classmethod
    def get_next_order(cls, app):
        """Gibt die nächste Ordnungsnummer zurück"""
        last = cls.objects.filter(app=app).order_by('-order').first()
        return (last.order + 1) if last else 0
