#!/usr/bin/env python3
"""
Diagnose-Script: Prüft ob das original_image Feld in der Datenbank existiert
"""
import django
import os
import sys

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from shopify_uploads.models import FotogravurImage
from django.db import connection

print("=" * 60)
print("DIAGNOSE: Original-Bild Feld")
print("=" * 60)

# 1. Model-Felder prüfen
print("\n1. Model-Felder:")
print("-" * 60)
fields = [f.name for f in FotogravurImage._meta.get_fields()]
print(f"Alle Felder: {', '.join(fields)}")

if 'original_image' in fields:
    print("✅ original_image Feld im Model vorhanden")
else:
    print("❌ original_image Feld NICHT im Model vorhanden")
    sys.exit(1)

# 2. Datenbank-Schema prüfen
print("\n2. Datenbank-Schema:")
print("-" * 60)
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'shopify_uploads_fotogravurimage'
        ORDER BY ordinal_position;
    """)

    columns = cursor.fetchall()
    has_original_image = False

    print(f"{'Spalte':<30} {'Typ':<20} {'Nullable':<10}")
    print("-" * 60)
    for col_name, col_type, is_nullable in columns:
        print(f"{col_name:<30} {col_type:<20} {is_nullable:<10}")
        if col_name == 'original_image':
            has_original_image = True

    if has_original_image:
        print("\n✅ original_image Spalte in Datenbank vorhanden")
    else:
        print("\n❌ original_image Spalte NICHT in Datenbank vorhanden")
        print("\n⚠️  MIGRATION WURDE NICHT AUSGEFÜHRT!")
        print("Bitte ausführen: python manage.py migrate")
        sys.exit(1)

# 3. Angewandte Migrationen prüfen
print("\n3. Migrationen:")
print("-" * 60)
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT id, app, name, applied
        FROM django_migrations
        WHERE app = 'shopify_uploads'
        ORDER BY id;
    """)

    migrations = cursor.fetchall()
    has_0002 = False

    for mid, app, name, applied in migrations:
        status = "✅" if applied else "❌"
        print(f"{status} {name} ({applied})")
        if name == '0002_fotogravurimage_original_image':
            has_0002 = True

    if has_0002:
        print("\n✅ Migration 0002 wurde ausgeführt")
    else:
        print("\n❌ Migration 0002 wurde NICHT ausgeführt")
        print("Bitte ausführen: python manage.py migrate shopify_uploads")
        sys.exit(1)

# 4. Test-Eintrag prüfen
print("\n4. Test-Eintrag:")
print("-" * 60)
test_entry = FotogravurImage.objects.filter(unique_id='test_original_check').first()
if test_entry:
    print(f"✅ Test-Eintrag gefunden: {test_entry.unique_id}")
    print(f"   - S/W-Bild: {test_entry.image.url if test_entry.image else 'NICHT vorhanden'}")
    print(f"   - Original: {test_entry.original_image.url if test_entry.original_image else 'NICHT vorhanden'}")

    if test_entry.original_image:
        print("\n✅ Original-Bild wird korrekt gespeichert!")
    else:
        print("\n⚠️  Test-Eintrag hat kein Original-Bild")
        print("Möglicherweise Problem beim Upload von Frontend")
else:
    print("ℹ️  Kein Test-Eintrag vorhanden (noch kein Upload durchgeführt)")

print("\n" + "=" * 60)
print("DIAGNOSE ABGESCHLOSSEN")
print("=" * 60)
