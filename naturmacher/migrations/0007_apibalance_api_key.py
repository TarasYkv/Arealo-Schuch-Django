# Generated manually for API key storage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('naturmacher', '0006_apibalance_apiusagelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='apibalance',
            name='api_key',
            field=models.CharField(blank=True, help_text='API-Schlüssel (verschlüsselt gespeichert)', max_length=255),
        ),
    ]