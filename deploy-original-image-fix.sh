#!/bin/bash
# Automatisches Deployment-Script für Original-Bild Feature

echo "======================================"
echo "ORIGINAL-BILD FEATURE DEPLOYMENT"
echo "======================================"
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Git Status prüfen
echo "1. Prüfe Git-Status..."
git status

echo ""
echo -e "${YELLOW}Falls 'modified' Dateien angezeigt werden, werden sie zurückgesetzt!${NC}"
echo ""

# 2. Lokale Änderungen verwerfen und neuesten Code holen
echo "2. Hole neuesten Code von GitHub..."
git fetch origin
git reset --hard origin/master

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Code erfolgreich aktualisiert${NC}"
else
    echo -e "${RED}✗ Fehler beim Git Pull${NC}"
    exit 1
fi

# 3. Neuesten Commit anzeigen
echo ""
echo "3. Neuester Commit:"
git log -1 --oneline

# 4. Python-Cache löschen
echo ""
echo "4. Lösche Python-Cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo -e "${GREEN}✓ Cache gelöscht${NC}"

# 5. Migration zurücksetzen und neu ausführen
echo ""
echo "5. Setze Migration zurück..."
python manage.py migrate shopify_uploads 0001

echo ""
echo "6. Führe Migration aus..."
python manage.py migrate shopify_uploads

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migration erfolgreich${NC}"
else
    echo -e "${RED}✗ Migration fehlgeschlagen${NC}"
    exit 1
fi

# 6. Migration-Status prüfen
echo ""
echo "7. Migrations-Status:"
python manage.py showmigrations shopify_uploads

# 7. Datenbank-Spalten prüfen
echo ""
echo "8. Prüfe Datenbank-Spalten..."
python manage.py shell << EOF
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("DESCRIBE shopify_uploads_fotogravurimage;")
    columns = [col[0] for col in cursor.fetchall()]
    if 'original_image' in columns:
        print("✓ original_image Spalte existiert in Datenbank")
    else:
        print("✗ original_image Spalte FEHLT in Datenbank!")
EOF

# 8. Admin.py prüfen
echo ""
echo "9. Prüfe admin.py..."
if grep -q "original_image_preview_large" shopify_uploads/admin.py; then
    echo -e "${GREEN}✓ admin.py wurde korrekt aktualisiert${NC}"
else
    echo -e "${RED}✗ admin.py wurde NICHT aktualisiert${NC}"
    exit 1
fi

# 9. Server neustarten
echo ""
echo "10. Starte Server neu..."

# Versuche verschiedene Restart-Methoden
if command -v systemctl &> /dev/null; then
    sudo systemctl restart gunicorn
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Server mit systemctl neugestartet${NC}"
    else
        echo -e "${YELLOW}Versuche alternative Methode...${NC}"
        sudo service gunicorn restart
    fi
elif command -v service &> /dev/null; then
    sudo service gunicorn restart
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Server mit service neugestartet${NC}"
    fi
else
    echo -e "${RED}✗ Konnte Server nicht neustarten - bitte manuell machen!${NC}"
fi

# 10. Zusammenfassung
echo ""
echo "======================================"
echo "DEPLOYMENT ABGESCHLOSSEN"
echo "======================================"
echo ""
echo -e "${GREEN}Nächster Schritt:${NC}"
echo "1. Gehe zu: https://www.workloom.de/admin/shopify_uploads/fotogravurimage/"
echo "2. Lade ein NEUES Bild hoch (vom Shopify Frontend)"
echo "3. Öffne das neueste Bild im Admin"
echo "4. Du solltest jetzt sehen:"
echo "   - Verarbeitetes Bild (S/W)"
echo "   - Original-Bild (Farbig) ← NEU!"
echo ""
echo -e "${YELLOW}WICHTIG: Das Shopify-Theme muss auch deployed werden!${NC}"
echo "Datei: assets/fotogravur-preview.js"
echo ""
