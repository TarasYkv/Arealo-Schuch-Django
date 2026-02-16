# Generated manually for subtitle support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0007_add_manual_storage_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='subtitle_file',
            field=models.FileField(blank=True, help_text='WebVTT Untertitel-Datei', null=True, upload_to='videos/subtitles/'),
        ),
        migrations.AddField(
            model_name='video',
            name='subtitle_status',
            field=models.CharField(choices=[('none', 'Keine'), ('pending', 'Wird erstellt...'), ('ready', 'Verfügbar'), ('failed', 'Fehlgeschlagen')], default='none', max_length=20),
        ),
        migrations.AddField(
            model_name='video',
            name='subtitle_language',
            field=models.CharField(blank=True, default='de', max_length=10),
        ),
        migrations.AddField(
            model_name='video',
            name='transcript',
            field=models.TextField(blank=True, help_text='Vollständiges Transkript'),
        ),
    ]
