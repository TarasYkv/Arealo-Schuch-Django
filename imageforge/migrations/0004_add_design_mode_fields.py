# Generated manually for Design Mode feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('imageforge', '0003_add_motif_to_mockup'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagegeneration',
            name='design_type',
            field=models.CharField(
                blank=True,
                choices=[('illustration', 'Illustration/Grafik'), ('pattern', 'Muster/Textur')],
                default='',
                max_length=20,
                verbose_name='Design-Typ'
            ),
        ),
        migrations.AddField(
            model_name='imagegeneration',
            name='design_color_style',
            field=models.CharField(
                blank=True,
                choices=[
                    ('colorful', 'Farbig'),
                    ('grayscale', 'Grautöne'),
                    ('bw', 'Schwarz/Weiß'),
                    ('monochrome', 'Monochrom'),
                    ('pastel', 'Pastell'),
                    ('vibrant', 'Kräftig/Lebhaft'),
                    ('neon', 'Neon'),
                    ('earth', 'Erdtöne'),
                ],
                default='',
                max_length=20,
                verbose_name='Farbstil'
            ),
        ),
        migrations.AddField(
            model_name='imagegeneration',
            name='design_tonality',
            field=models.CharField(
                blank=True,
                choices=[
                    ('humorous', 'Humorvoll'),
                    ('elegant', 'Elegant'),
                    ('playful', 'Verspielt'),
                    ('minimalist', 'Minimalistisch'),
                    ('vintage', 'Vintage/Retro'),
                    ('modern', 'Modern'),
                    ('professional', 'Professionell'),
                    ('artistic', 'Künstlerisch'),
                    ('cute', 'Niedlich/Kawaii'),
                ],
                default='',
                max_length=20,
                verbose_name='Tonalität'
            ),
        ),
        migrations.AddField(
            model_name='imagegeneration',
            name='design_text_enabled',
            field=models.BooleanField(default=False, verbose_name='Text auf Design'),
        ),
        migrations.AddField(
            model_name='imagegeneration',
            name='design_text_content',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='Design-Text'),
        ),
        migrations.AddField(
            model_name='imagegeneration',
            name='design_reference_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='imageforge/design_refs/%Y/%m/',
                verbose_name='Stil-Referenzbild'
            ),
        ),
    ]
