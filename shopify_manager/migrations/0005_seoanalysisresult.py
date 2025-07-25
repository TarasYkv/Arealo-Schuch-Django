# Generated by Django 5.2.1 on 2025-07-05 12:00

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_manager', '0004_productseooptimization'),
    ]

    operations = [
        migrations.CreateModel(
            name='SEOAnalysisResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('total_products', models.PositiveIntegerField(default=0)),
                ('products_with_good_seo', models.PositiveIntegerField(default=0)),
                ('products_with_poor_seo', models.PositiveIntegerField(default=0)),
                ('products_with_alt_texts', models.PositiveIntegerField(default=0)),
                ('products_without_alt_texts', models.PositiveIntegerField(default=0)),
                ('products_with_global_seo', models.PositiveIntegerField(default=0)),
                ('products_with_woo_data', models.PositiveIntegerField(default=0)),
                ('products_with_webrex_data', models.PositiveIntegerField(default=0)),
                ('products_with_no_metafields', models.PositiveIntegerField(default=0)),
                ('detailed_results', models.JSONField(blank=True, default=list)),
                ('is_current', models.BooleanField(default=True, help_text='Ist diese Analyse noch aktuell?')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seo_analyses', to='shopify_manager.shopifystore')),
            ],
            options={
                'verbose_name': 'SEO-Analyse-Ergebnis',
                'verbose_name_plural': 'SEO-Analyse-Ergebnisse',
                'ordering': ['-created_at'],
            },
        ),
    ]