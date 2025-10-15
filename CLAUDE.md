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

#### PythonAnywhere API (✅ Konfiguriert)
- **API-Key:** In `.env` als `pythonanywhereApiKey` gespeichert
- **Zweck:** Direkter Server-Zugriff für Deployments und Management
- **Verwendung:**
  ```bash
  # Beispiel: Deployment-Script auf Server ausführen
  curl -H "Authorization: Token $pythonanywhereApiKey" \
       https://www.pythonanywhere.com/api/v0/user/TarasYuzkiv/...
  ```
- **Endpoints:**
  - `/api/v0/user/TarasYuzkiv/consoles/` - Console-Management
  - `/api/v0/user/TarasYuzkiv/webapps/` - Web-App Reload
  - `/api/v0/user/TarasYuzkiv/files/` - Datei-Uploads
- **Wichtig:** API-Key nicht committen, bleibt in `.env`

#### PythonAnywhere SSH MCP (✅ Installiert - BEVORZUGTE METHODE)
- **Zugang:** SSH-Zugriff via MCP für direktes Deployment
- **Konfiguration:** `~/.claude.json` - SSH MCP Server
- **Installation:**
  ```bash
  claude mcp add pythonanywhere-ssh npx ssh-mcp -- \
    --host ssh.pythonanywhere.com \
    --user TarasYuzkiv \
    --port 22
  ```
- **Verwendung via Claude Code:**
  - Nach Neustart: Tools `mcp__pythonanywhere-ssh__*` verfügbar
  - Direktes Deployment über natürliche Sprache
  - Automatische SSH-Verbindung und Command-Execution
- **Manueller SSH-Zugang:**
  ```bash
  # SSH-Verbindung herstellen
  ssh TarasYuzkiv@ssh.pythonanywhere.com

  # Deployment ausführen
  cd ~/Arealo-Schuch-Django
  git pull origin master
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  touch /var/www/www_workloom_de_wsgi.py
  ```
- **Vorteil:** Schnellster und zuverlässigster Deployment-Weg!

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

### Deployment Workflow:

#### Methode 1: SSH MCP (✅ EMPFOHLEN - Nach Claude Code Neustart)
1. **Lokal:** Änderungen testen und committen
2. **GitHub:** `git push origin master`
3. **Claude Code:** Einfach sagen: "Deploy to PythonAnywhere via SSH"
   - Automatische SSH-Verbindung
   - Git Pull, Migrations, Collectstatic
   - WSGI Reload

#### Methode 2: PythonAnywhere API (Funktioniert aktuell)
1. **Lokal:** Änderungen testen und committen
2. **GitHub:** `git push origin master`
3. **API Console:**
   ```bash
   # Via Console Commands
   cd /home/TarasYuzkiv/Arealo-Schuch-Django
   git fetch origin && git reset --hard origin/master
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   touch /var/www/www_workloom_de_wsgi.py
   ```

#### Methode 3: Manuelles SSH (Fallback)
```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com
cd ~/Arealo-Schuch-Django && ./deploy_mysql.sh
```

**Wichtige Hinweise:**
- Nach Deployment **immer** WSGI reload: `touch /var/www/www_workloom_de_wsgi.py`
- Bei MySQL Connection Errors: WSGI reload hilft (CONN_MAX_AGE=600)
- Migrations-Konflikte: `python manage.py makemigrations --merge --noinput`

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