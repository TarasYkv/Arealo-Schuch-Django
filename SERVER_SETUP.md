# Server Setup - Abhängigkeiten für PDF-Export

## Problem
Fehlende `matplotlib` Bibliothek auf dem Server führt zu dem Fehler:
```
No module named 'matplotlib'
```

## Lösung
### 1. matplotlib installieren (Server-seitig)

Auf dem Server ausführen:

```bash
# Aktiviere die virtuelle Umgebung
source /path/to/your/venv/bin/activate

# Installiere matplotlib
pip install matplotlib

# Oder falls pip3 verwendet wird:
pip3 install matplotlib
```

### 2. Abhängigkeiten für matplotlib
Möglicherweise sind zusätzliche System-Pakete erforderlich:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-tk python3-dev

# CentOS/RHEL
sudo yum install python3-tkinter python3-devel

# Oder mit dnf:
sudo dnf install python3-tkinter python3-devel
```

### 3. Webserver neustarten
Nach der Installation den Webserver neu starten:

```bash
# Für Django development server
# Kein Neustart nötig

# Für uWSGI
sudo systemctl restart uwsgi

# Für Gunicorn
sudo systemctl restart gunicorn

# Für Apache/Nginx + uWSGI/Gunicorn
sudo systemctl restart nginx
sudo systemctl restart uwsgi
```

## Fallback-Verhalten
Falls `matplotlib` nicht installiert werden kann, zeigt das System automatisch:
- Hinweise statt Charts in PDFs
- Vollständige numerische Daten in Tabellen
- Funktionsfähige PDFs ohne Diagramme

## Überprüfung der Installation
```bash
python -c "import matplotlib; print('matplotlib version:', matplotlib.__version__)"
```

Bei erfolgreicher Installation sollte die Versionsnummer angezeigt werden.