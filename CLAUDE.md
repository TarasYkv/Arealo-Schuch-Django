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