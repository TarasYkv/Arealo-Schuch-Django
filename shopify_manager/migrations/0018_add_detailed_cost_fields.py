# Generated manually for enhanced cost tracking

from django.db import migrations, models
import decimal


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_manager', '0017_salesdata_actual_shipping_cost_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesdata',
            name='tax_amount',
            field=models.DecimalField(
                blank=True, 
                decimal_places=2, 
                default=decimal.Decimal('0.00'), 
                help_text='Steuerbetrag aus Shopify tax_lines',
                max_digits=10, 
                verbose_name='Steuerbetrag'
            ),
        ),
    ]