# Generated by Django 5.2.1 on 2025-07-22 12:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_seosettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='dark_mode',
            field=models.BooleanField(default=False, verbose_name='Dunkles Design aktivieren'),
        ),
    ]
