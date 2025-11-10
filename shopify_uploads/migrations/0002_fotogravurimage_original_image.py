# Generated manually on 2025-11-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_uploads', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='fotogravurimage',
            name='original_image',
            field=models.ImageField(blank=True, null=True, upload_to='fotogravur/originals/%Y/%m/'),
        ),
    ]
