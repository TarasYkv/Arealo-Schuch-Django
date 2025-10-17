# 🚀 Schnelle KI-API Einrichtung

## Problem: "KI-API nicht verfügbar" für alle APIs

Das Problem ist, dass keine API-Keys konfiguriert sind. Hier ist die schnellste Lösung:

## ⚡ Schnellste Lösung: Google Gemini (kostenlos)

### Schritt 1: Google AI API Key holen
1. Gehen Sie zu: https://ai.google.dev/
2. Klicken Sie auf "Get API key in Google AI Studio"
3. Erstellen Sie einen neuen API Key
4. Kopieren Sie den Key (beginnt mit "AIza...")

### Schritt 2: .env Datei erstellen
Erstellen Sie eine Datei namens `.env` im Projektverzeichnis:

```bash
# Datei: .env (im Hauptverzeichnis des Projekts)
GOOGLE_AI_API_KEY=AIzaSyA...ihr-echter-key-hier
```

### Schritt 3: Server neu starten
```bash
python manage.py runserver
```

Beim Start sollten Sie jetzt sehen:
```
🔧 API-Keys Status:
   OpenAI: ❌ Nicht gesetzt
   Claude: ❌ Nicht gesetzt  
   Gemini: ✅ Konfiguriert
```

## 🎯 Test der KI-Integration

1. Öffnen Sie die Naturmacher-Anwendung
2. Gehen Sie zu einem Thema
3. Klicken Sie auf "KI-Schulung erstellen"
4. Wählen Sie "Google Gemini" als KI-Anbieter
5. Füllen Sie das Formular aus und erstellen Sie eine Schulung

## 📊 Andere APIs hinzufügen (optional)

### Claude API (beste Qualität)
```bash
# In .env Datei hinzufügen:
ANTHROPIC_API_KEY=sk-ant-api03-...ihr-key
```
Registrierung: https://console.anthropic.com/

### OpenAI API
```bash
# In .env Datei hinzufügen:
OPENAI_API_KEY=sk-...ihr-key
```
Registrierung: https://platform.openai.com/

## 🔒 Sicherheit

**WICHTIG:** 
- Fügen Sie `.env` zu `.gitignore` hinzu
- Committen Sie NIEMALS API-Keys
- Die .env Datei sollte nur lokal existieren

## 🐛 Debugging

Falls es immer noch nicht funktioniert:
1. Überprüfen Sie die Konsolen-Ausgabe beim Server-Start
2. Schauen Sie in den Django-Logs nach detaillierten Fehlermeldungen
3. Die API-Funktionen geben jetzt detaillierte Debug-Informationen aus

## 💡 Schnelltest

Für einen sofortigen Test können Sie auch direkt in der `settings.py` einen API-Key setzen:

```python
# NUR FÜR TESTS - NICHT FÜR PRODUKTION!
GOOGLE_AI_API_KEY = "AIzaSyA...ihr-key-hier"
```

**Vergessen Sie nicht, das wieder zu entfernen und eine .env Datei zu verwenden!**