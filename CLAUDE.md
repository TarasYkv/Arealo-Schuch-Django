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

#### PythonAnywhere (⚠️ NICHT AKTIV - Nur lokale Entwicklung)
- **Status:** Server-Deployment ist pausiert
- **Aktueller Workflow:** Nur lokale Entwicklung auf WSL2
- **Hinweis:** PythonAnywhere API und SSH MCP sind konfiguriert aber werden nicht verwendet

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
- **KEIN automatisches Deployment** - nur lokale Entwicklung
- MySQL läuft lokal, nicht auf Server
- Bei DB-Problemen: `python manage.py migrate --run-syncdb`
- Statische Dateien: `python manage.py collectstatic` nur bei Bedarf

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