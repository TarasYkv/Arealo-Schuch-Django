# PythonAnywhere Scheduled Task - Datenbank-Backup Fix

## Problem
Der Scheduled Task für das tägliche Datenbank-Backup schlägt mit folgendem Fehler fehl:
```
bash: line 1: /home/TarasYuzkiv/arealo-venv/bin/python: No such file or directory
```

## Ursache
Der Pfad zum Python-Interpreter im virtualenv ist falsch. PythonAnywhere verwendet standardmäßig `~/.virtualenvs/` für virtuelle Umgebungen, nicht das Home-Verzeichnis direkt.

## Lösung

### 1. Korrekter Python-Pfad
**Falsch:** `/home/TarasYuzkiv/arealo-venv/bin/python`
**Richtig:** `/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python`

### 2. Korrigierter Scheduled Task Command

Gehe zu PythonAnywhere Dashboard → "Tasks" Tab und ändere den Command zu:

```bash
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py backup_database --output-dir /home/TarasYuzkiv/backups --keep-days 7 --method mysqldump
```

### 3. Alternative Commands je nach Bedarf

#### Option A: MySQL-Dump (schneller, empfohlen)
```bash
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py backup_database --method mysqldump
```

#### Option B: Django Dumpdata (portabler, aber langsamer)
```bash
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py backup_database --method dumpdata
```

#### Option C: Nur spezielle Apps sichern
```bash
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py dumpdata accounts core pricing loomconnect --indent 2 --output /home/TarasYuzkiv/backups/workloom_$(date +\%Y\%m\%d).json
```

### 4. Backup-Verzeichnis erstellen (einmalig via SSH)

```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com "mkdir -p ~/backups"
```

## Features des neuen Backup-Commands

Der neue `backup_database` Management Command bietet:

- **Automatische Komprimierung**: Backups werden mit gzip komprimiert
- **Alte Backups löschen**: Standardmäßig werden Backups älter als 7 Tage gelöscht
- **Zwei Methoden**:
  - `mysqldump`: Schneller, aber MySQL-spezifisch
  - `dumpdata`: Langsamer, aber Django-nativ und portabel
- **Fehlerbehandlung**: Saubere Fehlermeldungen bei Problemen

## Verifizierung

Nach der Änderung des Scheduled Tasks:

1. **Manueller Test via SSH:**
```bash
ssh TarasYuzkiv@ssh.pythonanywhere.com
cd ~/Arealo-Schuch-Django
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python manage.py backup_database --output-dir ~/backups
ls -la ~/backups/
```

2. **Prüfe Task-Logs:**
   - Gehe zu PythonAnywhere Dashboard → "Tasks" Tab
   - Klicke auf "Log" beim Backup-Task
   - Nach dem nächsten Lauf sollte "✓ Backup erfolgreich erstellt" erscheinen

## Restore-Prozess (bei Bedarf)

### MySQL-Dump wiederherstellen:
```bash
# Via SSH auf PythonAnywhere
cd ~/Arealo-Schuch-Django
gunzip -c ~/backups/workloom_backup_20241022_030000.sql.gz | mysql -u TarasYuzkiv -p'PASSWORT' TarasYuzkiv\$workloom
```

### Django Dumpdata wiederherstellen:
```bash
# Via SSH auf PythonAnywhere
cd ~/Arealo-Schuch-Django
gunzip -c ~/backups/workloom_backup_20241022_030000.json.gz | python manage.py loaddata -
```

## Wichtige Hinweise

1. **Speicherplatz**: PythonAnywhere Free Account hat begrenzten Speicher. 7 Tage Backups sollten passen.
2. **Zeitzone**: Scheduled Tasks laufen in UTC. 03:00 UTC = 05:00 MESZ / 04:00 MEZ
3. **Datenbank-Passwort**: Wird automatisch aus Django Settings gelesen

## Andere funktionierende Tasks als Referenz

```bash
# Email-Benachrichtigungen (funktioniert)
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py send_chat_email_notifications

# Beliebiger anderer Command
/home/TarasYuzkiv/.virtualenvs/arealo-venv/bin/python /home/TarasYuzkiv/Arealo-Schuch-Django/manage.py [COMMAND_NAME] [OPTIONEN]
```

## Deployment des neuen Backup-Commands

Der neue `backup_database.py` Command muss auf den Server deployed werden:

```bash
# Lokal
git add core/management/commands/backup_database.py
git commit -m "Feature: Datenbank-Backup Management Command für PythonAnywhere"
git push origin master

# Auf PythonAnywhere (via SSH oder später)
cd ~/Arealo-Schuch-Django
git pull origin master
```