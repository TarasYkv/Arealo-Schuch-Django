# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('learnloom', '0004_add_text_explanation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReadingListItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=500, verbose_name='Titel/Quelle')),
                ('url', models.URLField(blank=True, verbose_name='URL/Link')),
                ('notes', models.TextField(blank=True, verbose_name='Notizen')),
                ('status', models.CharField(choices=[('todo', 'ToDo'), ('done', 'Erledigt')], default='todo', max_length=20, verbose_name='Status')),
                ('priority', models.PositiveIntegerField(default=0, verbose_name='Priorität')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Erledigt am')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reading_list', to=settings.AUTH_USER_MODEL, verbose_name='Benutzer')),
            ],
            options={
                'verbose_name': 'Leselisten-Eintrag',
                'verbose_name_plural': 'Leselisten-Einträge',
                'ordering': ['status', 'priority', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='readinglistitem',
            index=models.Index(fields=['user', 'status'], name='learnloom_r_user_id_5a7c7d_idx'),
        ),
    ]
