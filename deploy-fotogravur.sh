#!/bin/bash
# Deployment-Script für Fotogravur Server-Upload Feature
# Dieses Script deployed die Backend-Änderungen auf workloom.de

echo "=================================================="
echo "FOTOGRAVUR SERVER-UPLOAD FEATURE DEPLOYMENT"
echo "=================================================="
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Neuesten Code holen
echo "1. Hole neuesten Code von GitHub..."
git fetch origin
git pull origin master

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Code erfolgreich aktualisiert${NC}"
else
    echo -e "${RED}✗ Fehler beim Git Pull${NC}"
    exit 1
fi

# 2. Neuesten Commit anzeigen
echo ""
echo "2. Neuester Commit:"
git log -1 --oneline

# 3. Python-Cache löschen
echo ""
echo "3. Lösche Python-Cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo -e "${GREEN}✓ Cache gelöscht${NC}"

# 4. Dependencies installieren (falls nötig)
echo ""
echo "4. Installiere Dependencies..."
pip install -r requirements.txt --quiet

# 5. Migrations prüfen
echo ""
echo "5. Prüfe Migrations..."
python manage.py migrate --check 2>&1 | grep -q "No migrations"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Keine neuen Migrations${NC}"
else
    echo ""
    echo "6. Führe Migrations aus..."
    python manage.py migrate

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Migrations erfolgreich${NC}"
    else
        echo -e "${RED}✗ Migrations fehlgeschlagen${NC}"
        exit 1
    fi
fi

# 6. Server neustarten
echo ""
echo "7. Starte Server neu..."

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
    echo "Versuche: sudo systemctl restart gunicorn"
fi

# 7. Zusammenfassung
echo ""
echo "=================================================="
echo "DEPLOYMENT ABGESCHLOSSEN"
echo "=================================================="
echo ""
echo -e "${GREEN}Was wurde geändert:${NC}"
echo "✓ Backend-Endpoint akzeptiert jetzt Initial-Uploads (nur Original-Bild)"
echo "✓ Backend-Endpoint unterstützt Updates (S/W-Bild nachträglich)"
echo "✓ Original-Bilder werden sofort nach Auswahl hochgeladen"
echo "✓ Bilder werden von workloom.de geladen (löst Mobile-File-Problem)"
echo ""
echo -e "${GREEN}Frontend (Shopify) Status:${NC}"
echo "✓ Bereits live deployed"
echo ""
echo -e "${YELLOW}Test:${NC}"
echo "1. Gehe zu: https://naturmacher.de/products/blumentopf-mit-fotogravur"
echo "2. Lade ein Bild hoch (besonders auf Mobile testen!)"
echo "3. Prüfe Debug-Logs auf Erfolg"
echo "4. Prüfe im Admin: https://www.workloom.de/admin/shopify_uploads/fotogravurimage/"
echo ""
