# Issue: Design Mail - Modernes Email-Interface

## Zusammenfassung
Komplette Neugestaltung des Mail-Interfaces mit einem modernen, dreispaltigen Layout ähnlich zu professionellen Email-Clients wie Gmail oder Outlook. Das Design soll schlicht, elegant und modern sein.

## Gewünschte Features
- **Dreispaltiges Layout**: Ordner links | Email-Liste mitte | Email-Inhalt rechts
- **Inline Email-Antwort**: Direkt auf Emails antworten ohne Popup
- **Email-Weiterleitung**: Emails direkt weiterleiten können
- **Rich-Text Editor**: Mit Bildeinfügung und Formatierung
- **Multiple Email-Adressen**: Eigene Email-Adressen hinzufügen
- **Vollständige Email-Darstellung**: Original HTML/CSS der Email beibehalten

## Implementierungsplan in Phasen

### Phase 1: Layout-Grundstruktur (2-3 Tage)
```
1. Neues dreispaltiges Layout erstellen
   - Linke Spalte: Ordner-Navigation (200-250px breit)
   - Mittlere Spalte: Email-Liste (300-400px breit)
   - Rechte Spalte: Email-Vorschau (flexibel)
   
2. Responsive Design implementieren
   - Mobile: Spalten untereinander
   - Tablet: 2 Spalten (Ordner/Liste zusammen, Email separat)
   - Desktop: Alle 3 Spalten
   
3. CSS Framework anpassen
   - Moderne Farbpalette definieren
   - Schatten und Hover-Effekte
   - Smooth Transitions
```

### Phase 2: Ordner-Navigation (1-2 Tage)
```
1. Ordner-Sidebar gestalten
   - Icons für jeden Ordnertyp
   - Ungelesene Email-Counter als Badge
   - Aktiver Ordner hervorheben
   - Collapse/Expand für Unterordner
   
2. Ordner-Funktionalität
   - AJAX-basiertes Laden ohne Seitenreload
   - Ordner erstellen/umbenennen/löschen
   - Drag & Drop für Email-Verschiebung
```

### Phase 3: Email-Liste (2 Tage)
```
1. Email-Liste Design
   - Kompakte Darstellung mit Absender, Betreff, Datum
   - Vorschau der ersten Zeile
   - Ungelesene Emails fett
   - Anhang-Indikator
   - Stern/Flag-Funktionen
   
2. Interaktionen
   - Klick öffnet Email in rechter Spalte
   - Mehrfachauswahl mit Checkboxen
   - Bulk-Aktionen (löschen, verschieben, markieren)
   - Infinite Scroll oder Pagination
```

### Phase 4: Email-Anzeige (3 Tage)
```
1. Email-Viewer implementieren
   - Vollständige HTML-Email-Darstellung in iframe
   - Sicherheit: CSS-Sandbox, JavaScript blockieren
   - Anhänge-Vorschau und Download
   - Email-Header mit Absender-Details
   
2. Aktions-Toolbar
   - Antworten-Button
   - Allen antworten
   - Weiterleiten
   - Löschen/Archivieren
   - Als Spam markieren
   - Drucken
```

### Phase 5: Email-Composer (3-4 Tage)
```
1. Inline-Antwort implementieren
   - Composer unterhalb der Email einblenden
   - Original-Email als Zitat einfügen
   - An/CC/BCC Felder
   
2. Rich-Text Editor erweitern
   - Quill.js oder TinyMCE konfigurieren
   - Bildupload und -einfügung
   - Formatierungsoptionen (Bold, Italic, Listen, etc.)
   - Email-Signatur verwalten
   
3. Erweiterte Features
   - Entwürfe automatisch speichern
   - Anhänge per Drag & Drop
   - Email-Vorlagen
   - Senden planen
```

### Phase 6: Multi-Account Support (2 Tage)
```
1. Account-Switcher implementieren
   - Dropdown in der Toolbar
   - Account-spezifische Ordner
   - Unified Inbox Option
   
2. Absender-Auswahl
   - "Von"-Dropdown im Composer
   - Standard-Absender festlegen
   - Alias-Adressen verwalten
```

### Phase 7: Performance & Polish (2 Tage)
```
1. Performance-Optimierung
   - Email-Caching
   - Lazy Loading
   - WebSocket für Real-time Updates
   
2. UI-Verfeinerungen
   - Animations und Transitions
   - Dark Mode
   - Keyboard Shortcuts
   - Accessibility (ARIA labels)
```

## Technische Überlegungen

### Frontend-Stack
- **Framework**: Vanilla JS mit modernen ES6+ Features oder Vue.js/React
- **CSS**: Tailwind CSS oder custom CSS mit CSS Grid/Flexbox
- **Editor**: Quill.js für Rich-Text
- **Icons**: Lucide Icons oder Font Awesome

### Backend-Anpassungen
- REST API erweitern für:
  - Pagination/Filtering
  - Email-Aktionen (reply, forward)
  - Real-time Updates
- WebSocket für Live-Updates
- Email-HTML-Sanitization

### Sicherheit
- XSS-Schutz bei Email-Darstellung
- CSRF-Token für alle Aktionen
- Content Security Policy für Email-iframes
- Anhang-Virus-Scanning

## Design-Mockup Struktur
```
+------------------+------------------+--------------------------------+
|   ORDNER         |   EMAIL-LISTE    |        EMAIL-INHALT           |
+------------------+------------------+--------------------------------+
| ✉️ Posteingang(3) | Von: Max M.      | Von: max@example.com          |
| 📤 Gesendet      | Betreff: Meeting | An: ich@example.com           |
| 📝 Entwürfe (1)  | Heute, 14:32     | Betreff: Meeting morgen       |
| 🗑️ Papierkorb    |                  |                               |
|                  | Von: Anna K.     | Hallo,                        |
| + Neuer Ordner   | Betreff: Projekt | könnten wir uns morgen...     |
|                  | Gestern, 09:15   |                               |
|                  |                  | [Antworten] [Weiterleiten]    |
+------------------+------------------+--------------------------------+
```

## Geschätzter Zeitrahmen
- **Gesamt**: 15-20 Arbeitstage
- **MVP** (Phase 1-4): 8-10 Tage
- **Vollständige Implementierung**: 15-20 Tage

## Prioritäten
1. **Hoch**: Layout, Email-Anzeige, Basis-Navigation
2. **Mittel**: Inline-Antwort, Rich-Text Editor
3. **Niedrig**: Multi-Account, erweiterte Features

---

*Erstellt am: 2025-01-24*
*Status: Planung*
*Priorität: Hoch*