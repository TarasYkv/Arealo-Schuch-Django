# Generated by Django 5.2.1 on 2025-07-11 20:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_customuser_can_make_audio_calls_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLoginHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('login_time', models.DateTimeField(auto_now_add=True, verbose_name='Login Zeit')),
                ('logout_time', models.DateTimeField(blank=True, null=True, verbose_name='Logout Zeit')),
                ('session_duration', models.DurationField(blank=True, null=True, verbose_name='Session Dauer')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP-Adresse')),
                ('user_agent', models.TextField(blank=True, verbose_name='User Agent')),
                ('is_active_session', models.BooleanField(default=True, verbose_name='Aktive Session')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Benutzer Login Historie',
                'verbose_name_plural': 'Benutzer Login Historien',
                'ordering': ['-login_time'],
            },
        ),
    ]
