# Canva Integration - Installationsanleitung

Diese Anleitung erklärt, wie Sie die Canva-Integration einrichten, um Designs direkt aus Canva in den Bildeditor zu importieren.

## 🔧 Setup-Schritte

### 1. Canva Developer Account erstellen

1. Besuchen Sie [Canva for Developers](https://www.canva.com/developers/)
2. Melden Sie sich mit Ihrem Canva-Konto an
3. Gehen Sie zur [Developer Console](https://www.canva.com/developers/console)
4. Klicken Sie auf "Create new app"

### 2. Canva App konfigurieren

1. **App Name**: Geben Sie einen Namen für Ihre App ein (z.B. "Bildeditor Integration")
2. **App Description**: Beschreibung der Integration
3. **Redirect URIs**: Fügen Sie hinzu:
   ```
   https://ihre-domain.com/accounts/canva-oauth-callback/
   ```
   (Ersetzen Sie `ihre-domain.com` durch Ihre tatsächliche Domain)

4. **Scopes**: Wählen Sie folgende Berechtigungen:
   - `design:read` - Designs lesen
   - `asset:read` - Assets lesen
   - `folder:read` - Ordner lesen
   - `brand_template:read` - Brand Templates lesen

5. Speichern Sie die App-Konfiguration

### 3. API-Credentials erhalten

Nach der App-Erstellung erhalten Sie:
- **Client ID** - Öffentlicher Identifier Ihrer App
- **Client Secret** - Privater Schlüssel (geheim halten!)

## 🚀 Integration im Bildeditor

### 1. API-Einstellungen konfigurieren

1. Loggen Sie sich in den Bildeditor ein
2. Gehen Sie zu **"API Keys verwalten"** (über das Benutzermenü)
3. Scrollen Sie zum **"Canva Integration"** Bereich
4. Geben Sie Ihre **Client ID** und **Client Secret** ein
5. Optional: Konfigurieren Sie **Brand Template ID** und **Ordner ID**
6. Klicken Sie auf **"Canva-Einstellungen speichern"**

### 2. Canva-Konto verbinden

1. Nach dem Speichern der Credentials erscheint der Button **"Mit Canva verbinden"**
2. Klicken Sie darauf - Sie werden zu Canva weitergeleitet
3. Autorisieren Sie die App mit Ihrem Canva-Konto
4. Sie werden zurück zum Bildeditor geleitet
5. Bei Erfolg sehen Sie: **"Erfolgreich verbunden!"**

### 3. Designs importieren

1. Gehen Sie zum **Bildbearbeitung Dashboard**
2. Klicken Sie auf **"Canva Import"**
3. Durchsuchen Sie Ihre Canva-Designs
4. Klicken Sie bei gewünschten Designs auf **"Importieren"**
5. Geben Sie einen Projektnamen ein (optional)
6. Das Design wird als PNG heruntergeladen und als neues Projekt erstellt

## 🔒 Sicherheit

- **Client Secret**: Wird verschlüsselt in der Datenbank gespeichert
- **Access Tokens**: Werden automatisch erneuert
- **OAuth 2.0**: Sichere Autorisierung ohne Passwort-Weitergabe
- **State-Parameter**: Schutz vor CSRF-Angriffen

## 🛠️ Troubleshooting

### "Redirect URI mismatch"
- Stellen Sie sicher, dass die Redirect URI in Canva exakt mit Ihrer Domain übereinstimmt
- Format: `https://ihre-domain.com/accounts/canva-oauth-callback/`
- Achten Sie auf `https://` und den abschließenden `/`

### "Invalid credentials"
- Prüfen Sie Client ID und Secret auf Tippfehler
- Stellen Sie sicher, dass die App in Canva aktiv ist

### "Token expired"
- Tokens werden automatisch erneuert
- Bei anhaltenden Problemen: Verbindung trennen und neu verbinden

### "No designs found"
- Stellen Sie sicher, dass Designs in Ihrem Canva-Konto vorhanden sind
- Prüfen Sie die Ordner-ID Einstellung (leer = alle Ordner)

## 📋 Funktionsumfang

### ✅ Unterstützte Features
- **Design-Import**: PNG-Export mit hoher Qualität
- **OAuth 2.0**: Sichere Autorisierung
- **Automatisches Token-Refresh**: Nahtlose Nutzung
- **Pagination**: Laden großer Design-Sammlungen
- **Thumbnail-Vorschau**: Visuelle Design-Auswahl
- **Projekt-Integration**: Designs werden als editierbare Projekte importiert

### 🔄 Import-Workflow
1. Design auswählen → 2. Projektname eingeben → 3. Import starten → 4. PNG-Download → 5. Projekt erstellt

## 🆘 Support

Bei Problemen:
1. Prüfen Sie die Canva Developer Console auf App-Status
2. Kontrollieren Sie die Redirect URI Konfiguration
3. Testen Sie die Verbindung über "API-Einstellungen"
4. Bei anhaltenden Problemen: Neu-Autorisierung durchführen

## 📈 Erweiterte Konfiguration

### Brand Templates
- Setzen Sie eine **Brand Template ID** für konsistentes Branding
- Designs aus diesem Template werden bevorzugt angezeigt

### Ordner-Filter
- Konfigurieren Sie eine **Ordner ID** um nur Designs aus bestimmten Ordnern zu laden
- Leer = alle verfügbaren Designs

### Rate Limits
- Canva API hat Rate Limits (100 Requests/Minute)
- Bei vielen Designs: Verwenden Sie Pagination

---

**Hinweis**: Diese Integration nutzt die offizielle Canva Connect API und entspricht allen Sicherheits- und Datenschutzrichtlinien.