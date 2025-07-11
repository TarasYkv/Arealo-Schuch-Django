# Generated migration for todos app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TodoList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Titel')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
                ('is_public', models.BooleanField(default=False, verbose_name='Öffentlich sichtbar')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_todo_lists', to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
                ('shared_with', models.ManyToManyField(blank=True, related_name='shared_todo_lists', to=settings.AUTH_USER_MODEL, verbose_name='Geteilt mit')),
            ],
            options={
                'verbose_name': 'ToDo-Liste',
                'verbose_name_plural': 'ToDo-Listen',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='Todo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Titel')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('status', models.CharField(choices=[('pending', 'Steht aus'), ('in_progress', 'In Bearbeitung'), ('completed', 'Erledigt')], default='pending', max_length=20, verbose_name='Status')),
                ('priority', models.CharField(choices=[('low', 'Niedrig'), ('medium', 'Mittel'), ('high', 'Hoch'), ('urgent', 'Dringend')], default='medium', max_length=20, verbose_name='Priorität')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
                ('due_date', models.DateTimeField(blank=True, null=True, verbose_name='Fälligkeitsdatum')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Erledigt am')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_todos', to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
                ('todo_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='todos', to='todos.todolist', verbose_name='Liste')),
            ],
            options={
                'verbose_name': 'ToDo',
                'verbose_name_plural': 'ToDos',
                'ordering': ['-priority', 'due_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TodoAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True, verbose_name='Zugeordnet am')),
                ('notes', models.TextField(blank=True, verbose_name='Notizen')),
                ('user_status', models.CharField(choices=[('pending', 'Steht aus'), ('in_progress', 'In Bearbeitung'), ('completed', 'Erledigt')], default='pending', max_length=20, verbose_name='Benutzerstatus')),
                ('assigned_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assigned_todos_by', to=settings.AUTH_USER_MODEL)),
                ('todo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='todos.todo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='todo_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ToDo-Zuordnung',
                'verbose_name_plural': 'ToDo-Zuordnungen',
            },
        ),
        migrations.CreateModel(
            name='TodoComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='Kommentar')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')),
                ('todo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='todos.todo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='todo_comments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ToDo-Kommentar',
                'verbose_name_plural': 'ToDo-Kommentare',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='TodoActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(choices=[('created', 'Erstellt'), ('updated', 'Aktualisiert'), ('status_changed', 'Status geändert'), ('assigned', 'Zugeordnet'), ('unassigned', 'Zuordnung entfernt'), ('commented', 'Kommentiert'), ('due_date_set', 'Fälligkeitsdatum gesetzt'), ('due_date_changed', 'Fälligkeitsdatum geändert')], max_length=20)),
                ('description', models.TextField(verbose_name='Beschreibung')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('todo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='todos.todo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='todo_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ToDo-Aktivität',
                'verbose_name_plural': 'ToDo-Aktivitäten',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='todo',
            name='assigned_to',
            field=models.ManyToManyField(blank=True, related_name='assigned_todos', through='todos.TodoAssignment', through_fields=('todo', 'user'), to=settings.AUTH_USER_MODEL, verbose_name='Zugeordnet an'),
        ),
        migrations.AlterUniqueTogether(
            name='todoassignment',
            unique_together={('todo', 'user')},
        ),
    ]