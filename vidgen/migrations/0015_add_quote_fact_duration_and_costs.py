# Generated migration for quote/fact duration and cost tracking
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vidgen', '0014_add_render_backend'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoproject',
            name='quote_duration',
            field=models.IntegerField(
                default=5,
                verbose_name='Zitat Dauer (Sek)',
                help_text='Wie lange das Zitat angezeigt wird'
            ),
        ),
        migrations.AddField(
            model_name='videoproject',
            name='fact_box_duration',
            field=models.IntegerField(
                default=5,
                verbose_name='Fakten-Box Dauer (Sek)',
                help_text='Wie lange die Fakten-Box angezeigt wird'
            ),
        ),
        migrations.AddField(
            model_name='videoproject',
            name='cost_music',
            field=models.DecimalField(
                max_digits=10, decimal_places=4, default=0,
                verbose_name='Musik-Generierung Kosten ($)'
            ),
        ),
        migrations.AddField(
            model_name='videoproject',
            name='cost_modal',
            field=models.DecimalField(
                max_digits=10, decimal_places=4, default=0,
                verbose_name='Modal Cloud Kosten ($)'
            ),
        ),
    ]
