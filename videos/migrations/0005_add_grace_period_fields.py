# Generated by Django 5.2.1 on 2025-07-23 08:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0004_add_thumbnail_and_duration'),
    ]

    operations = [
        migrations.AddField(
            model_name='userstorage',
            name='grace_period_end',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userstorage',
            name='grace_period_start',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userstorage',
            name='is_in_grace_period',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userstorage',
            name='last_overage_notification',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userstorage',
            name='overage_restriction_level',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userstorage',
            name='storage_overage_notified',
            field=models.BooleanField(default=False),
        ),
    ]
