# Generated for CapSolver + 2Captcha API-Key-Felder

import encrypted_model_fields.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0040_customuser_google_account_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='capsolver_api_key',
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True, null=True, verbose_name='CapSolver API Key'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='twocaptcha_api_key',
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True, null=True, verbose_name='2Captcha API Key'),
        ),
    ]
