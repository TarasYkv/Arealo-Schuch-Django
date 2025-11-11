#!/bin/bash
# Deployment-Script für PythonAnywhere
# Führt automatisch alle Schritte für PythonAnywhere aus

echo "=========================================================="
echo "PYTHONANYWHERE DEPLOYMENT - Fotogravur Feature"
echo "=========================================================="
echo ""

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Git pull
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

# 3. Virtual Environment aktivieren (falls vorhanden)
echo ""
echo "3. Aktiviere Virtual Environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual Environment aktiviert${NC}"
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
    echo -e "${GREEN}✓ Virtual Environment aktiviert${NC}"
else
    echo -e "${YELLOW}⚠ Kein Virtual Environment gefunden (möglicherweise nicht nötig)${NC}"
fi

# 4. Python-Cache löschen
echo ""
echo "4. Lösche Python-Cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
echo -e "${GREEN}✓ Cache gelöscht${NC}"

# 5. Dependencies installieren (falls nötig)
echo ""
echo "5. Installiere Dependencies..."
pip install -r requirements.txt --quiet

# 6. Migrations prüfen
echo ""
echo "6. Prüfe Migrations..."
python manage.py migrate --check 2>&1 | grep -q "No migrations"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Keine neuen Migrations${NC}"
else
    echo ""
    echo "7. Führe Migrations aus..."
    python manage.py migrate

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Migrations erfolgreich${NC}"
    else
        echo -e "${RED}✗ Migrations fehlgeschlagen${NC}"
        exit 1
    fi
fi

# 7. Collectstatic (für PythonAnywhere wichtig!)
echo ""
echo "8. Sammle static files..."
python manage.py collectstatic --noinput --clear

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Static files gesammelt${NC}"
else
    echo -e "${YELLOW}⚠ Static files Problem (möglicherweise nicht kritisch)${NC}"
fi

# 8. PythonAnywhere Web-App neu laden
echo ""
echo "9. Lade PythonAnywhere Web-App neu..."
echo ""
echo -e "${YELLOW}WICHTIG: Du musst jetzt manuell die Web-App neu laden!${NC}"
echo ""
echo "Gehe zu:"
echo "1. https://www.pythonanywhere.com/user/TarasYuzkiv/webapps/"
echo "2. Finde deine Web-App (tarasyuzkiv.pythonanywhere.com oder workloom.de)"
echo "3. Klicke auf den grünen 'Reload' Button"
echo ""

# 9. Zusammenfassung
echo ""
echo "=========================================================="
echo "DEPLOYMENT ABGESCHLOSSEN"
echo "=========================================================="
echo ""
echo -e "${GREEN}Was wurde geändert:${NC}"
echo "✓ Django CORS-Proxy für Media-Dateien"
echo "✓ URL: /shopify-uploads/media/<file_path>"
echo "✓ Bilder werden mit CORS-Headern serviert"
echo "✓ Funktioniert auf PythonAnywhere ohne nginx-Zugriff"
echo ""
echo -e "${RED}⚠ WICHTIGER SCHRITT:${NC}"
echo "1. Gehe zu: https://www.pythonanywhere.com/user/TarasYuzkiv/webapps/"
echo "2. Klicke auf 'Reload' Button (grüner Button oben)"
echo ""
echo -e "${YELLOW}Nach Reload testen:${NC}"
echo "1. Gehe zu: https://naturmacher.de/products/blumentopf-mit-fotogravur"
echo "2. Lade ein Bild hoch (MOBILE TESTEN!)"
echo "3. Erwartete Logs:"
echo "   • ✅ Original-Bild erfolgreich hochgeladen"
echo "   • ✅ Bild von workloom.de geladen: 1024x768"
echo "   • ⚙️ Starte processUploadedImage..."
echo ""
echo "4. Prüfe Admin:"
echo "   https://www.workloom.de/admin/shopify_uploads/fotogravurimage/"
echo ""
echo -e "${GREEN}Fertig! 🎉 (Nach Web-App Reload)${NC}"
echo ""
