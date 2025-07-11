# Manual migration to fix unit field NULL constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_sucher', '0002_alter_tenderposition_unit'),
    ]

    operations = [
        # First, fill any NULL values with empty string
        migrations.RunSQL(
            "UPDATE pdf_sucher_tenderposition SET unit = '' WHERE unit IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Then alter the field to allow blank and have default
        migrations.AlterField(
            model_name='tenderposition',
            name='unit',
            field=models.CharField(blank=True, default='', help_text='Einheit (Stk, m², kg, etc.)', max_length=50, null=True),
        ),
    ]