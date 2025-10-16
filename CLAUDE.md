# Claude Performance & Qualitäts-Anweisungen

## 🧠 Denkzeit & Qualität erzwingen

### Grundlegende Qualitätsanweisungen:
- **"denke lange nach und erkläre dein Vorgehen"**
- **"analysiere das gründlich, bevor du handelst"**
- **"überlege dir mehrere Ansätze und wähle den besten"**
- **"prüfe deine Lösung nochmal kritisch"**

### Bei komplexen Problemen:
- **"zerlege das Problem in kleinere Teile"**
- **"betrachte alle Abhängigkeiten und Seiteneffekte"**
- **"welche Edge Cases könnten auftreten?"**

---

## 📋 Strukturiertes Vorgehen

### Planungsphase:
- **"erstelle erst einen detaillierten Plan"**
- **"liste alle erforderlichen Schritte auf"**
- **"erkläre deine Überlegungen und Entscheidungen"**
- **"was könnte bei diesem Ansatz schief gehen?"**

### Ausführungsphase:
- **"arbeite Schritt für Schritt ab"**
- **"erkläre was du gerade machst und warum"**
- **"teste jeden Schritt bevor du weiter machst"**

---

## 💬 Kommunikation & Rückfragen

### Verständnis sicherstellen:
- **"frag nach, wenn etwas unklar ist"**
- **"treffe keine Annahmen - bestätige dein Verständnis"**
- **"erkläre was du tun wirst, bevor du es machst"**
- **"halte Rücksprache bei wichtigen Entscheidungen"**

### Bei mehrdeutigen Anweisungen:
- **"interpretiere nicht - frag explizit nach"**
- **"liste verschiedene Interpretationen auf und lass wählen"**

---

## ✅ Qualitätskontrolle

### Vor der Ausführung:
- **"überprüfe deine Antwort auf Vollständigkeit"**
- **"hast du alle Aspekte bedacht?"**
- **"gibt es bessere oder elegantere Alternativen?"**
- **"teste deine Lösung gedanklich durch"**

### Nach der Ausführung:
- **"funktioniert die Lösung wie erwartet?"**
- **"sind alle Requirements erfüllt?"**
- **"gibt es potenzielle Probleme oder Verbesserungen?"**

---

## 🎯 Projektspezifische Hinweise

### Django-Projekt Standards:
- Immer vorhandene Patterns und Konventionen befolgen
- Bestehende Libraries und Utilities verwenden
- Code-Style aus umgebenden Dateien übernehmen

### Testing & Linting:
- Nach Code-Änderungen immer verfügbare Lint/Typecheck-Befehle ausführen
- Tests laufen lassen wenn vorhanden
- Niemals Code ohne Überprüfung committen

### E-Mail System:
- SuperConfig Email Backend wird verwendet (Datenbank-Konfiguration)
- Email Templates sind datenbankbasiert über Trigger-System
- SMTP-Konfiguration lädt aus Datenbank, nicht aus Django Settings

### MCP Server & Tools:

#### Chrome DevTools MCP (✅ Installiert)
- **Zweck:** Browser-Automatisierung, Performance-Analyse, Debugging
- **Konfiguration:** `~/.claude.json` - nutzt Windows Chrome über WSL2
- **Verwendung:**
  ```
  - Webseiten im echten Browser öffnen und analysieren
  - Browser-Console-Fehler in Echtzeit sehen
  - Performance-Traces aufzeichnen (Core Web Vitals)
  - Network-Requests analysieren (404, 500, API-Fehler)
  - Screenshots erstellen (Desktop/Mobile)
  - SEO & Meta-Daten validieren
  ```
- **Tools verfügbar:** `mcp__chrome-devtools__*` (nach Claude Code Neustart)
- **Hinweis:** Für volle Funktionalität Chrome mit `--remote-debugging-port=9222` starten

#### PythonAnywhere SSH (✅ AKTIV - Production Deployment)
- **Status:** SSH-Deployment voll funktionsfähig
- **Workflow:** Lokale Entwicklung → Git Push → SSH Deploy
- **Geschwindigkeit:** 30 Sekunden (10-30x schneller als API)
- **Verwendung:** Für alle Server-Deployments
- **Hinweis:** API als Fallback verfügbar, aber SSH bevorzugt

#### GitHub Token (✅ Konfiguriert)
- **Token:** In `.env` als `GH_TOKEN` gespeichert
- **Zweck:** Authentifizierung für GitHub API-Zugriffe
- **Verwendung:**
  ```bash
  # GitHub API-Calls mit Token
  export GH_TOKEN=$(grep GH_TOKEN .env | cut -d'=' -f2)
  curl -H "Authorization: token $GH_TOKEN" https://api.github.com/...

  # Oder mit gh CLI
  gh auth login --with-token <<< "$GH_TOKEN"
  ```
- **Berechtigungen:** Repo-Zugriff, Issues, Pull Requests
- **Wichtig:** Token nicht committen, bleibt in `.env`

### Lokaler Entwicklungs-Workflow:

#### Umgebung:
- **System:** WSL2 (Ubuntu) auf Windows
- **Datenbank:** MySQL lokal (localhost:3306)
- **Python:** Lokale venv in `/mnt/c/Users/taras.yuzkiv/PycharmProjects/Arealo-Schuch/venv`
- **Server:** Django Development Server (`python manage.py runserver`)

#### Standard-Workflow:
1. **Änderungen implementieren**
   ```bash
   # Virtuelle Umgebung aktivieren (falls nötig)
   source venv/bin/activate

   # Code ändern und testen
   python manage.py runserver
   ```

2. **Datenbank-Änderungen**
   ```bash
   # Migrations erstellen
   python manage.py makemigrations

   # Migrations anwenden
   python manage.py migrate
   ```

3. **Testen**
   ```bash
   # Tests ausführen (falls vorhanden)
   python manage.py test

   # Manuelles Testen im Browser
   http://localhost:8000
   ```

4. **Git Commit**
   ```bash
   git add .
   git commit -m "Beschreibung der Änderungen"
   git push origin master
   ```

**Wichtige Hinweise:**
- MySQL läuft lokal (localhost:3306) für Entwicklung
- Bei DB-Problemen: `python manage.py migrate --run-syncdb`
- Statische Dateien: `python manage.py collectstatic` nur bei Bedarf

---

## 🚀 Server-Deployment via SSH (PythonAnywhere)

### SSH-Verbindung (✅ Aktiv & Schnell):
```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com
```

### Standard-Deployment (Empfohlen):

**1. Lokal: Code committen & pushen**
```bash
# Änderungen stagen
git add <geänderte-dateien>

# Commit mit aussagekräftiger Message
git commit -m "Feature: Beschreibung der Änderung

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push zu GitHub
git push origin master
```

**2. Server: Via SSH deployen (⚡ 30 Sekunden)**
```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com << 'EOF'
cd ~/Arealo-Schuch-Django

# Code aktualisieren
git pull origin master

# Migrations anwenden (falls vorhanden)
python manage.py migrate --noinput

# Static Files sammeln (falls geändert)
python manage.py collectstatic --noinput

# WSGI neu laden (WICHTIG!)
touch /var/www/www_workloom_de_wsgi.py

echo "✓ Deployment abgeschlossen!"
EOF
```

**3. Verifizierung**
```bash
# Optional: Django Check ausführen
ssh TarasYuzkiv@ssh.pythonanywhere.com "cd ~/Arealo-Schuch-Django && python manage.py check --deploy"

# Website testen
# https://www.workloom.de
```

### Schnell-Deployment (One-Liner):
```bash
# Nur Code-Änderungen (keine DB/Static)
ssh TarasYuzkiv@ssh.pythonanywhere.com "cd ~/Arealo-Schuch-Django && git pull && touch /var/www/www_workloom_de_wsgi.py"
```

### Deployment mit TodoWrite-Tracking:
Für komplexe Deployments immer Todo-Liste verwenden:
1. Git Status prüfen und Änderungen commiten
2. Änderungen zu GitHub pushen
3. Via SSH auf Server deployen
4. Server-Deployment verifizieren

### Wichtige Deployment-Regeln:
- ✅ **Immer SSH verwenden** (10-30x schneller als API)
- ✅ **WSGI reload nicht vergessen** (`touch /var/www/www_workloom_de_wsgi.py`)
- ✅ **Migrations prüfen** vor Deployment
- ✅ **Django Check** nach größeren Änderungen
- ⚠️ **Server-DB ist MySQL** (nicht SQLite)
- ⚠️ **Python 3.13** auf Server (lokal 3.12)

### Troubleshooting:
```bash
# Fehlende Dependencies installieren
ssh TarasYuzkiv@ssh.pythonanywhere.com "pip install <package> --user"

# Django Shell auf Server
ssh TarasYuzkiv@ssh.pythonanywhere.com "cd ~/Arealo-Schuch-Django && python manage.py shell"

# Logs prüfen
ssh TarasYuzkiv@ssh.pythonanywhere.com "tail -50 /var/log/www.workloom.de.error.log"
```

### Server-Umgebung:
- **Host:** ssh.pythonanywhere.com
- **User:** TarasYuzkiv
- **Projekt-Pfad:** ~/Arealo-Schuch-Django
- **WSGI-Pfad:** /var/www/www_workloom_de_wsgi.py
- **Datenbank:** MySQL (TarasYuzkiv$workloom)
- **Python:** 3.13 (virtualenv: arealo-venv)
- **Domain:** https://www.workloom.de

---

## ❌ Anti-Pattern vermeiden

### Was NICHT tun:
- **Nicht voreilig handeln ohne Verständnis**
- **Nicht raten, sondern prüfen und testen**
- **Nicht Code ohne Tests/Linting ändern**
- **Nicht committen ohne explizite Aufforderung**
- **Nicht Annahmen treffen bei unklaren Anweisungen**

### Bei Unsicherheit:
- **Stoppen und nachfragen**
- **Recherchieren statt raten**
- **Bestehenden Code analysieren vor Änderungen**

---

## 🚀 Effizienz-Tipps

### Für bessere Performance:
- **"verwende parallele Tool-Aufrufe wo möglich"**
- **"batch ähnliche Operationen zusammen"**
- **"nutze spezialisierte Agenten für komplexe Aufgaben"**

### Für Konsistenz:
- **"folge etablierten Mustern im Projekt"**
- **"halte dich an bestehende Namenskonventionen"**
- **"verwende vorhandene Komponenten und Libraries"**

---

## 📝 Praktische Anwendung

### Bei jeder Aufgabe fragen:
1. **Verstehe ich das Problem vollständig?**
2. **Habe ich alle notwendigen Informationen?**
3. **Welche Schritte sind erforderlich?**
4. **Was könnte schief gehen?**
5. **Wie kann ich das testen/überprüfen?**

### Magische Phrases für bessere Qualität:
- **"Denk gründlich nach und erkläre mir deinen Lösungsansatz, bevor du etwas machst"**
- **"Analysiere das Problem systematisch und erstelle einen Schritt-für-Schritt-Plan"**
- **"Prüfe alle Aspekte und mögliche Probleme, bevor du eine Lösung implementierst"**