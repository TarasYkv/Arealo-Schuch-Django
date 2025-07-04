# Generated manually for API balance tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('naturmacher', '0005_usertrainingnotizen_input_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('openai', 'OpenAI (ChatGPT)'), ('anthropic', 'Anthropic (Claude)'), ('google', 'Google (Gemini)')], max_length=20)),
                ('balance', models.DecimalField(decimal_places=2, default=0.0, help_text='Aktueller Kontostand in USD/EUR', max_digits=10)),
                ('currency', models.CharField(default='USD', help_text='Währung (USD, EUR)', max_length=3)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('auto_warning_threshold', models.DecimalField(decimal_places=2, default=5.0, help_text='Warnung bei diesem Kontostand', max_digits=10)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'API-Kontostand',
                'verbose_name_plural': 'API-Kontostände',
                'unique_together': {('user', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='APIUsageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('openai', 'OpenAI (ChatGPT)'), ('anthropic', 'Anthropic (Claude)'), ('google', 'Google (Gemini)')], max_length=20)),
                ('model_name', models.CharField(help_text='z.B. gpt-4.1, claude-opus-4', max_length=50)),
                ('prompt_tokens', models.PositiveIntegerField(default=0)),
                ('completion_tokens', models.PositiveIntegerField(default=0)),
                ('total_tokens', models.PositiveIntegerField(default=0)),
                ('estimated_cost', models.DecimalField(decimal_places=4, default=0.0, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('training', models.ForeignKey(blank=True, help_text='Zugehöriges Training falls vorhanden', null=True, on_delete=django.db.models.deletion.SET_NULL, to='naturmacher.training')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'API-Nutzungsprotokoll',
                'verbose_name_plural': 'API-Nutzungsprotokolle',
                'ordering': ['-created_at'],
            },
        ),
    ]