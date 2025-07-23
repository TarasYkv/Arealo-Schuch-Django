"""
Management command to setup default feature access rules
Run: python manage.py setup_feature_access
"""

from django.core.management.base import BaseCommand
from accounts.models import FeatureAccess


class Command(BaseCommand):
    help = 'Setup default feature access rules for all apps and features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing feature access rules and recreate them',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating anything',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - Keine Änderungen werden gespeichert')
            )
        
        if reset and not dry_run:
            self.stdout.write('🗑️ Lösche bestehende Feature-Zugriffsregeln...')
            deleted_count = FeatureAccess.objects.all().delete()[0]
            self.stdout.write(f'   Gelöscht: {deleted_count} Regeln')
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Erstelle Standard Feature-Zugriffsregeln...')
        )
        
        # Standard-Regeln definieren
        default_rules = [
            # Kostenlose Apps/Features
            ('chat', 'free', 'Basis-Chat verfügbar für alle angemeldeten Benutzer'),
            ('videos', 'free', 'Video-Ansicht verfügbar, Upload erfordert Storage-Plan'),
            ('bug_report', 'free', 'Bug-Meldungen verfügbar für alle'),
            ('payments', 'free', 'Abo-Verwaltung verfügbar für alle'),
            ('core', 'free', 'Schuch Startseite und Kernfunktionen verfügbar für alle'),
            
            # Founder's Early Access erforderlich
            ('shopify_manager', 'founder_access', 'Vollständiger Shopify-Manager nur mit Early Access'),
            ('image_editor', 'founder_access', 'Bild-Editor nur mit Early Access'),
            ('naturmacher', 'founder_access', 'Schulungs-Tools nur mit Early Access'),
            ('organization', 'founder_access', 'Organisations-Tools nur mit Early Access'),
            ('todos', 'founder_access', 'Erweiterte ToDo-Features nur mit Early Access'),
            ('pdf_sucher', 'founder_access', 'PDF-Suche nur mit Early Access'),
            ('amortization_calculator', 'founder_access', 'Wirtschaftlichkeitsrechner nur mit Early Access'),
            ('sportplatzApp', 'founder_access', 'Sportplatz-Konfigurator nur mit Early Access'),
            
            # Spezifische Features
            ('video_upload', 'storage_plan', 'Video-Upload erfordert Storage-Plan'),
            ('video_sharing', 'free', 'Video-Sharing verfügbar für alle'),
            ('ai_features', 'founder_access', 'KI-Features nur mit Early Access'),
            ('premium_support', 'any_paid', 'Premium-Support für alle bezahlten Pläne'),
            ('advanced_analytics', 'founder_access', 'Erweiterte Analytik nur mit Early Access'),
        ]
        
        created_count = 0
        updated_count = 0
        
        for app_name, subscription_required, description in default_rules:
            rule_data = {
                'subscription_required': subscription_required,
                'description': description,
                'is_active': True,
                'show_upgrade_prompt': True,
            }
            
            if dry_run:
                self.stdout.write(f'   Würde erstellen/aktualisieren: {app_name} -> {subscription_required}')
                continue
            
            rule, created = FeatureAccess.objects.get_or_create(
                app_name=app_name,
                defaults=rule_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'✅ Erstellt: {rule.get_app_name_display()} -> {rule.get_subscription_required_display()}')
            else:
                # Update existing rule
                for key, value in rule_data.items():
                    setattr(rule, key, value)
                rule.save()
                updated_count += 1
                self.stdout.write(f'🔄 Aktualisiert: {rule.get_app_name_display()} -> {rule.get_subscription_required_display()}')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(f'📊 DRY RUN Zusammenfassung: {len(default_rules)} Regeln würden erstellt/aktualisiert')
            )
            return
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('📊 Zusammenfassung:')
        )
        self.stdout.write(f'   Regeln erstellt: {created_count}')
        self.stdout.write(f'   Regeln aktualisiert: {updated_count}')
        self.stdout.write(f'   Gesamt Regeln: {FeatureAccess.objects.count()}')
        
        # Zeige aktuelle Statistiken
        self.stdout.write('')
        self.stdout.write('📋 Aktuelle Feature-Zugriff Statistiken:')
        
        free_count = FeatureAccess.objects.filter(subscription_required='free').count()
        founder_count = FeatureAccess.objects.filter(subscription_required='founder_access').count()
        paid_count = FeatureAccess.objects.filter(subscription_required='any_paid').count()
        storage_count = FeatureAccess.objects.filter(subscription_required='storage_plan').count()
        blocked_count = FeatureAccess.objects.filter(subscription_required='blocked').count()
        
        self.stdout.write('')
        self.stdout.write('🔓 Kostenlose Features:')
        for feature in FeatureAccess.objects.filter(subscription_required='free'):
            self.stdout.write(f'   - {feature.get_app_name_display()}')
        
        self.stdout.write('')
        self.stdout.write('🌟 Founder\'s Early Access Features:')
        for feature in FeatureAccess.objects.filter(subscription_required='founder_access'):
            self.stdout.write(f'   - {feature.get_app_name_display()}')
        
        if storage_count > 0:
            self.stdout.write('')
            self.stdout.write('💾 Storage-Plan Features:')
            for feature in FeatureAccess.objects.filter(subscription_required='storage_plan'):
                self.stdout.write(f'   - {feature.get_app_name_display()}')
        
        if paid_count > 0:
            self.stdout.write('')
            self.stdout.write('💰 Beliebiges bezahltes Abo:')
            for feature in FeatureAccess.objects.filter(subscription_required='any_paid'):
                self.stdout.write(f'   - {feature.get_app_name_display()}')
        
        if blocked_count > 0:
            self.stdout.write('')
            self.stdout.write('🚫 Gesperrte Features:')
            for feature in FeatureAccess.objects.filter(subscription_required='blocked'):
                self.stdout.write(f'   - {feature.get_app_name_display()}')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('✅ Feature-Zugriffsregeln erfolgreich eingerichtet!')
        )
        self.stdout.write('')
        self.stdout.write('💡 Nächste Schritte:')
        self.stdout.write('   1. Admin-Interface prüfen: /admin/accounts/featureaccess/')
        self.stdout.write('   2. Views mit @require_subscription_access() Decorator schützen')
        self.stdout.write('   3. Templates mit {% load feature_access %} erweitern')
        self.stdout.write('   4. Navigation mit Feature-Badges versehen')