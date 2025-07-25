# Generated by Django 5.2.1 on 2025-07-24 11:13

import django.db.models.deletion
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('zoho_message_id', models.CharField(max_length=255, unique=True)),
                ('message_id', models.CharField(blank=True, max_length=255)),
                ('thread_id', models.CharField(blank=True, max_length=255)),
                ('subject', models.CharField(blank=True, max_length=998)),
                ('from_email', models.EmailField(max_length=254)),
                ('from_name', models.CharField(blank=True, max_length=255)),
                ('to_emails', models.JSONField(default=list)),
                ('cc_emails', models.JSONField(default=list)),
                ('bcc_emails', models.JSONField(default=list)),
                ('reply_to', models.EmailField(blank=True, max_length=254)),
                ('body_text', models.TextField(blank=True)),
                ('body_html', models.TextField(blank=True)),
                ('message_type', models.CharField(choices=[('received', 'Received'), ('sent', 'Sent'), ('draft', 'Draft')], default='received', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')], default='normal', max_length=10)),
                ('is_read', models.BooleanField(default=False)),
                ('is_starred', models.BooleanField(default=False)),
                ('is_important', models.BooleanField(default=False)),
                ('is_spam', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField()),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Email',
                'verbose_name_plural': 'Emails',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(max_length=100)),
                ('file_size', models.PositiveIntegerField()),
                ('zoho_attachment_id', models.CharField(blank=True, max_length=255)),
                ('file_data', models.BinaryField(blank=True, null=True)),
                ('is_cached', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('email', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='mail_app.email')),
            ],
            options={
                'verbose_name': 'Attachment',
                'verbose_name_plural': 'Attachments',
                'ordering': ['filename'],
            },
        ),
        migrations.CreateModel(
            name='EmailAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_address', models.EmailField(max_length=254, unique=True)),
                ('display_name', models.CharField(blank=True, max_length=255)),
                ('access_token', encrypted_model_fields.fields.EncryptedTextField(blank=True, null=True)),
                ('refresh_token', encrypted_model_fields.fields.EncryptedTextField(blank=True, null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('sync_enabled', models.BooleanField(default=True)),
                ('last_sync', models.DateTimeField(blank=True, null=True)),
                ('signature', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Email Account',
                'verbose_name_plural': 'Email Accounts',
                'ordering': ['-is_default', 'email_address'],
            },
        ),
        migrations.AddField(
            model_name='email',
            name='account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emails', to='mail_app.emailaccount'),
        ),
        migrations.CreateModel(
            name='EmailDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(blank=True, max_length=998)),
                ('to_emails', models.JSONField(default=list)),
                ('cc_emails', models.JSONField(default=list)),
                ('bcc_emails', models.JSONField(default=list)),
                ('body_text', models.TextField(blank=True)),
                ('body_html', models.TextField(blank=True)),
                ('is_forward', models.BooleanField(default=False)),
                ('is_auto_saved', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drafts', to='mail_app.emailaccount')),
                ('in_reply_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mail_app.email')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Email Draft',
                'verbose_name_plural': 'Email Drafts',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='Folder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('folder_type', models.CharField(choices=[('inbox', 'Inbox'), ('sent', 'Sent'), ('drafts', 'Drafts'), ('trash', 'Trash'), ('spam', 'Spam'), ('custom', 'Custom')], default='custom', max_length=20)),
                ('zoho_folder_id', models.CharField(blank=True, max_length=255)),
                ('unread_count', models.IntegerField(default=0)),
                ('total_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='folders', to='mail_app.emailaccount')),
            ],
            options={
                'verbose_name': 'Folder',
                'verbose_name_plural': 'Folders',
                'ordering': ['account', 'folder_type', 'name'],
                'unique_together': {('account', 'zoho_folder_id')},
            },
        ),
        migrations.AddField(
            model_name='email',
            name='folder',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emails', to='mail_app.folder'),
        ),
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sync_type', models.CharField(choices=[('full', 'Full Sync'), ('incremental', 'Incremental Sync'), ('manual', 'Manual Sync')], default='incremental', max_length=20)),
                ('status', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('failed', 'Failed'), ('partial', 'Partial')], default='started', max_length=20)),
                ('emails_fetched', models.IntegerField(default=0)),
                ('emails_created', models.IntegerField(default=0)),
                ('emails_updated', models.IntegerField(default=0)),
                ('errors_count', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('sync_duration', models.DurationField(blank=True, null=True)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_logs', to='mail_app.emailaccount')),
            ],
            options={
                'verbose_name': 'Sync Log',
                'verbose_name_plural': 'Sync Logs',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='email',
            index=models.Index(fields=['account', 'folder', '-sent_at'], name='mail_app_em_account_94ac1a_idx'),
        ),
        migrations.AddIndex(
            model_name='email',
            index=models.Index(fields=['zoho_message_id'], name='mail_app_em_zoho_me_6f39e3_idx'),
        ),
        migrations.AddIndex(
            model_name='email',
            index=models.Index(fields=['is_read', 'is_starred'], name='mail_app_em_is_read_0ea6ad_idx'),
        ),
        migrations.AddIndex(
            model_name='email',
            index=models.Index(fields=['thread_id'], name='mail_app_em_thread__cebd21_idx'),
        ),
    ]
