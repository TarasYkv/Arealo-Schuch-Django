# Migration zur Erstellung aller fehlenden API-Management Tabellen
# Führen Sie diese aus mit: python manage.py migrate

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('naturmacher', '0007_apibalance_api_key'),
    ]

    operations = [
        # Erstelle APIBalance Tabelle falls sie nicht existiert
        migrations.RunSQL(
            """
            CREATE TABLE IF NOT EXISTS naturmacher_apibalance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES auth_user(id),
                provider VARCHAR(20) NOT NULL,
                balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                api_key VARCHAR(255) NOT NULL DEFAULT '',
                last_updated DATETIME NOT NULL,
                auto_warning_threshold DECIMAL(10, 2) NOT NULL DEFAULT 5.00,
                UNIQUE(user_id, provider)
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS naturmacher_apibalance;"
        ),
        
        # Erstelle APIUsageLog Tabelle falls sie nicht existiert
        migrations.RunSQL(
            """
            CREATE TABLE IF NOT EXISTS naturmacher_apiusagelog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES auth_user(id),
                provider VARCHAR(20) NOT NULL,
                model_name VARCHAR(50) NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                estimated_cost DECIMAL(8, 4) NOT NULL DEFAULT 0.0000,
                training_id INTEGER NULL REFERENCES naturmacher_training(id),
                created_at DATETIME NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS naturmacher_apiusagelog;"
        ),
        
        # Erstelle Indizes für bessere Performance
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS idx_apibalance_user_provider 
            ON naturmacher_apibalance(user_id, provider);
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_apibalance_user_provider;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS idx_apiusagelog_user_created 
            ON naturmacher_apiusagelog(user_id, created_at);
            """,
            reverse_sql="DROP INDEX IF EXISTS idx_apiusagelog_user_created;"
        ),
    ]