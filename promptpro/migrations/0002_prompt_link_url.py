from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('promptpro', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='prompt',
            name='link_url',
            field=models.URLField(blank=True, help_text='Optionaler Link, der mit diesem Prompt verknüpft ist'),
        ),
    ]

