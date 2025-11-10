# Shopify Webhook Setup für Fotogravur Order Processing

## Übersicht

Dieser Webhook wird ausgelöst, wenn eine Bestellung in Shopify abgeschlossen wird. Er:
1. Aktualisiert das FotogravurImage mit der Shopify Order-ID
2. Benennt das Bild um von `<unique_id>.png` zu `<order_id>.png`
3. Speichert alle Bestellinformationen für spätere Referenz

## Webhook-Registrierung in Shopify

### 1. In Shopify Admin navigieren

1. Gehe zu **Settings** → **Notifications**
2. Scrolle runter zu **Webhooks**
3. Klicke auf **Create webhook**

### 2. Webhook konfigurieren

Fülle die Felder wie folgt aus:

- **Event**: `Order creation` (oder `orders/create`)
- **Format**: `JSON`
- **URL**: `https://www.workloom.de/shopify-uploads/api/webhook/order-created/`
- **Webhook API version**: Latest (empfohlen: `2024-01` oder neuer)

### 3. Webhook Secret (optional, aber empfohlen)

Für zusätzliche Sicherheit solltest du ein Webhook Secret verwenden:

1. Kopiere das **Webhook Secret** aus den Shopify Webhook-Einstellungen
2. Füge es als Environment Variable auf dem Server hinzu:
   ```bash
   export SHOPIFY_WEBHOOK_SECRET="dein_webhook_secret_hier"
   ```
3. Oder füge es zur `.env` Datei hinzu:
   ```
   SHOPIFY_WEBHOOK_SECRET=dein_webhook_secret_hier
   ```

**Wichtig**: Ohne das Secret wird die HMAC-Verifizierung übersprungen (nur für Development OK).

## Webhook-Endpoint Details

### URL
```
POST https://www.workloom.de/shopify-uploads/api/webhook/order-created/
```

### Was der Webhook macht

1. **Empfängt Order Data** von Shopify im Format:
   ```json
   {
     "id": 5678901234,
     "order_number": 1234,
     "line_items": [
       {
         "properties": [
           {"name": "Bild ID", "value": "fg_1234567890_abc123"}
         ]
       }
     ]
   }
   ```

2. **Sucht nach Fotogravur-Bildern** in den Line Item Properties (Property-Name: `"Bild ID"`)

3. **Aktualisiert die Datenbank**:
   - Findet FotogravurImage mit der `unique_id` aus dem Property
   - Setzt `shopify_order_id` auf die Order-ID
   - Benennt Bilddatei um: `<unique_id>.png` → `<order_id>.png`

4. **Gibt Response zurück**:
   ```json
   {
     "success": true,
     "order_id": "5678901234",
     "order_number": 1234,
     "updated_images": [
       {
         "unique_id": "fg_1234567890_abc123",
         "order_id": "5678901234",
         "new_filename": "5678901234.png"
       }
     ],
     "count": 1
   }
   ```

## Testing

### Manueller Test mit curl

```bash
curl -X POST https://www.workloom.de/shopify-uploads/api/webhook/order-created/ \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test_order_123",
    "order_number": 9999,
    "line_items": [
      {
        "properties": [
          {"name": "Bild ID", "value": "fg_existierende_unique_id"}
        ]
      }
    ]
  }'
```

**Hinweis**: Ersetze `fg_existierende_unique_id` mit einer tatsächlichen unique_id aus deiner Datenbank.

### Shopify Test-Bestellung

1. Erstelle eine Test-Bestellung in Shopify mit einem Fotogravur-Produkt
2. Prüfe in den Shopify Webhook-Logs, ob der Webhook erfolgreich aufgerufen wurde
3. Überprüfe in der Django Admin (`/shopify-uploads/`) ob:
   - Die `shopify_order_id` gesetzt wurde
   - Das Bild umbenannt wurde

## Monitoring & Debugging

### Shopify Webhook-Logs

- Gehe zu **Settings** → **Notifications** → **Webhooks**
- Klicke auf deinen Webhook
- Scrolle zu **Recent deliveries** um Status und Responses zu sehen

### Django Logs

Der Webhook loggt Fehler automatisch. Bei Problemen:

```bash
# Logs auf dem Server anschauen
tail -f /var/log/django/error.log
# oder
tail -f /var/log/gunicorn/error.log
```

### Häufige Fehler

1. **401 Invalid HMAC signature**: Webhook Secret stimmt nicht überein
2. **404**: URL falsch konfiguriert
3. **500**: Server-Fehler - siehe Django Logs

## Datenbank-Queries

Nach erfolgreicher Webhook-Verarbeitung kannst du Bestellungen abfragen:

```python
from shopify_uploads.models import FotogravurImage

# Alle Bilder mit Order-ID
images_with_orders = FotogravurImage.objects.exclude(shopify_order_id__isnull=True)

# Bestimmte Order
order_images = FotogravurImage.objects.filter(shopify_order_id='5678901234')
```

## Deployment

Nach dem Deployment:

1. Server neustarten (damit neue Code-Änderungen aktiv werden)
   ```bash
   systemctl restart gunicorn
   ```

2. Webhook in Shopify registrieren (siehe oben)

3. Test-Bestellung durchführen

4. Logs überprüfen
