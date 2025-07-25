# Generated by Django 5.2.1 on 2025-07-13 15:41

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_alter_apppermission_app_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='EditableContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page', models.CharField(choices=[('startseite', 'Startseite'), ('about', 'Über uns'), ('contact', 'Kontakt'), ('services', 'Services'), ('products', 'Produkte')], max_length=50, verbose_name='Seite')),
                ('content_type', models.CharField(choices=[('text', 'Text'), ('image', 'Bild'), ('hero_title', 'Hero Titel'), ('hero_subtitle', 'Hero Untertitel'), ('section_title', 'Bereich Titel'), ('section_text', 'Bereich Text'), ('button_text', 'Button Text'), ('testimonial', 'Kundenstimme')], max_length=50, verbose_name='Inhaltstyp')),
                ('content_key', models.CharField(help_text='Eindeutige Bezeichnung für diesen Inhalt', max_length=100, verbose_name='Inhalt Schlüssel')),
                ('text_content', models.TextField(blank=True, verbose_name='Text Inhalt')),
                ('image_content', models.ImageField(blank=True, null=True, upload_to='editable_content/', verbose_name='Bild Inhalt')),
                ('image_alt_text', models.CharField(blank=True, max_length=255, verbose_name='Bild Alt-Text')),
                ('link_url', models.URLField(blank=True, verbose_name='Link URL')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='editable_contents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Bearbeitbarer Inhalt',
                'verbose_name_plural': 'Bearbeitbare Inhalte',
                'ordering': ['page', 'content_key'],
                'unique_together': {('user', 'page', 'content_key')},
            },
        ),
    ]
