from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('video', '0005_scene_render_stats')]
    operations = [
        migrations.AddField('Scene', 'celery_task_id', models.CharField(max_length=255, null=True, blank=True)),
    ]
