# Generated manually for backup settings

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = False

    dependencies = [
        ('superconfig', '0008_add_profile_text_color'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.CharField(choices=[('hourly', 'Stündlich'), ('every6hours', 'Alle 6 Stunden'), ('daily', 'Täglich'), ('weekly', 'Wöchentlich'), ('monthly', 'Monatlich'), ('disabled', 'Deaktiviert')], default='daily', max_length=20, verbose_name='Backup-Häufigkeit')),
                ('retention_days', models.PositiveIntegerField(default=30, help_text='Backups älter als X Tage werden automatisch gelöscht', verbose_name='Aufbewahrungszeit (Tage)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Automatische Backups aktivieren')),
                ('last_backup_at', models.DateTimeField(blank=True, null=True, verbose_name='Letztes Backup')),
                ('last_backup_size_mb', models.FloatField(blank=True, null=True, verbose_name='Letzte Backup-Größe (MB)')),
                ('last_backup_status', models.CharField(blank=True, max_length=100, verbose_name='Letzter Status')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Backup-Einstellungen',
                'verbose_name_plural': 'Backup-Einstellungen',
            },
        ),
    ]
