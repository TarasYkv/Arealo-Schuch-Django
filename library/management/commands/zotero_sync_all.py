"""Management-Command für automatischen Zotero-Sync aller Accounts mit auto_sync=True.

Einsatz via Cron (z.B. stündlich):
    0 * * * * cd /var/www/workloom && source venv/bin/activate && python manage.py zotero_sync_all
"""
import logging
from django.core.management.base import BaseCommand
from library.models import ZoteroAccount
from library.zotero_sync import sync_account

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronisiert alle ZoteroAccounts mit auto_sync=True."

    def add_arguments(self, p):
        p.add_argument("--user", help="Nur einen bestimmten User synchronisieren")
        p.add_argument("--all", action="store_true",
                       help="Alle Accounts synchronisieren (ignoriert auto_sync-Flag)")

    def handle(self, *a, **o):
        qs = ZoteroAccount.objects.all()
        if not o["all"]:
            qs = qs.filter(auto_sync=True)
        if o["user"]:
            qs = qs.filter(owner__username=o["user"])

        total_accounts = qs.count()
        self.stdout.write(f"Starte Sync für {total_accounts} Account(s)...")

        summary = {"created": 0, "updated": 0, "errors": 0}
        for account in qs:
            try:
                stats = sync_account(account, collection_name="Zotero-Sync")
                summary["created"] += stats["created"]
                summary["updated"] += stats["updated"]
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {account.owner.username}: {stats['created']} neu, "
                    f"{stats['updated']} aktualisiert"))
            except Exception as e:
                summary["errors"] += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {account.owner.username}: {e}"))
                logger.exception("Zotero-Sync fehlgeschlagen für %s",
                                 account.owner.username)

        self.stdout.write(self.style.SUCCESS(
            f"\nGesamt: {summary['created']} neu, {summary['updated']} aktualisiert, "
            f"{summary['errors']} Fehler"))
