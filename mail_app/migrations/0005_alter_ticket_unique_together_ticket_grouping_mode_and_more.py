# Generated by Django 5.2.1 on 2025-07-24 22:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mail_app', '0004_email_is_open_ticket_email_ticket_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ticket',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='ticket',
            name='grouping_mode',
            field=models.CharField(choices=[('email', 'Nach Email-Adresse'), ('email_subject', 'Nach Email + Betreff')], default='email', help_text='How emails are grouped in this ticket', max_length=20),
        ),
        migrations.AddField(
            model_name='ticket',
            name='normalized_subject',
            field=models.CharField(blank=True, help_text='Normalized subject for matching', max_length=200),
        ),
        migrations.AlterUniqueTogether(
            name='ticket',
            unique_together={('account', 'sender_email', 'normalized_subject', 'grouping_mode')},
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['normalized_subject'], name='mail_app_ti_normali_b4d4cd_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['grouping_mode'], name='mail_app_ti_groupin_903fae_idx'),
        ),
    ]
