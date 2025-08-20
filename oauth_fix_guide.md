# OAuth Authorization Code Fix Guide

## Problem
OAuth-Autorisierungscode läuft ab bevor er verwendet werden kann ("Authorization code expired or invalid").

## Lösung: Schnelle OAuth-Verbindung

### ✅ SCHRITT 1: Server starten
```bash
python manage.py runserver
```

### ✅ SCHRITT 2: Sofort zur OAuth-URL navigieren
Gehe direkt zu: **http://127.0.0.1:8000/mail/auth/authorize/**

### ✅ SCHRITT 3: Schnelle Autorisierung
1. **SOFORT** Zoho-Login durchführen (nicht warten!)
2. **SOFORT** "Allow" klicken
3. **SOFORT** zur Callback-URL weiterleiten lassen

### ⏱️ TIMING IST KRITISCH
- **Maximal 1-2 Minuten** zwischen Autorisierung und Callback!
- **Keine Pausen** während des OAuth-Flows
- **Sofort handeln** nach jedem Schritt

## ✅ LÖSUNGSSCHRITTE IM DETAIL

### **METHODE 1: Schneller OAuth-Flow (Empfohlen)**

1. **Server läuft lassen:**
   ```bash
   python manage.py runserver
   ```

2. **Neuen Browser-Tab öffnen (oder Inkognito):**
   - Gehe zu: http://127.0.0.1:8000/mail/auth/authorize/

3. **⏱️ SCHNELL HANDELN:**
   - **Schritt 1:** Zoho-Login (sofort)
   - **Schritt 2:** "Allow" klicken (sofort)  
   - **Schritt 3:** Warten auf Redirect (automatisch)
   - **Gesamtzeit:** Maximal 1-2 Minuten!

4. **✅ Erfolgsmeldung erwarten:**
   - "Email account connected successfully!"
   - Falls Fehlermeldung: Sofort wiederholen

---

### **METHODE 2: Fehlerbehebung bei wiederholten Problemen**

Falls Methode 1 nicht funktioniert:

#### 🔍 **Check 1: Zoho App Konfiguration prüfen**

Gehe zu: https://console.zoho.eu/developer/home (EU) oder https://console.zoho.com/developer/home (US)

**Client Details:**
- Client ID: `1000.4SNCS2E6VE317MWQ68SB0P8I3YL0BO`
- Client Secret: **Muss aktuell sein** (nicht vor kurzem regeneriert)

**Redirect URLs:**
- **Muss exakt enthalten:** `http://127.0.0.1:8000/mail/auth/callback/`
- **Achten auf:** Trailing Slash, HTTP vs HTTPS, Port-Nummer

**Scopes:**
- ✅ `ZohoMail.accounts.READ`
- ✅ `ZohoMail.folders.READ`
- ✅ `ZohoMail.messages.READ`
- ✅ `ZohoMail.messages.CREATE`

**App Status:**
- **Muss sein:** "Published" oder "Development"
- **Nicht:** "Draft" oder "Rejected"

#### 🔧 **Check 2: Browser Cache leeren**

```bash
# Chrome/Edge - Entwicklertools öffnen (F12)
# Netzwerk-Tab -> "Disable cache" aktivieren
# Oder Inkognito-Fenster verwenden
```

#### 🔄 **Check 3: Alte Sessions bereinigen**

```bash
python manage.py shell -c "
from mail_app.models import EmailAccount
EmailAccount.objects.all().delete()
print('Alte Email Accounts gelöscht')
"
```

#### 📞 **Check 4: Debug-Modus aktivieren**

1. **Terminal 1:** `python manage.py runserver`
2. **Terminal 2:** `tail -f logs/mail_app.log` (Live-Log anschauen)
3. **OAuth Flow starten** und Logs beobachten

---

## 🚨 HÄUFIGE PROBLEME UND LÖSUNGEN

### Problem: "Invalid redirect URI"
**Lösung:** Zoho Console -> App -> Redirect URLs -> Exakt `http://127.0.0.1:8000/mail/auth/callback/` hinzufügen

### Problem: "Scope not authorized"  
**Lösung:** Zoho Console -> App -> Scopes -> Alle Mail-Scopes aktivieren und App neu publishen

### Problem: "Client authentication failed"
**Lösung:** Client Secret in Zoho Console regenerieren und in Django aktualisieren

### Problem: Immer noch "Authorization code expired"
**Lösung:** 
1. Zoho App Status auf "Development" setzen (längere Code-Gültigkeit)
2. OAuth URL direkt im gleichen Browser-Tab öffnen (keine neuen Tabs)
3. Alle Browser-Erweiterungen deaktivieren

---

## ✅ ERFOLG TESTEN

Nach erfolgreichem OAuth:

```bash
python manage.py shell -c "
from mail_app.models import EmailAccount
accounts = EmailAccount.objects.all()
print(f'Email Accounts: {accounts.count()}')
for acc in accounts:
    print(f'- {acc.email_address}: {acc.status}')
"
```

**Erwartetes Ergebnis:**
```
Email Accounts: 1
- [deine-email@domain.de]: active
```