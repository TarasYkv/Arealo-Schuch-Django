#!/bin/bash
# Automatisches Setup-Script für nginx CORS-Konfiguration
# Dieses Script konfiguriert nginx automatisch für Cross-Origin Media-Zugriff

echo "=================================================="
echo "NGINX CORS AUTO-SETUP FÜR FOTOGRAVUR"
echo "=================================================="
echo ""

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Prüfe ob nginx installiert ist
echo "1. Prüfe nginx Installation..."
if ! command -v nginx &> /dev/null; then
    echo -e "${RED}✗ nginx ist nicht installiert!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ nginx gefunden${NC}"

# 2. Finde MEDIA_ROOT Pfad aus Django settings
echo ""
echo "2. Ermittle MEDIA_ROOT Pfad..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MEDIA_ROOT=$(python manage.py shell -c "from django.conf import settings; print(settings.MEDIA_ROOT)" 2>/dev/null)

if [ -z "$MEDIA_ROOT" ]; then
    echo -e "${YELLOW}⚠ Konnte MEDIA_ROOT nicht automatisch ermitteln${NC}"
    echo "Verwende Standard: $SCRIPT_DIR/media"
    MEDIA_ROOT="$SCRIPT_DIR/media"
fi

echo -e "${GREEN}✓ MEDIA_ROOT: $MEDIA_ROOT${NC}"

# 3. Prüfe ob MEDIA_ROOT existiert
if [ ! -d "$MEDIA_ROOT" ]; then
    echo -e "${YELLOW}⚠ MEDIA_ROOT existiert nicht, erstelle Verzeichnis...${NC}"
    mkdir -p "$MEDIA_ROOT"
    echo -e "${GREEN}✓ Verzeichnis erstellt${NC}"
fi

# 4. Finde nginx-Konfigurationsdatei
echo ""
echo "3. Suche nginx-Konfiguration..."

NGINX_CONFIG=""
POSSIBLE_CONFIGS=(
    "/etc/nginx/sites-available/workloom.de"
    "/etc/nginx/sites-available/www.workloom.de"
    "/etc/nginx/conf.d/workloom.de.conf"
    "/etc/nginx/conf.d/www.workloom.de.conf"
    "/etc/nginx/sites-enabled/default"
)

for config in "${POSSIBLE_CONFIGS[@]}"; do
    if [ -f "$config" ]; then
        # Prüfe ob workloom.de in der Config vorkommt
        if grep -q "workloom.de" "$config" 2>/dev/null; then
            NGINX_CONFIG="$config"
            break
        fi
    fi
done

if [ -z "$NGINX_CONFIG" ]; then
    echo -e "${RED}✗ Konnte nginx-Konfiguration für workloom.de nicht finden!${NC}"
    echo ""
    echo "Mögliche Lösungen:"
    echo "1. Suche manuell: sudo find /etc/nginx -name '*.conf' -o -name 'default'"
    echo "2. Öffne die Datei und füge den CORS-Block ein (siehe NGINX_CORS_SETUP.md)"
    exit 1
fi

echo -e "${GREEN}✓ Gefunden: $NGINX_CONFIG${NC}"

# 5. Erstelle Backup
echo ""
echo "4. Erstelle Backup der aktuellen Konfiguration..."
BACKUP_FILE="${NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
sudo cp "$NGINX_CONFIG" "$BACKUP_FILE"
echo -e "${GREEN}✓ Backup: $BACKUP_FILE${NC}"

# 6. Prüfe ob /media/ Block bereits existiert
echo ""
echo "5. Prüfe bestehende /media/ Konfiguration..."
if sudo grep -q "location /media/" "$NGINX_CONFIG"; then
    echo -e "${YELLOW}⚠ /media/ Block existiert bereits!${NC}"
    echo ""
    echo "Optionen:"
    echo "1. Manuell CORS-Header hinzufügen"
    echo "2. Backup wiederherstellen und neu starten"
    echo ""
    read -p "Trotzdem fortfahren und CORS-Header hinzufügen? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 7. Erstelle temporäre Datei mit CORS-Block
echo ""
echo "6. Erstelle CORS-Konfiguration..."
TEMP_CORS_BLOCK=$(mktemp)
cat > "$TEMP_CORS_BLOCK" << 'EOFCORS'

    # Fotogravur Media Files mit CORS (automatisch hinzugefügt)
    location /media/ {
        alias MEDIA_ROOT_PLACEHOLDER;

        # CORS-Header für naturmacher.de
        add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
        add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
        add_header 'Access-Control-Max-Age' '86400' always;

        # Handle OPTIONS preflight requests
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://naturmacher.de' always;
            add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept' always;
            add_header 'Access-Control-Max-Age' '86400' always;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Cache-Header für Performance
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
EOFCORS

# Ersetze Platzhalter mit tatsächlichem Pfad (mit Trailing Slash!)
sed -i "s|MEDIA_ROOT_PLACEHOLDER|${MEDIA_ROOT}/|g" "$TEMP_CORS_BLOCK"

echo -e "${GREEN}✓ CORS-Block erstellt${NC}"

# 8. Finde die richtige Stelle zum Einfügen (vor location / oder am Ende des server-Blocks)
echo ""
echo "7. Füge CORS-Block in nginx-Konfiguration ein..."

# Erstelle neue Konfiguration
TEMP_NEW_CONFIG=$(mktemp)

# Suche nach dem letzten server-Block und füge den CORS-Block davor ein
awk -v cors_block="$(cat $TEMP_CORS_BLOCK)" '
/^}$/ && in_server {
    # Vor dem schließenden } des server-Blocks einfügen
    print cors_block
    print $0
    in_server = 0
    next
}
/^[[:space:]]*server[[:space:]]*{/ {
    in_server = 1
}
{
    print $0
}
' "$NGINX_CONFIG" > "$TEMP_NEW_CONFIG"

# Kopiere die neue Konfiguration
sudo cp "$TEMP_NEW_CONFIG" "$NGINX_CONFIG"

# Aufräumen
rm "$TEMP_CORS_BLOCK" "$TEMP_NEW_CONFIG"

echo -e "${GREEN}✓ CORS-Block eingefügt${NC}"

# 9. Teste nginx-Konfiguration
echo ""
echo "8. Teste nginx-Konfiguration..."
if sudo nginx -t 2>&1 | grep -q "syntax is ok"; then
    echo -e "${GREEN}✓ nginx-Konfiguration ist gültig${NC}"
else
    echo -e "${RED}✗ nginx-Konfiguration hat Fehler!${NC}"
    echo ""
    echo "Teste Konfiguration:"
    sudo nginx -t
    echo ""
    echo "Stelle Backup wieder her:"
    echo "  sudo cp $BACKUP_FILE $NGINX_CONFIG"
    exit 1
fi

# 10. Reload nginx
echo ""
echo "9. Lade nginx neu..."
if sudo systemctl reload nginx; then
    echo -e "${GREEN}✓ nginx erfolgreich neu geladen${NC}"
else
    echo -e "${RED}✗ nginx reload fehlgeschlagen!${NC}"
    echo ""
    echo "Versuche:"
    echo "  sudo systemctl status nginx"
    echo "  sudo systemctl restart nginx"
    exit 1
fi

# 11. Teste CORS-Header
echo ""
echo "10. Teste CORS-Header..."
echo ""

# Finde ein beliebiges Bild in media/fotogravur/originals
TEST_IMAGE=$(find "$MEDIA_ROOT/fotogravur/originals" -type f -name "*.png" | head -1)

if [ ! -z "$TEST_IMAGE" ]; then
    # Extrahiere relativen Pfad
    REL_PATH=${TEST_IMAGE#$MEDIA_ROOT}
    TEST_URL="https://www.workloom.de/media$REL_PATH"

    echo "Teste URL: $TEST_URL"
    CORS_HEADER=$(curl -s -I -H "Origin: https://naturmacher.de" "$TEST_URL" | grep -i "Access-Control-Allow-Origin")

    if echo "$CORS_HEADER" | grep -q "https://naturmacher.de"; then
        echo -e "${GREEN}✓ CORS-Header korrekt gesetzt!${NC}"
        echo "  $CORS_HEADER"
    else
        echo -e "${YELLOW}⚠ CORS-Header nicht gefunden${NC}"
        echo "  Möglicherweise gibt es ein Problem mit der nginx-Konfiguration"
    fi
else
    echo -e "${YELLOW}⚠ Kein Test-Bild gefunden${NC}"
    echo "  Teste nach dem ersten Upload"
fi

# 12. Zusammenfassung
echo ""
echo "=================================================="
echo "SETUP ABGESCHLOSSEN"
echo "=================================================="
echo ""
echo -e "${GREEN}Was wurde gemacht:${NC}"
echo "✓ nginx-Konfiguration gefunden: $NGINX_CONFIG"
echo "✓ Backup erstellt: $BACKUP_FILE"
echo "✓ CORS-Block für /media/ hinzugefügt"
echo "✓ nginx-Konfiguration getestet"
echo "✓ nginx neu geladen"
echo ""
echo -e "${YELLOW}Nächste Schritte:${NC}"
echo "1. Teste Upload auf: https://naturmacher.de/products/blumentopf-mit-fotogravur"
echo "2. Prüfe Debug-Logs auf '✅ Bild von workloom.de geladen'"
echo "3. Bei Problemen: sudo cp $BACKUP_FILE $NGINX_CONFIG && sudo systemctl reload nginx"
echo ""
echo -e "${GREEN}Fertig! 🎉${NC}"
echo ""
