# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0033_add_user_app_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='editablecontent',
            name='section',
            field=models.CharField(blank=True, help_text='Kategorisierung des Inhalts (z.B. hero, features, pricing)', max_length=50, verbose_name='Bereich'),
        ),
    ]