# 🎫 Intelligentes Ticket-Gruppierungssystem

## Übersicht

Das Email-System wurde um ein intelligentes Ticket-Gruppierungssystem erweitert, das automatisch verwandte Emails gruppiert und als Tickets verwaltet.

## ✨ Neue Funktionen

### 1. **Automatische Email-Gruppierung**
Wenn eine Email als "offen" markiert wird, werden automatisch alle verwandten Emails derselben Absender-Adresse ebenfalls als offen markiert und zum gleichen Ticket hinzugefügt.

### 2. **Zwei Gruppierungsmodi**
- **Nach Email-Adresse** (Standard): Alle Emails von derselben Absender-Adresse werden gruppiert
- **Nach Email + Betreff**: Emails werden nur gruppiert, wenn sie von derselben Absender-Adresse stammen UND ähnliche Betreff-Zeilen haben

### 3. **Intelligente Betreff-Erkennung**
Das System erkennt automatisch ähnliche Betreff-Zeilen, auch wenn sie Prefixe wie "Re:", "AW:", "Fw:" etc. enthalten:
- `"Important Meeting"` ↔ `"Re: Important Meeting"` ↔ `"AW: Important Meeting"`
- Werden alle als gleich erkannt und gruppiert

## 🎮 Bedienung

### Im Email-Dashboard (`/mail/standalone/`)

1. **Gruppierungsmodus auswählen**:
   - Oben rechts im Email-List-Header finden Sie das Dropdown "Ticket-Gruppierung"
   - Wählen Sie zwischen "Nach Email" oder "Nach Email + Betreff"
   - Die Einstellung wird automatisch gespeichert

2. **Email als offen markieren**:
   - Klicken Sie auf den "⭕ Markieren" Button bei einer Email
   - Das System erstellt automatisch ein Ticket und gruppiert verwandte Emails
   - Sie erhalten eine Benachrichtigung über die Anzahl der gruppierten Emails

3. **Tickets anzeigen**:
   - Besuchen Sie `/mail/tickets/` um alle offenen Tickets zu sehen
   - Jedes Ticket zeigt alle gruppierten Emails chronologisch an

## 🔧 Technische Details

### Datenbank-Änderungen
- Neues Feld `grouping_mode` in Ticket-Modell
- Neues Feld `normalized_subject` für intelligente Betreff-Matching
- Erweiterte Indizierung für bessere Performance

### API-Änderungen
- `toggle_email_open` API akzeptiert nun `grouping_mode` Parameter
- Rückgabe enthält `auto_grouped_count` für UI-Feedback

### Betreff-Normalisierung
Automatische Entfernung von:
- `Re:`, `RE:`, `Fw:`, `FWD:`
- `AW:`, `WG:` (Deutsche Prefixe)  
- `Reply:`, `Antwort:`, `Antw:`
- `[Tag]` Prefixe
- Extra Leerzeichen

## 📊 Management Commands

### Testen des Systems
```bash
# Zeigt aktuellen Status aller Tickets
python manage.py demo_ticket_grouping

# Testet ein einzelnes Email für Ticket-Erstellung  
python manage.py test_single_email <email_id> [--grouping-mode email|email_subject]

# Vollständiger Funktionstest
python manage.py test_ticket_grouping
```

## 🎯 Anwendungsbeispiele

### Beispiel 1: Kundenanfrage-Thread
```
Email 1: "Angebot anfordern" 
Email 2: "Re: Angebot anfordern"
Email 3: "AW: Angebot anfordern - Nachfrage"
```
→ Werden automatisch in einem Ticket gruppiert

### Beispiel 2: Newsletter vs. Anfrage
Mit "Email + Betreff" Modus:
```
Von: kunde@example.com
- "Newsletter Anmeldung" → Ticket A
- "Re: Newsletter Anmeldung" → Ticket A  
- "Produktanfrage" → Ticket B
- "Re: Produktanfrage" → Ticket B
```

### Beispiel 3: Nur Email-Gruppierung
Mit "Email" Modus:
```
Von: kunde@example.com
- Alle Emails → Ein gemeinsames Ticket
```

## 🚀 Vorteile

1. **Effizienz**: Keine manuelle Gruppierung von verwandten Emails nötig
2. **Übersichtlichkeit**: Zusammenhängende Emails werden automatisch als Thread dargestellt
3. **Flexibilität**: Zwei Gruppierungsmodi je nach Bedarf
4. **Intelligenz**: Automatische Erkennung von Email-Threads trotz verschiedener Prefixe
5. **Benutzerfreundlichkeit**: Einfache Bedienung mit sofortigem Feedback

## 🔄 Migration bestehender Daten

Bestehende Tickets werden automatisch migriert:
- `grouping_mode` wird auf "email" (Standard) gesetzt
- `normalized_subject` bleibt leer für Email-only Gruppierung
- Alle bestehenden Funktionen bleiben unverändert

Das System ist rückwärtskompatibel und funktioniert sofort ohne weitere Konfiguration.