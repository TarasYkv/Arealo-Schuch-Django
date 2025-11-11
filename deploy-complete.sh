#!/bin/bash
# KOMPLETTES Deployment für Fotogravur Server-Upload Feature
# Führt ALLES aus: Django Backend + nginx CORS Konfiguration

echo "=========================================================="
echo "FOTOGRAVUR KOMPLETTES DEPLOYMENT"
echo "Django Backend + nginx CORS Setup"
echo "=========================================================="
echo ""

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Prüfe ob Scripts existieren
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ ! -f "$SCRIPT_DIR/deploy-fotogravur.sh" ]; then
    echo -e "${RED}✗ deploy-fotogravur.sh nicht gefunden!${NC}"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/setup-nginx-cors.sh" ]; then
    echo -e "${RED}✗ setup-nginx-cors.sh nicht gefunden!${NC}"
    exit 1
fi

# ====================
# SCHRITT 1: Django Backend
# ====================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}SCHRITT 1/2: Django Backend Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

bash "$SCRIPT_DIR/deploy-fotogravur.sh"
DJANGO_EXIT=$?

if [ $DJANGO_EXIT -ne 0 ]; then
    echo ""
    echo -e "${RED}✗ Django Deployment fehlgeschlagen!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Django Backend erfolgreich deployed${NC}"

# ====================
# SCHRITT 2: nginx CORS
# ====================
echo ""
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}SCHRITT 2/2: nginx CORS Konfiguration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

bash "$SCRIPT_DIR/setup-nginx-cors.sh"
NGINX_EXIT=$?

if [ $NGINX_EXIT -ne 0 ]; then
    echo ""
    echo -e "${RED}✗ nginx Setup fehlgeschlagen!${NC}"
    echo ""
    echo "Django Backend ist deployed, aber nginx CORS fehlt noch."
    echo "Versuche manuell: ./setup-nginx-cors.sh"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ nginx CORS erfolgreich konfiguriert${NC}"

# ====================
# ABSCHLUSS
# ====================
echo ""
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓✓✓ KOMPLETTES DEPLOYMENT ERFOLGREICH ✓✓✓${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Was wurde deployed:${NC}"
echo "✓ Django Backend (Upload-Endpoints, Templates, Views)"
echo "✓ nginx CORS-Header für /media/ URLs"
echo "✓ Gunicorn Server neugestartet"
echo "✓ nginx neu geladen"
echo ""
echo -e "${YELLOW}Teste jetzt:${NC}"
echo "1. Gehe zu: https://naturmacher.de/products/blumentopf-mit-fotogravur"
echo "2. Lade ein Bild hoch (MOBILE TESTEN!)"
echo "3. Erwartete Logs:"
echo "   • ✅ Original-Bild erfolgreich hochgeladen"
echo "   • ✅ Bild von workloom.de geladen: 1024x768"
echo "   • ⚙️ Starte processUploadedImage..."
echo "   • ✅ handleImageUpload ABGESCHLOSSEN"
echo ""
echo -e "${GREEN}4. Prüfe Admin:${NC}"
echo "   https://www.workloom.de/admin/shopify_uploads/fotogravurimage/"
echo ""
echo -e "${YELLOW}Bei Problemen:${NC}"
echo "• nginx Logs: sudo tail -f /var/log/nginx/error.log"
echo "• Django Logs: sudo journalctl -u gunicorn -f"
echo "• CORS testen: curl -I -H 'Origin: https://naturmacher.de' https://www.workloom.de/media/..."
echo ""
echo -e "${GREEN}Fertig! 🎉🎉🎉${NC}"
echo ""
