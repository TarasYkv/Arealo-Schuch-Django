# Automatisiertes Datenbank-Backup Setup (PythonAnywhere)

## Übersicht

Automatisches tägliches Datenbank-Backup mit 30-Tage-Rotation.

- **Backup-Frequenz:** Täglich um 03:00 Uhr UTC
- **Retention:** 30 Tage (automatisches Löschen älterer Backups)
- **Backup-Format:** MySQL `.sql` Dumps
- **Backup-Größe:** ~50-60 MB pro Backup
- **Speicherort:** `/home/TarasYuzkiv/Arealo-Schuch-Django/backups/`

## PythonAnywhere Scheduled Task einrichten

### Schritt 1: PythonAnywhere Dashboard öffnen

1. Gehe zu https://www.pythonanywhere.com/
2. Login mit Account `TarasYuzkiv`
3. Klicke auf **"Schedule"** Tab (oder https://www.pythonanywhere.com/user/TarasYuzkiv/schedule/)

### Schritt 2: Neuen Scheduled Task erstellen

Klicke auf **"Add new task"** und konfiguriere:

#### Task Details:
```
Description (optional):  Tägliches Datenbank-Backup mit 30-Tage-Rotation

Command:                 /home/TarasYuzkiv/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py daily_database_backup

Frequency:               Daily at [03:00] UTC
```

**Wichtig:** Verwende den **vollständigen Pfad** zum Python-Interpreter im Virtualenv!

### Schritt 3: Task speichern

Klicke auf **"Create"** um den Task zu speichern.

### Schritt 4: Verify (Optional)

Nach der Erstellung kannst du den Task manuell testen:

```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com
cd ~/Arealo-Schuch-Django
python manage.py daily_database_backup --dry-run
```

## Manuelle Verwendung

### Backup erstellen

```bash
# Standard Backup (30 Tage Retention)
python manage.py daily_database_backup

# Mit Custom Retention (z.B. 60 Tage)
python manage.py daily_database_backup --retention-days 60

# Dry-Run (keine Änderungen, nur Simulation)
python manage.py daily_database_backup --dry-run
```

### Backups auflisten

```bash
ls -lh backups/
```

### Backup manuell wiederherstellen

```bash
# Via SuperConfig Web-Interface:
https://www.workloom.de/superconfig/

# Oder via Kommandozeile:
mysql -h <host> -u <user> -p <database> < backups/auto_backup_YYYYMMDD_HHMMSS.sql
```

## Backup-Dateinamen

Automatische Backups haben das Format:
```
auto_backup_YYYYMMDD_HHMMSS.sql
```

Beispiele:
- `auto_backup_20251017_030000.sql` - Backup vom 17. Oktober 2025, 03:00 Uhr
- `auto_backup_20251018_030000.sql` - Backup vom 18. Oktober 2025, 03:00 Uhr

## Backup-Rotation

Das System löscht **automatisch** alle Backups, die älter als 30 Tage sind:

- **Tag 1-30:** Backups werden behalten
- **Tag 31+:** Backups werden automatisch gelöscht
- **Manuell erstellte Backups:** Werden NICHT automatisch gelöscht (nur `auto_backup_*` Dateien)

## Monitoring

### Logs prüfen

Nach jedem Scheduled Task Run kannst du die Logs auf PythonAnywhere einsehen:

1. Gehe zu https://www.pythonanywhere.com/user/TarasYuzkiv/schedule/
2. Klicke auf den Task
3. Unter "History" siehst du die letzten Runs und deren Output

### Backup-Größe überwachen

```bash
# Gesamtgröße aller Backups
du -sh backups/

# Einzelne Backup-Größen
ls -lh backups/ | grep auto_backup
```

### Email-Benachrichtigungen (Optional)

Du kannst das Command erweitern um bei Fehlern Emails zu senden:

```python
# In daily_database_backup.py
from django.core.mail import mail_admins

try:
    backup_file = self.create_backup()
except Exception as e:
    mail_admins(
        'Backup Failed',
        f'Datenbank-Backup fehlgeschlagen: {str(e)}'
    )
    raise
```

## Troubleshooting

### Problem: Task läuft nicht

**Lösung:** Prüfe, ob der Command manuell funktioniert:
```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com
cd ~/Arealo-Schuch-Django
python manage.py daily_database_backup
```

### Problem: "Command not found"

**Lösung:** Stelle sicher, dass der vollständige Pfad zum Python-Interpreter verwendet wird:
```bash
/home/TarasYuzkiv/arealo-venv/bin/python
```

### Problem: "Permission denied"

**Lösung:** Prüfe Berechtigungen des Backup-Verzeichnisses:
```bash
chmod 755 ~/Arealo-Schuch-Django/backups/
```

### Problem: Backup-Verzeichnis voll

**Lösung:** Reduziere die Retention-Zeit oder lösche alte manuelle Backups:
```bash
# Alte manuelle Backups löschen
find backups/ -name "database_backup_*.sql" -mtime +60 -delete
```

## Storage Management

PythonAnywhere hat Storage-Limits:

- **Free Account:** 512 MB
- **Hacker Account:** 1 GB
- **Web Developer Account:** Mehr

**Empfohlene Actions:**
1. Ältere manuelle Backups regelmäßig löschen
2. Backups auf lokalen Server oder Cloud herunterladen
3. Retention auf 14-21 Tage reduzieren bei Storage-Problemen

## Sicherheit

### Backup-Sicherheit

- Backups enthalten **sensitive Daten** (Passwörter, User-Daten, etc.)
- Stelle sicher, dass nur autorisierte Personen Zugriff haben
- PythonAnywhere Backups sind **nur für dich** zugänglich
- Bei Download: Verschlüsselte Übertragung (SCP/SFTP)

### Backup-Download

```bash
# Backups auf lokalen Rechner herunterladen
scp TarasYuzkiv@ssh.pythonanywhere.com:~/Arealo-Schuch-Django/backups/auto_backup_*.sql ~/local_backups/
```

## Weitere Informationen

- Django Management Commands: https://docs.djangoproject.com/en/stable/howto/custom-management-commands/
- PythonAnywhere Scheduled Tasks: https://help.pythonanywhere.com/pages/ScheduledTasks/
- MySQL Backup: https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html
