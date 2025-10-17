# 🤖 KI-Integration für Naturmacher Schulungserstellung

## 🎯 Übersicht

Das Naturmacher-System unterstützt jetzt **echte KI-Integration** zur automatischen Erstellung von maßgeschneiderten HTML-Schulungen. Das System versucht verschiedene KI-APIs in der Reihenfolge ihrer Qualität und fällt bei Fehlern auf die nächste API oder eine Demo-Version zurück.

## 🔧 API-Konfiguration

### 1. Claude API (Anthropic) - **Empfohlen** 🏆
- **Qualität:** Ausgezeichnet für Bildungsinhalte
- **Registrierung:** https://console.anthropic.com/
- **Kosten:** Pay-per-use, sehr effizient
- **Konfiguration in `settings.py`:**
```python
ANTHROPIC_API_KEY = 'sk-ant-api03-...'
```

### 2. OpenAI API (GPT-4) ⭐
- **Qualität:** Sehr gut für strukturierte Inhalte
- **Registrierung:** https://platform.openai.com/
- **Kosten:** Pay-per-use
- **Konfiguration in `settings.py`:**
```python
OPENAI_API_KEY = 'sk-...'
```

### 3. Google Gemini API 🆓
- **Qualität:** Gut, kostenlose Option
- **Registrierung:** https://ai.google.dev/
- **Kosten:** Kostenlos mit Limits
- **Konfiguration in `settings.py`:**
```python
GOOGLE_AI_API_KEY = 'AIza...'
```

## 🚀 Setup-Anweisungen

### Schritt 1: API-Key erhalten
1. Wählen Sie mindestens eine der oben genannten APIs
2. Registrieren Sie sich bei der gewählten Plattform
3. Erstellen Sie einen API-Key

### Schritt 2: Konfiguration
Fügen Sie den API-Key zu Ihrer `settings.py` hinzu:

```python
# Beispiel für Claude (empfohlen)
ANTHROPIC_API_KEY = 'ihr-api-key-hier'

# Oder für OpenAI
OPENAI_API_KEY = 'ihr-api-key-hier'

# Oder für Google Gemini
GOOGLE_AI_API_KEY = 'ihr-api-key-hier'
```

### Schritt 3: Umgebungsvariablen (Empfohlen)
Für Sicherheit verwenden Sie Umgebungsvariablen:

```python
import os

# In settings.py
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY')
```

Dann in Ihrer `.env` Datei:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

## 🎭 Funktionsweise

### API-Fallback-System
1. **Claude API** wird zuerst versucht
2. Bei Fehler wird **OpenAI API** versucht
3. Bei Fehler wird **Gemini API** versucht
4. Bei Fehler wird **Demo-HTML** generiert

### Generierte Inhalte
Die KI erstellt vollständige HTML-Schulungen mit:
- ✅ Interaktiven Checklisten
- ✅ Praktischen Übungen
- ✅ Naturmacher-spezifischen Inhalten
- ✅ Professionellem Design
- ✅ 2-Stunden Lernformat

## 🔒 Sicherheit

**WICHTIG:** 
- ❌ **NIEMALS** API-Keys in den Code committen
- ✅ Verwenden Sie Umgebungsvariablen
- ✅ Fügen Sie `.env` zu `.gitignore` hinzu
- ✅ Rotieren Sie API-Keys regelmäßig

## 🐛 Debugging

### Log-Ausgaben
Das System gibt detaillierte Logs aus:
```
Starte KI-Generierung für Schulung: [Titel]
KI-Generierung erfolgreich - [Anzahl] Zeichen generiert
```

### Häufige Probleme
1. **"Keine KI-API verfügbar"** → Überprüfen Sie API-Key Konfiguration
2. **API-Timeout** → Versuchen Sie es erneut oder verwenden Sie kleinere Prompts
3. **Demo-Version wird verwendet** → Alle APIs sind offline oder falsch konfiguriert

## 💰 Kosten-Schätzung

### Claude (Anthropic)
- ~$0.01-0.05 pro Schulung
- Beste Qualität für Bildungsinhalte

### OpenAI GPT-4
- ~$0.02-0.06 pro Schulung  
- Sehr gute Allzweck-Qualität

### Google Gemini
- Kostenlos bis 15 Requests/Minute
- Gute Qualität für Testzwecke

## 🏃‍♂️ Schnellstart

1. **Einfachste Option:** Google Gemini (kostenlos)
   ```python
   GOOGLE_AI_API_KEY = 'your-key-here'
   ```

2. **Beste Qualität:** Claude API
   ```python
   ANTHROPIC_API_KEY = 'your-key-here'
   ```

3. **Testen:** Erstellen Sie eine neue Schulung über die Web-Oberfläche

## 📞 Support

Bei Problemen:
1. Überprüfen Sie die Django-Logs
2. Testen Sie API-Keys direkt in der jeweiligen Console
3. Stellen Sie sicher, dass alle Dependencies installiert sind: `requests`

**Das System ist jetzt bereit für echte KI-Integration! 🚀**