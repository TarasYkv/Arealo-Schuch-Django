# Generated by Django 5.2.1 on 2025-07-29 10:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('email_templates', '0001_initial'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='emailsendlog',
            new_name='email_templ_created_bff515_idx',
            old_name='email_templ_created_4c0a02_idx',
        ),
        migrations.RenameIndex(
            model_name='emailsendlog',
            new_name='email_templ_recipie_83f1b7_idx',
            old_name='email_templ_recipie_83b4ae_idx',
        ),
        migrations.RenameIndex(
            model_name='emailsendlog',
            new_name='email_templ_is_sent_f54e3d_idx',
            old_name='email_templ_is_sent_a25f8a_idx',
        ),
        migrations.AddField(
            model_name='zohomailserverconnection',
            name='zoho_account_id',
            field=models.CharField(blank=True, max_length=50, verbose_name='Zoho Account ID'),
        ),
    ]
