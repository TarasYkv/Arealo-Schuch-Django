# Generated manually for karaoke subtitle support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0008_add_subtitle_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='subtitle_words_json',
            field=models.FileField(blank=True, help_text='JSON mit Wort-Zeitstempeln für Karaoke-Modus', null=True, upload_to='videos/subtitles/'),
        ),
    ]
