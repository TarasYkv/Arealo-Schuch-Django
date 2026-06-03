# Generated for pipeline-mode (manual)
# Erweitert MODE_CHOICES um ('pipeline', 'Pipeline (externe Quellen)').

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('research', '0005_researchquery_is_public_researchquery_share_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='researchquery',
            name='mode',
            field=models.CharField(
                choices=[
                    ('rag', 'RAG (aus eigener Bibliothek)'),
                    ('council', 'Council (mehrere Modelle)'),
                    ('council_edited', 'Council + Redakteur (Primär-Modell strukturiert)'),
                    ('hybrid', 'Hybrid (RAG + Council)'),
                    ('pipeline', 'Pipeline (externe Quellen)'),
                ],
                default='rag',
                max_length=16,
            ),
        ),
    ]
