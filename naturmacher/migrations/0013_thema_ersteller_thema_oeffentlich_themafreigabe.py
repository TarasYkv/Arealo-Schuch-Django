# Generated by Django 5.2.1 on 2025-07-07 14:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('naturmacher', '0012_alter_apibalance_provider_alter_apiusagelog_provider_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='thema',
            name='ersteller',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='erstellte_themen', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='thema',
            name='oeffentlich',
            field=models.BooleanField(default=False, help_text='Thema für alle Benutzer sichtbar'),
        ),
        migrations.CreateModel(
            name='ThemaFreigabe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('freigegeben_am', models.DateTimeField(auto_now_add=True)),
                ('benutzer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='thema_freigaben', to=settings.AUTH_USER_MODEL)),
                ('freigegeben_von', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gegebene_freigaben', to=settings.AUTH_USER_MODEL)),
                ('thema', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='freigaben', to='naturmacher.thema')),
            ],
            options={
                'verbose_name': 'Thema-Freigabe',
                'verbose_name_plural': 'Thema-Freigaben',
                'unique_together': {('thema', 'benutzer')},
            },
        ),
    ]
