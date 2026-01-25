# Generated manually for new P-Loom features

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ploom', '0001_initial'),
    ]

    operations = [
        # Add new fields to PLoomProduct
        migrations.AddField(
            model_name='ploomproduct',
            name='weight',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Gewicht'),
        ),
        migrations.AddField(
            model_name='ploomproduct',
            name='weight_unit',
            field=models.CharField(choices=[('kg', 'kg'), ('g', 'g'), ('lb', 'lb'), ('oz', 'oz')], default='kg', max_length=5, verbose_name='Gewichtseinheit'),
        ),
        migrations.AddField(
            model_name='ploomproduct',
            name='track_inventory',
            field=models.BooleanField(default=True, help_text='Wenn aktiviert, wird der Bestand in Shopify verfolgt', verbose_name='Inventar verfolgen'),
        ),
        migrations.AddField(
            model_name='ploomproduct',
            name='inventory_quantity',
            field=models.IntegerField(default=0, verbose_name='Bestand'),
        ),
        migrations.AddField(
            model_name='ploomproduct',
            name='template_suffix',
            field=models.CharField(blank=True, help_text="z.B. 'featured' für product.featured.liquid", max_length=100, verbose_name='Shopify Template'),
        ),
        migrations.AddField(
            model_name='ploomproduct',
            name='sales_channels',
            field=models.JSONField(blank=True, default=list, help_text='Liste der Publication IDs für Shopify Sales Channels', verbose_name='Vertriebskanäle'),
        ),

        # Add new fields to PLoomProductImage
        migrations.AddField(
            model_name='ploomproductimage',
            name='external_url',
            field=models.URLField(blank=True, help_text='URL zu Shopify CDN, Video oder externem Bild', max_length=500, verbose_name='Externe URL'),
        ),
        migrations.AddField(
            model_name='ploomproductimage',
            name='filename',
            field=models.CharField(blank=True, help_text='Benutzerdefinierter Dateiname für Shopify', max_length=255, verbose_name='Dateiname'),
        ),

        # Update SOURCE_CHOICES for PLoomProductImage
        migrations.AlterField(
            model_name='ploomproductimage',
            name='source',
            field=models.CharField(choices=[('imageforge_generation', 'ImageForge Generierung'), ('imageforge_mockup', 'ImageForge Mockup'), ('upload', 'Eigener Upload'), ('external_url', 'Externe URL (Shopify/CDN)')], default='upload', max_length=30, verbose_name='Quelle'),
        ),

        # Create PLoomImageHistory model
        migrations.CreateModel(
            name='PLoomImageHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('upload', 'Upload'), ('imageforge', 'ImageForge'), ('external_url', 'Externe URL')], default='upload', max_length=20)),
                ('url', models.URLField(max_length=500, verbose_name='Bild-URL')),
                ('thumbnail_url', models.URLField(blank=True, max_length=500, verbose_name='Thumbnail-URL')),
                ('filename', models.CharField(blank=True, max_length=255, verbose_name='Dateiname')),
                ('alt_text', models.CharField(blank=True, max_length=255, verbose_name='Alt-Text')),
                ('usage_count', models.PositiveIntegerField(default=1, verbose_name='Verwendungen')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ploom_image_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Bild-Verlauf',
                'verbose_name_plural': 'Bild-Verlauf',
                'ordering': ['-last_used'],
                'unique_together': {('user', 'url')},
            },
        ),
    ]
