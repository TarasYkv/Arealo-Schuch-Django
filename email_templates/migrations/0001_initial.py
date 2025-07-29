# Generated manually for email_templates app

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplateCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Kategoriename')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Slug')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('icon', models.CharField(blank=True, max_length=50, verbose_name='Icon CSS-Klasse')),
                ('order', models.IntegerField(default=0, verbose_name='Reihenfolge')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'E-Mail-Vorlage Kategorie',
                'verbose_name_plural': 'E-Mail-Vorlage Kategorien',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ZohoMailServerConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Verbindungsname')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('client_id', encrypted_model_fields.fields.EncryptedCharField(max_length=255, verbose_name='Zoho Client ID')),
                ('client_secret', encrypted_model_fields.fields.EncryptedCharField(max_length=255, verbose_name='Zoho Client Secret')),
                ('redirect_uri', models.URLField(verbose_name='Redirect URI')),
                ('region', models.CharField(choices=[('US', 'US'), ('EU', 'EU'), ('IN', 'India'), ('AU', 'Australia'), ('CN', 'China'), ('JP', 'Japan')], default='EU', max_length=5, verbose_name='Zoho Region')),
                ('access_token', encrypted_model_fields.fields.EncryptedTextField(blank=True, null=True)),
                ('refresh_token', encrypted_model_fields.fields.EncryptedTextField(blank=True, null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('email_address', models.EmailField(max_length=254, verbose_name='E-Mail-Adresse')),
                ('display_name', models.CharField(blank=True, max_length=255, verbose_name='Anzeigename')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('is_configured', models.BooleanField(default=False, verbose_name='Konfiguriert')),
                ('last_test_success', models.DateTimeField(blank=True, null=True, verbose_name='Letzter erfolgreicher Test')),
                ('last_error', models.TextField(blank=True, verbose_name='Letzter Fehler')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_mail_connections', to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
            ],
            options={
                'verbose_name': 'Zoho Mail Server Verbindung',
                'verbose_name_plural': 'Zoho Mail Server Verbindungen',
                'ordering': ['-is_active', 'name'],
                'permissions': [('can_test_connection', 'Kann Verbindung testen')],
            },
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Vorlagenname')),
                ('slug', models.SlugField(max_length=200, unique=True, verbose_name='Slug')),
                ('template_type', models.CharField(choices=[('order_confirmation', 'Bestellbestätigung'), ('order_shipped', 'Versandbestätigung'), ('order_delivered', 'Lieferbestätigung'), ('order_cancelled', 'Stornierungsbestätigung'), ('invoice', 'Rechnung'), ('reminder', 'Erinnerung'), ('newsletter', 'Newsletter'), ('welcome', 'Willkommens-E-Mail'), ('password_reset', 'Passwort zurücksetzen'), ('account_activation', 'Account-Aktivierung'), ('custom', 'Benutzerdefiniert')], default='custom', max_length=50, verbose_name='Vorlagentyp')),
                ('subject', models.CharField(help_text='Unterstützt Variablen wie {{customer_name}}, {{order_number}}', max_length=255, verbose_name='Betreff')),
                ('html_content', models.TextField(verbose_name='HTML-Inhalt')),
                ('text_content', models.TextField(blank=True, help_text='Optionaler Nur-Text-Inhalt für E-Mail-Clients ohne HTML-Unterstützung', verbose_name='Text-Inhalt')),
                ('use_base_template', models.BooleanField(default=True, help_text='Verwendet das Standard-E-Mail-Layout mit Header und Footer', verbose_name='Basis-Template verwenden')),
                ('custom_css', models.TextField(blank=True, verbose_name='Benutzerdefiniertes CSS')),
                ('available_variables', models.JSONField(blank=True, default=dict, help_text='JSON-Dokumentation der verfügbaren Template-Variablen', verbose_name='Verfügbare Variablen')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('is_default', models.BooleanField(default=False, help_text='Standard-Vorlage für diesen Vorlagentyp', verbose_name='Standard-Vorlage')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('times_used', models.PositiveIntegerField(default=0, verbose_name='Verwendungen')),
                ('last_used_at', models.DateTimeField(blank=True, null=True, verbose_name='Zuletzt verwendet')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='templates', to='email_templates.emailtemplatecategory', verbose_name='Kategorie')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_email_templates', to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
                ('last_modified_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modified_email_templates', to=settings.AUTH_USER_MODEL, verbose_name='Zuletzt geändert von')),
            ],
            options={
                'verbose_name': 'E-Mail-Vorlage',
                'verbose_name_plural': 'E-Mail-Vorlagen',
                'ordering': ['-is_default', 'category__order', 'name'],
                'permissions': [('can_preview_template', 'Kann Vorlagen-Vorschau anzeigen'), ('can_send_test_email', 'Kann Test-E-Mail senden')],
            },
        ),
        migrations.CreateModel(
            name='EmailSendLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(max_length=254, verbose_name='Empfänger E-Mail')),
                ('recipient_name', models.CharField(blank=True, max_length=255, verbose_name='Empfänger Name')),
                ('subject', models.CharField(max_length=255, verbose_name='Betreff')),
                ('is_sent', models.BooleanField(default=False, verbose_name='Gesendet')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Gesendet am')),
                ('error_message', models.TextField(blank=True, verbose_name='Fehlermeldung')),
                ('context_data', models.JSONField(blank=True, default=dict, help_text='Variablen die beim Rendern verwendet wurden', verbose_name='Kontext-Daten')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('connection', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='email_templates.zohomailserverconnection', verbose_name='Verwendete Verbindung')),
                ('sent_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Gesendet von')),
                ('template', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='send_logs', to='email_templates.emailtemplate', verbose_name='Verwendete Vorlage')),
            ],
            options={
                'verbose_name': 'E-Mail Versandprotokoll',
                'verbose_name_plural': 'E-Mail Versandprotokolle',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailTemplateVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField(verbose_name='Versionsnummer')),
                ('subject', models.CharField(max_length=255, verbose_name='Betreff')),
                ('html_content', models.TextField(verbose_name='HTML-Inhalt')),
                ('text_content', models.TextField(blank=True, verbose_name='Text-Inhalt')),
                ('custom_css', models.TextField(blank=True, verbose_name='Benutzerdefiniertes CSS')),
                ('change_description', models.TextField(blank=True, verbose_name='Änderungsbeschreibung')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Erstellt von')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='email_templates.emailtemplate', verbose_name='Vorlage')),
            ],
            options={
                'verbose_name': 'E-Mail-Vorlagen Version',
                'verbose_name_plural': 'E-Mail-Vorlagen Versionen',
                'ordering': ['template', '-version_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='emailtemplate',
            constraint=models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('template_type', 'is_default'), name='unique_default_per_type'),
        ),
        migrations.AddIndex(
            model_name='emailsendlog',
            index=models.Index(fields=['-created_at'], name='email_templ_created_4c0a02_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendlog',
            index=models.Index(fields=['recipient_email'], name='email_templ_recipie_83b4ae_idx'),
        ),
        migrations.AddIndex(
            model_name='emailsendlog',
            index=models.Index(fields=['is_sent', '-created_at'], name='email_templ_is_sent_a25f8a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='emailtemplateversion',
            unique_together={('template', 'version_number')},
        ),
    ]