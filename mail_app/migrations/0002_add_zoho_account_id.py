# Generated manually for Zoho Account ID

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mail_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailaccount',
            name='zoho_account_id',
            field=models.CharField(max_length=50, blank=True, verbose_name='Zoho Account ID'),
        ),
    ]