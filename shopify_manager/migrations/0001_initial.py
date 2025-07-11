# Generated by Django 5.2.1 on 2025-07-04 23:24

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ShopifyProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shopify_id', models.CharField(help_text='Shopify Product ID', max_length=50, unique=True)),
                ('title', models.CharField(help_text='Produkttitel', max_length=255)),
                ('handle', models.CharField(help_text='URL Handle', max_length=255)),
                ('body_html', models.TextField(blank=True, help_text='Produktbeschreibung (HTML)')),
                ('vendor', models.CharField(blank=True, help_text='Hersteller', max_length=255)),
                ('product_type', models.CharField(blank=True, help_text='Produkttyp', max_length=255)),
                ('status', models.CharField(choices=[('active', 'Aktiv'), ('archived', 'Archiviert'), ('draft', 'Entwurf')], default='active', max_length=20)),
                ('seo_title', models.CharField(blank=True, help_text='SEO Titel (max. 70 Zeichen)', max_length=70)),
                ('seo_description', models.TextField(blank=True, help_text='SEO Beschreibung (max. 160 Zeichen)', max_length=160)),
                ('featured_image_url', models.URLField(blank=True, help_text='Haupt-Produktbild URL')),
                ('featured_image_alt', models.CharField(blank=True, help_text='Alt-Text für Hauptbild', max_length=255)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('compare_at_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('tags', models.TextField(blank=True, help_text='Tags (kommagetrennt)')),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('needs_sync', models.BooleanField(default=False, help_text='Wurde lokal geändert und muss synchronisiert werden')),
                ('sync_error', models.TextField(blank=True, help_text='Letzter Sync-Fehler')),
                ('shopify_created_at', models.DateTimeField(blank=True, null=True)),
                ('shopify_updated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_shopify_data', models.JSONField(blank=True, default=dict, help_text='Komplette Shopify Produktdaten')),
            ],
            options={
                'verbose_name': 'Shopify Produkt',
                'verbose_name_plural': 'Shopify Produkte',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ShopifyProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shopify_image_id', models.CharField(help_text='Shopify Image ID', max_length=50)),
                ('image_url', models.URLField(help_text='Bild URL')),
                ('alt_text', models.CharField(blank=True, help_text='Alt-Text', max_length=255)),
                ('position', models.PositiveIntegerField(default=1, help_text='Reihenfolge der Bilder')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='shopify_manager.shopifyproduct')),
            ],
            options={
                'verbose_name': 'Produktbild',
                'verbose_name_plural': 'Produktbilder',
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='ShopifyStore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name des Shops', max_length=200)),
                ('shop_domain', models.CharField(help_text='mystore.myshopify.com', max_length=200)),
                ('access_token', models.CharField(help_text='Shopify Access Token', max_length=255)),
                ('api_key', models.CharField(blank=True, help_text='Shopify API Key', max_length=255)),
                ('api_secret', models.CharField(blank=True, help_text='Shopify API Secret', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shopify_stores', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Shopify Store',
                'verbose_name_plural': 'Shopify Stores',
                'unique_together': {('shop_domain', 'user')},
            },
        ),
        migrations.AddField(
            model_name='shopifyproduct',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='shopify_manager.shopifystore'),
        ),
        migrations.CreateModel(
            name='ShopifySyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('import', 'Import von Shopify'), ('export', 'Export zu Shopify'), ('update', 'Update zu Shopify'), ('sync_all', 'Alle Produkte synchronisieren')], max_length=20)),
                ('status', models.CharField(choices=[('success', 'Erfolgreich'), ('error', 'Fehler'), ('partial', 'Teilweise erfolgreich')], max_length=20)),
                ('products_processed', models.PositiveIntegerField(default=0)),
                ('products_success', models.PositiveIntegerField(default=0)),
                ('products_failed', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('duration_seconds', models.PositiveIntegerField(blank=True, null=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_logs', to='shopify_manager.shopifystore')),
            ],
            options={
                'verbose_name': 'Sync Log',
                'verbose_name_plural': 'Sync Logs',
                'ordering': ['-started_at'],
            },
        ),
    ]
