# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loommarket', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='impressum_instagram',
            field=models.TextField(blank=True, null=True, verbose_name='Impressum (Instagram)'),
        ),
        migrations.AddField(
            model_name='business',
            name='impressum_website',
            field=models.TextField(blank=True, null=True, verbose_name='Impressum (Website)'),
        ),
        migrations.AddField(
            model_name='business',
            name='impressum_website_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='Impressum URL'),
        ),
    ]
