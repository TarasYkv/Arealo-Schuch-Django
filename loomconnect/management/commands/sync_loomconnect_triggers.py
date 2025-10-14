"""
Management Command: Sync LoomConnect Email Triggers
Synchronisiert die LoomConnect Email-Trigger in die Datenbank
"""

from django.core.management.base import BaseCommand
from email_templates.trigger_manager import TriggerManager


class Command(BaseCommand):
    help = 'Synchronisiert LoomConnect Email-Trigger in die Datenbank'

    def handle(self, *args, **options):
        self.stdout.write('Synchronisiere LoomConnect Email-Trigger...\n')

        trigger_manager = TriggerManager()
        trigger_manager.sync_triggers_to_database()

        self.stdout.write(self.style.SUCCESS('✅ LoomConnect Email-Trigger erfolgreich synchronisiert!'))
        self.stdout.write('\nVerfügbare Trigger:')
        self.stdout.write('  • loomconnect_new_match - Benachrichtigung über neues Match')
        self.stdout.write('  • loomconnect_new_message - Benachrichtigung über neue Nachricht')
        self.stdout.write('  • loomconnect_weekly_digest - Wöchentliche Zusammenfassung')
        self.stdout.write('  • loomconnect_connection_accepted - Verbindung akzeptiert')
        self.stdout.write('\n📧 Du kannst jetzt Email-Templates für diese Trigger im Admin erstellen!')
