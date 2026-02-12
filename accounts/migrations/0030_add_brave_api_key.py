# Generated manually for Brave Search API Key

from django.db import migrations
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_add_bing_api_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='brave_api_key',
            field=encrypted_model_fields.fields.EncryptedCharField(blank=True, max_length=255, null=True, verbose_name='Brave Search API Key'),
        ),
    ]
