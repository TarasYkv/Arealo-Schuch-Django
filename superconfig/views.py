import os
import json
import shutil
from datetime import datetime
from .zoho_oauth import ZohoOAuthHandler
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.core.mail import send_mail, EmailMessage
import sqlite3
import smtplib
import ssl
import requests
from .models import EmailConfiguration, SuperuserEmailShare, GlobalMessage


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def superconfig_dashboard(request):
    """SuperConfig Dashboard - only for superusers"""
    return render(request, 'superconfig/dashboard.html')


@login_required
@user_passes_test(is_superuser)
def database_backup(request):
    """Create database backup"""
    if request.method == 'POST':
        try:
            # Create backup directory if it doesn't exist
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'database_backup_{timestamp}.sqlite3'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Get current database path
            db_path = settings.DATABASES['default']['NAME']
            
            # Create backup
            shutil.copy2(db_path, backup_path)
            
            messages.success(request, f'Database backup created successfully: {backup_filename}')
            return JsonResponse({
                'success': True, 
                'message': f'Backup erstellt: {backup_filename}',
                'filename': backup_filename
            })
            
        except Exception as e:
            messages.error(request, f'Backup failed: {str(e)}')
            return JsonResponse({
                'success': False, 
                'message': f'Backup fehlgeschlagen: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def database_restore(request):
    """Restore database from backup file upload"""
    if request.method == 'POST':
        backup_file = request.FILES.get('backup_file')
        
        if not backup_file:
            return JsonResponse({
                'success': False, 
                'message': 'Keine Backup-Datei ausgewählt'
            })
        
        try:
            # Validate file extension
            if not backup_file.name.endswith('.sqlite3'):
                return JsonResponse({
                    'success': False, 
                    'message': 'Ungültiges Dateiformat. Nur .sqlite3 Dateien sind erlaubt.'
                })
            
            # Get current database path
            db_path = settings.DATABASES['default']['NAME']
            
            # Create backup of current database before restore
            current_backup_path = db_path + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            shutil.copy2(db_path, current_backup_path)
            
            # Save uploaded file temporarily
            temp_path = os.path.join(settings.BASE_DIR, 'temp_restore.sqlite3')
            with open(temp_path, 'wb+') as destination:
                for chunk in backup_file.chunks():
                    destination.write(chunk)
            
            # Validate the backup file by trying to open it
            try:
                conn = sqlite3.connect(temp_path)
                conn.close()
            except sqlite3.Error:
                os.remove(temp_path)
                return JsonResponse({
                    'success': False, 
                    'message': 'Ungültige SQLite-Datei'
                })
            
            # Replace current database with backup
            shutil.move(temp_path, db_path)
            
            return JsonResponse({
                'success': True, 
                'message': f'Database erfolgreich wiederhergestellt. Aktuelle DB wurde gesichert als: {os.path.basename(current_backup_path)}'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Wiederherstellung fehlgeschlagen: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def database_restore_from_server(request):
    """Restore database from server backup"""
    if request.method == 'POST':
        backup_filename = request.POST.get('backup_filename')
        
        if not backup_filename:
            return JsonResponse({
                'success': False, 
                'message': 'Keine Backup-Datei ausgewählt'
            })
        
        try:
            # Security check: ensure filename is safe
            if '..' in backup_filename or '/' in backup_filename or '\\' in backup_filename:
                return JsonResponse({
                    'success': False, 
                    'message': 'Ungültiger Dateiname'
                })
            
            # Check if backup file exists
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            backup_path = os.path.join(backup_dir, backup_filename)
            
            if not os.path.exists(backup_path) or not backup_filename.endswith('.sqlite3'):
                return JsonResponse({
                    'success': False, 
                    'message': 'Backup-Datei nicht gefunden'
                })
            
            # Get current database path
            db_path = settings.DATABASES['default']['NAME']
            
            # Create backup of current database before restore
            current_backup_path = db_path + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            shutil.copy2(db_path, current_backup_path)
            
            # Validate the backup file by trying to open it
            try:
                conn = sqlite3.connect(backup_path)
                conn.close()
            except sqlite3.Error:
                return JsonResponse({
                    'success': False, 
                    'message': 'Ungültige SQLite-Datei'
                })
            
            # Replace current database with backup
            shutil.copy2(backup_path, db_path)
            
            return JsonResponse({
                'success': True, 
                'message': f'Database erfolgreich wiederhergestellt von {backup_filename}. Aktuelle DB wurde gesichert als: {os.path.basename(current_backup_path)}'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Wiederherstellung fehlgeschlagen: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def list_backups(request):
    """List available database backups"""
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        backups = []
        
        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                if filename.endswith('.sqlite3'):
                    file_path = os.path.join(backup_dir, filename)
                    file_stat = os.stat(file_path)
                    backups.append({
                        'filename': filename,
                        'size': round(file_stat.st_size / (1024 * 1024), 2),  # Size in MB
                        'created': datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return JsonResponse({
            'success': True, 
            'backups': backups
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Fehler beim Laden der Backups: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
def download_backup(request, filename):
    """Download a specific backup file"""
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Security check: ensure filename is safe
        if '..' in filename or '/' in filename or '\\' in filename:
            return HttpResponse('Invalid filename', status=400)
        
        if not os.path.exists(file_path) or not filename.endswith('.sqlite3'):
            return HttpResponse('File not found', status=404)
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
    except Exception as e:
        return HttpResponse(f'Error downloading file: {str(e)}', status=500)


@login_required
@user_passes_test(is_superuser)
def database_info(request):
    """Get database information and statistics"""
    try:
        db_path = settings.DATABASES['default']['NAME']
        db_size = os.path.getsize(db_path) / (1024 * 1024)  # Size in MB
        
        # Get table information
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name, 
                       (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=t.name) as table_count
                FROM sqlite_master t 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables_info = []
            for table_name, _ in cursor.fetchall():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                tables_info.append({
                    'name': table_name,
                    'rows': row_count
                })
        
        return JsonResponse({
            'success': True,
            'database_info': {
                'size_mb': round(db_size, 2),
                'path': str(db_path),  # Convert PosixPath to string
                'tables': tables_info
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler beim Laden der DB-Informationen: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
def email_service_status(request):
    """Get email service status and configuration"""
    try:
        # Get active database configuration
        db_config = EmailConfiguration.get_active_config()
        
        # Get current settings (from settings.py or database)
        if db_config:
            email_config = {
                'source': 'database',
                'backend': db_config.get_django_email_settings()['EMAIL_BACKEND'],
                'host': db_config.smtp_host,
                'port': db_config.smtp_port,
                'use_tls': db_config.smtp_use_tls,
                'use_ssl': db_config.smtp_use_ssl,
                'host_user': db_config.email_host_user,
                'default_from': db_config.default_from_email,
                'password_configured': bool(db_config.email_host_password),
                'masked_password': db_config.masked_password,
                'backend_type': db_config.backend_type,
                'config_id': db_config.id,
                'last_updated': db_config.updated_at.isoformat() if db_config.updated_at else None,
            }
            
            # Use database config for SMTP test
            smtp_status = check_smtp_connection_with_config(db_config)
            
            # Get Zoho config from database
            zoho_status = {
                'client_id_configured': bool(db_config.zoho_client_id),
                'client_secret_configured': bool(db_config.zoho_client_secret),
                'redirect_uri': db_config.zoho_redirect_uri or '',
                'base_url': 'https://mail.zoho.eu/api/',
            }
        else:
            # Fallback to settings.py
            email_config = {
                'source': 'settings.py',
                'backend': settings.EMAIL_BACKEND,
                'host': settings.EMAIL_HOST,
                'port': settings.EMAIL_PORT,
                'use_tls': settings.EMAIL_USE_TLS,
                'use_ssl': getattr(settings, 'EMAIL_USE_SSL', False),
                'host_user': settings.EMAIL_HOST_USER,
                'default_from': settings.DEFAULT_FROM_EMAIL,
                'password_configured': bool(settings.EMAIL_HOST_PASSWORD),
                'masked_password': '●●●●●●●●●●●●' if settings.EMAIL_HOST_PASSWORD else 'Nicht gesetzt',
                'backend_type': 'smtp',
                'config_id': None,
                'last_updated': None,
            }
            
            smtp_status = check_smtp_connection()
            
            # Get Zoho configuration from settings
            zoho_config = getattr(settings, 'ZOHO_MAIL_CONFIG', {})
            zoho_status = {
                'client_id_configured': bool(zoho_config.get('CLIENT_ID')),
                'client_secret_configured': bool(zoho_config.get('CLIENT_SECRET')),
                'redirect_uri': zoho_config.get('REDIRECT_URI', ''),
                'base_url': zoho_config.get('BASE_URL', ''),
            }
        
        # Get shared superuser emails
        shared_emails = list(SuperuserEmailShare.objects.filter(is_active=True).values(
            'email_address', 'display_name', 'description', 'created_at'
        ))
        
        # Check recent email activity
        email_activity = get_recent_email_activity()
        
        # Include raw email config for form population
        if db_config:
            raw_email_config = {
                'smtp_host': db_config.smtp_host,
                'smtp_port': db_config.smtp_port,
                'smtp_use_tls': db_config.smtp_use_tls,
                'smtp_use_ssl': db_config.smtp_use_ssl,
                'email_host_user': db_config.email_host_user,
                'email_host_password': bool(db_config.email_host_password),  # Don't send actual password
                'default_from_email': db_config.default_from_email,
                'backend_type': db_config.backend_type,
                'zoho_client_id': bool(db_config.zoho_client_id),
                'zoho_client_secret': bool(db_config.zoho_client_secret),
                'zoho_redirect_uri': db_config.zoho_redirect_uri,
            }
        else:
            raw_email_config = None

        return JsonResponse({
            'success': True,
            'email_service': {
                'smtp_config': email_config,
                'zoho_config': zoho_status,
                'smtp_connection': smtp_status,
                'recent_activity': email_activity,
                'shared_emails': shared_emails,
                'has_db_config': bool(db_config),
            },
            'email_config': raw_email_config,
            'shared_emails': shared_emails
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler beim Laden der Email-Service-Informationen: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
def test_email_service(request):
    """Test email sending functionality"""
    if request.method == 'POST':
        test_email = request.POST.get('test_email', 'test@example.com')
        test_config = request.POST.get('test_config', False)
        
        try:
            if test_config == 'true':
                # Test with custom configuration from form
                smtp_host = request.POST.get('smtp_host')
                smtp_port = int(request.POST.get('smtp_port', 587))
                smtp_use_tls = request.POST.get('smtp_use_tls') == 'true'
                smtp_use_ssl = request.POST.get('smtp_use_ssl') == 'true'
                email_host_user = request.POST.get('email_host_user')
                email_host_password = request.POST.get('email_host_password')
                backend_type = request.POST.get('backend_type', 'smtp')
                
                # Test SMTP connection with custom config
                if backend_type == 'smtp':
                    import smtplib
                    from email.mime.text import MIMEText
                    
                    # Test connection
                    try:
                        if smtp_use_ssl:
                            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
                        else:
                            server = smtplib.SMTP(smtp_host, smtp_port)
                            if smtp_use_tls:
                                server.starttls()
                        
                        server.login(email_host_user, email_host_password)
                        server.quit()
                        
                        return JsonResponse({
                            'success': True,
                            'message': f'SMTP-Verbindung zu {smtp_host}:{smtp_port} erfolgreich getestet'
                        })
                    except Exception as e:
                        error_msg = str(e)
                        
                        # Enhanced Zoho-specific error guidance
                        if 'Authentication' in error_msg or '535' in error_msg:
                            guidance = """🔐 Zoho Authentication Failed - Mögliche Ursachen:
                            
                            ✅ 1. IMAP/SMTP/POP aktivieren
                               → Zoho Mail → Einstellungen → Konten → Ihr Konto → IMAP/POP/SMTP: AKTIVIEREN
                            
                            ✅ 2. "Weniger sichere Apps" aktivieren  
                               → Zoho Mail → Einstellungen → Sicherheit → Weniger sichere Apps: EIN
                               → Oder: Anwendungsspezifische Passwörter verwenden
                            
                            ✅ 3. Korrekte Zoho-Server verwenden
                               → Europa: smtp.zoho.eu:587 (TLS)
                               → Alternative: smtp.zoho.com:587
                            
                            ✅ 4. Email-Adresse und Server-Region prüfen
                               → @zoho.eu Adressen → smtp.zoho.eu
                               → @zoho.com Adressen → smtp.zoho.com
                            
                            ℹ️ Tipp: Prüfen Sie Ihr Zoho-Kontotyp (Free/Paid)"""
                            
                            return JsonResponse({
                                'success': False,
                                'message': f'❌ SMTP Authentication Failed (535)',
                                'guidance': guidance,
                                'error_type': '535_Authentication_Failed'
                            })
                        else:
                            return JsonResponse({
                                'success': False,
                                'message': f'SMTP-Test fehlgeschlagen: {error_msg}'
                            })
                else:
                    return JsonResponse({
                        'success': True,
                        'message': f'Backend-Typ "{backend_type}" konfiguriert (kein SMTP-Test erforderlich)'
                    })
            else:
                # Standard email test using current configuration
                subject = 'SuperConfig Email Test'
                message = f'''
                Dies ist eine Test-Email von SuperConfig.
                
                Gesendet am: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                Von: {settings.DEFAULT_FROM_EMAIL}
                Backend: {settings.EMAIL_BACKEND}
                
                Wenn Sie diese Email erhalten, funktioniert der Email-Service korrekt.
                '''
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[test_email],
                    fail_silently=False,
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Test-Email erfolgreich an {test_email} gesendet'
                })
            
        except Exception as e:
            error_msg = str(e)
            
            # Enhanced error guidance for general email test
            if 'Authentication' in error_msg or '535' in error_msg:
                guidance = """🔐 Zoho Authentication Problem mit normalem Passwort!
                
                CHECKLISTE - Zoho Konto-Einstellungen:
                
                1. ✅ IMAP/SMTP aktivieren
                   → Zoho Mail → Einstellungen → Konten → [Ihr Konto] → IMAP/POP/SMTP aktivieren
                
                2. ✅ "Weniger sichere Apps" zulassen
                   → Zoho Mail → Einstellungen → Sicherheit → Weniger sichere Apps: EIN
                   → (Für Login mit normalem Passwort erforderlich)
                
                3. ✅ Zoho-Server und Email prüfen
                   → @zoho.eu Email = smtp.zoho.eu verwenden
                   → @zoho.com Email = smtp.zoho.com verwenden
                
                4. ✅ Kontotyp prüfen
                   → Free-Konten haben manchmal andere SMTP-Limits"""
                
                return JsonResponse({
                    'success': False,
                    'message': f'❌ Authentication Failed (535) - Zoho Konto-Einstellungen prüfen!',
                    'guidance': guidance,
                    'zoho_help_url': 'https://www.zoho.eu/mail/help/adminconsole/two-factor-authentication.html#alink-generatepassword'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Email-Test fehlgeschlagen: {error_msg}'
                })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def check_smtp_connection():
    """Check SMTP server connection using settings.py config"""
    try:
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            return {
                'status': 'console',
                'message': 'Console Backend aktiv (kein SMTP)',
                'connected': False
            }
        
        # Get SMTP settings from database config if available
        db_config = EmailConfiguration.get_active_config()
        
        if db_config:
            smtp_host = db_config.smtp_host
            smtp_port = db_config.smtp_port
            use_tls = db_config.smtp_use_tls
            use_ssl = db_config.smtp_use_ssl
            username = db_config.email_host_user
            password = db_config.email_host_password
        else:
            # Fallback to Django settings
            smtp_host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
            smtp_port = getattr(settings, 'EMAIL_PORT', 587)
            use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
            use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
            username = getattr(settings, 'EMAIL_HOST_USER', '')
            password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        
        # First, try to resolve the hostname
        import socket
        try:
            socket.gethostbyname(smtp_host)
        except socket.gaierror as dns_error:
            return {
                'status': 'dns_error',
                'message': f'DNS-Auflösung fehlgeschlagen für {smtp_host}: {str(dns_error)}',
                'connected': False,
                'diagnostics': {
                    'dns_resolution': False,
                    'suggested_hosts': get_alternative_smtp_hosts(),
                    'error_details': str(dns_error)
                }
            }
        
        # Try to connect to SMTP server
        import smtplib
        import ssl
        
        try:
            if use_ssl:
                # Use SSL connection
                with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                    if username and password:
                        server.login(username, password)
                    return {
                        'status': 'connected',
                        'message': f'SMTP SSL-Verbindung zu {smtp_host}:{smtp_port} erfolgreich',
                        'connected': True
                    }
            else:
                # Use TLS or plain connection
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    if use_tls:
                        server.starttls()
                    if username and password:
                        server.login(username, password)
                    return {
                        'status': 'connected',
                        'message': f'SMTP-Verbindung zu {smtp_host}:{smtp_port} erfolgreich',
                        'connected': True
                    }
        except smtplib.SMTPAuthenticationError as auth_error:
            return {
                'status': 'auth_error',
                'message': f'SMTP-Authentifizierung fehlgeschlagen: {str(auth_error)}',
                'connected': False,
                'diagnostics': {
                    'authentication': False,
                    'suggestions': [
                        'Überprüfen Sie Benutzername und Passwort',
                        'Verwenden Sie App-Passwörter bei Gmail',
                        'Aktivieren Sie "Weniger sichere Apps" falls erforderlich'
                    ]
                }
            }
        except smtplib.SMTPConnectError as connect_error:
            return {
                'status': 'connection_error',
                'message': f'SMTP-Verbindung fehlgeschlagen: {str(connect_error)}',
                'connected': False,
                'diagnostics': {
                    'connection': False,
                    'suggestions': get_connection_troubleshooting_tips(smtp_host, smtp_port)
                }
            }
        except Exception as smtp_error:
            return {
                'status': 'smtp_error',
                'message': f'SMTP-Fehler: {str(smtp_error)}',
                'connected': False,
                'diagnostics': {
                    'error_type': type(smtp_error).__name__,
                    'suggestions': ['Prüfen Sie die SMTP-Konfiguration', 'Versuchen Sie einen anderen SMTP-Server']
                }
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Unbekannter Fehler: {str(e)}',
            'connected': False
        }


def get_alternative_smtp_hosts():
    """Get Zoho-specific SMTP hosts to suggest"""
    return [
        {'name': 'Zoho Mail Europe', 'host': 'smtp.zoho.eu', 'port': 587, 'tls': True, 'recommended': True},
        {'name': 'Zoho Mail EU', 'host': 'smtp.zohomaileu.com', 'port': 587, 'tls': True, 'recommended': True},
        {'name': 'Zoho Mail US', 'host': 'smtp.zoho.com', 'port': 587, 'tls': True, 'recommended': False},
        {'name': 'Zoho Mail India', 'host': 'smtp.zoho.in', 'port': 587, 'tls': True, 'recommended': False},
    ]


def get_connection_troubleshooting_tips(smtp_host, smtp_port):
    """Get specific troubleshooting tips based on SMTP host and port"""
    tips = [
        'Überprüfen Sie Ihre Internetverbindung',
        'Prüfen Sie, ob Port {port} durch eine Firewall blockiert wird'.format(port=smtp_port),
    ]
    
    if 'gmail' in smtp_host.lower():
        tips.extend([
            'Verwenden Sie App-Passwörter anstatt Ihr Gmail-Passwort',
            'Aktivieren Sie 2-Faktor-Authentifizierung und generieren Sie ein App-Passwort',
            'Versuchen Sie Port 465 mit SSL anstatt 587 mit TLS'
        ])
    elif 'outlook' in smtp_host.lower() or 'hotmail' in smtp_host.lower():
        tips.extend([
            'Stellen Sie sicher, dass SMTP-Authentifizierung aktiviert ist',
            'Verwenden Sie Ihre vollständige E-Mail-Adresse als Benutzername'
        ])
    elif 'zoho' in smtp_host.lower():
        tips.extend([
            'Überprüfen Sie die korrekte Zoho-Region (zoho.eu, zoho.com, etc.)',
            'Aktivieren Sie IMAP/SMTP in Ihren Zoho Mail-Einstellungen'
        ])
    
    return tips


def check_dns_connectivity():
    """Check DNS connectivity for Zoho SMTP servers"""
    import socket
    from django.conf import settings
    
    # Get configured SMTP host
    configured_host = getattr(settings, 'EMAIL_HOST', None)
    
    # Zoho-spezifische Test-Hosts
    test_hosts = []
    if configured_host:
        test_hosts.append(configured_host)
    
    # DNS-Server für Basis-Konnektivität
    test_hosts.extend(['8.8.8.8', '1.1.1.1'])
    
    # Zoho SMTP Server (alle Regionen)
    test_hosts.extend([
        'smtp.zoho.eu',           # Europe (empfohlen)
        'smtp.zohomaileu.com',    # EU Alternative
        'smtp.zoho.com',          # US
        'smtp.zoho.in'            # India
    ])
    
    results = {}
    
    for host in test_hosts:
        try:
            socket.gethostbyname(host)
            results[host] = True
        except socket.gaierror:
            results[host] = False
    
    return results


@login_required
@user_passes_test(is_superuser)
def auto_configure_email_fallback(request):
    """Automatically configure email fallback for DNS issues"""
    from .models import EmailConfiguration
    from django.conf import settings
    
    try:
        # Get the most recent working configuration
        config = EmailConfiguration.objects.filter(is_active=True).first()
        
        if not config:
            # Create new configuration with Zoho fallback
            config = EmailConfiguration.objects.create(
                email_host_user='kontakt@workloom.de',
                email_host_password='',  # User needs to set this
                default_from_email='kontakt@workloom.de',
                smtp_host='smtp.zoho.eu',  # Start with working server
                smtp_port=587,
                smtp_use_tls=True,
                smtp_use_ssl=False,
                is_active=True,
                backend_type='smtp',
                created_by=request.user
            )
            created = True
        else:
            created = False
        
        # Test connection and auto-configure
        result = config.test_connection()
        
        # Update Django settings with working configuration
        if result['success']:
            settings.EMAIL_HOST = config.smtp_host
            settings.EMAIL_PORT = config.smtp_port
            settings.EMAIL_USE_TLS = config.smtp_use_tls
            settings.EMAIL_USE_SSL = config.smtp_use_ssl
            settings.EMAIL_HOST_USER = config.email_host_user
            settings.DEFAULT_FROM_EMAIL = config.default_from_email
            
            message = f"✅ Auto-Konfiguration erfolgreich! Django Settings aktualisiert auf {config.smtp_host}:${config.smtp_port}"
            if result.get('fallback_used'):
                message += f" (Fallback von {result.get('original_host', 'unbekannt')})"
        else:
            message = result['message']
        
        return JsonResponse({
            'success': result['success'],
            'message': message,
            'fallback_used': result.get('fallback_used', False),
            'config_created': created,
            'current_server': f"{config.smtp_host}:{config.smtp_port}",
            'config_id': config.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler bei Auto-Konfiguration: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
def email_network_diagnostics(request):
    """Perform comprehensive email network diagnostics"""
    diagnostics = {
        'dns_connectivity': check_dns_connectivity(),
        'smtp_connection': check_smtp_connection(),
        'suggested_alternatives': get_alternative_smtp_hosts(),
    }
    
    return JsonResponse({
        'success': True,
        'diagnostics': diagnostics,
        'timestamp': datetime.now().isoformat()
    })


@login_required
@user_passes_test(is_superuser)
def setup_zoho_oauth(request):
    """Setup Zoho OAuth2 for reliable email sending"""
    from .models import EmailConfiguration
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client_secret = request.POST.get('client_secret')
        
        if not client_id or not client_secret:
            return JsonResponse({
                'success': False,
                'message': 'Client ID und Client Secret sind erforderlich'
            })
        
        try:
            # Get or create email configuration
            config = EmailConfiguration.objects.filter(is_active=True).first()
            if not config:
                config = EmailConfiguration.objects.create(
                    email_host_user='kontakt@workloom.de',
                    default_from_email='kontakt@workloom.de',
                    smtp_host='smtp.zoho.eu',
                    smtp_port=587,
                    smtp_use_tls=True,
                    is_active=True,
                    backend_type='smtp',
                    created_by=request.user
                )
            
            # Save OAuth2 credentials
            config.zoho_client_id = client_id
            config.zoho_client_secret = client_secret
            
            # Generate redirect URI
            oauth_handler = ZohoOAuthHandler()
            redirect_uri = oauth_handler.get_redirect_uri(request)
            config.zoho_redirect_uri = redirect_uri
            
            config.save()
            
            # Generate authorization URL
            auth_url = oauth_handler.get_authorization_url(request, client_id)
            
            return JsonResponse({
                'success': True,
                'message': 'OAuth2 Konfiguration gespeichert',
                'authorization_url': auth_url,
                'redirect_uri': redirect_uri,
                'next_step': 'Klicken Sie auf den Authorization Link um OAuth2 zu vervollständigen'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Speichern der OAuth2 Konfiguration: {str(e)}'
            })
    
    # GET request - return setup information
    oauth_handler = ZohoOAuthHandler()
    redirect_uri = oauth_handler.get_redirect_uri(request)
    
    return JsonResponse({
        'redirect_uri': redirect_uri,
        'setup_instructions': """
        1. Gehen Sie zu https://api-console.zoho.eu/
        2. Erstellen Sie eine neue 'Server-based Applications' Anwendung
        3. Tragen Sie als Redirect URI ein: """ + redirect_uri + """
        4. Fügen Sie diese Scopes hinzu: ZohoMail.send.ALL
        5. Kopieren Sie Client ID und Client Secret hierher
        """,
        'current_configuration': EmailConfiguration.objects.filter(is_active=True).first().zoho_client_id if EmailConfiguration.objects.filter(is_active=True).exists() else None
    })


@login_required
@user_passes_test(is_superuser)
def zoho_oauth_callback(request):
    """Handle OAuth2 callback from Zoho"""
    from .models import EmailConfiguration
    
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'OAuth2 Fehler: {error}')
        return redirect('superconfig:dashboard')
    
    if not code:
        messages.error(request, 'Kein Authorization Code erhalten')
        return redirect('superconfig:dashboard')
    
    try:
        # Get email configuration
        config = EmailConfiguration.objects.filter(is_active=True).first()
        if not config or not config.zoho_client_id:
            messages.error(request, 'Keine OAuth2 Konfiguration gefunden')
            return redirect('superconfig:dashboard')
        
        # Exchange code for tokens
        oauth_handler = ZohoOAuthHandler()
        tokens = oauth_handler.exchange_code_for_tokens(
            code,
            config.zoho_client_id,
            config.zoho_client_secret,
            config.zoho_redirect_uri
        )
        
        if 'error' in tokens:
            messages.error(request, f'Token Exchange Fehler: {tokens["error"]}')
            return redirect('superconfig:dashboard')
        
        # Save tokens (you might want to create a separate model for this)
        # For now, we'll use a simple approach
        config.email_host_password = f"oauth2:{tokens.get('access_token', '')}"
        config.save()
        
        messages.success(request, '✅ Zoho OAuth2 erfolgreich konfiguriert! E-Mails können jetzt über die Zoho API gesendet werden.')
        
    except Exception as e:
        messages.error(request, f'OAuth2 Callback Fehler: {str(e)}')
    
    return redirect('superconfig:dashboard')


def get_recent_email_activity():
    """Get recent email activity (placeholder)"""
    # This could be extended to check actual email logs
    return {
        'status': 'connected',
        'message': f'SMTP Verbindung zu {settings.EMAIL_HOST}:{settings.EMAIL_PORT} erfolgreich',
        'connected': True
    }


def check_smtp_connection_with_config(config):
    """Check SMTP server connection using EmailConfiguration"""
    try:
        if config.backend_type != 'smtp':
            return {
                'status': config.backend_type,
                'message': f'{config.backend_type.title()} Backend aktiv (kein SMTP)',
                'connected': False
            }
        
        # Try to connect to SMTP server
        context = ssl.create_default_context()
        
        # Choose connection method based on SSL/TLS settings
        if config.smtp_use_ssl:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context) as server:
                if config.email_host_password:
                    server.login(config.email_host_user, config.email_host_password)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
                if config.smtp_use_tls:
                    server.starttls(context=context)
                if config.email_host_password:
                    server.login(config.email_host_user, config.email_host_password)
        
        return {
            'status': 'connected',
            'message': f'SMTP Verbindung zu {config.smtp_host}:{config.smtp_port} erfolgreich',
            'connected': True
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'SMTP Verbindung fehlgeschlagen: {str(e)}',
            'connected': False
        }


def get_recent_email_activity():
    """Get recent email activity from logs or database"""
    try:
        # Try to get recent email activity from Django's email logs
        # This would typically come from a custom email logging system
        
        # For now, return mock data - this can be enhanced with actual logging
        return {
            'last_email_sent': 'N/A (Logging nicht konfiguriert)',
            'total_emails_today': 'N/A',
            'failed_emails': 'N/A',
            'email_queue_length': 'N/A'
        }
        
    except Exception as e:
        return {
            'error': f'Fehler beim Laden der Email-Aktivität: {str(e)}'
        }


@login_required
@user_passes_test(is_superuser)
def save_email_config(request):
    """Save new email configuration to database"""
    if request.method == 'POST':
        try:
            # Get form data
            data = {
                'smtp_host': request.POST.get('smtp_host'),
                'smtp_port': int(request.POST.get('smtp_port', 587)),
                'smtp_use_tls': request.POST.get('smtp_use_tls') == 'true',
                'smtp_use_ssl': request.POST.get('smtp_use_ssl') == 'true',
                'email_host_user': request.POST.get('email_host_user'),
                'email_host_password': request.POST.get('email_host_password'),
                'default_from_email': request.POST.get('default_from_email'),
                'backend_type': request.POST.get('backend_type', 'smtp'),
                'zoho_client_id': request.POST.get('zoho_client_id', ''),
                'zoho_client_secret': request.POST.get('zoho_client_secret', ''),
                'zoho_redirect_uri': request.POST.get('zoho_redirect_uri', ''),
            }
            
            # Validate required fields
            required_fields = ['smtp_host', 'email_host_user', 'default_from_email']
            if data['backend_type'] == 'smtp':
                required_fields.extend(['email_host_password'])
                
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({
                    'success': False,
                    'message': f'Erforderliche Felder fehlen: {", ".join(missing_fields)}'
                })
            
            # Test connection before saving
            temp_config = EmailConfiguration(**data, created_by=request.user)
            test_result = check_smtp_connection_with_config(temp_config)
            
            if data['backend_type'] == 'smtp' and not test_result['connected']:
                return JsonResponse({
                    'success': False,
                    'message': f'SMTP-Verbindungstest fehlgeschlagen: {test_result["message"]}'
                })
            
            # Save configuration
            config = EmailConfiguration.objects.create(
                created_by=request.user,
                is_active=True,  # This will deactivate other configs
                **data
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Email-Konfiguration erfolgreich gespeichert (ID: {config.id})',
                'config_id': config.id
            })
            
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': f'Ungültige Eingabe: {str(e)}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Speichern: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def add_shared_email(request):
    """Add email to shared superuser list"""
    if request.method == 'POST':
        try:
            email_address = request.POST.get('email_address')
            display_name = request.POST.get('display_name')
            description = request.POST.get('description', '')
            
            if not email_address or not display_name:
                return JsonResponse({
                    'success': False,
                    'message': 'Email-Adresse und Anzeigename sind erforderlich'
                })
            
            # Create or update shared email
            shared_email, created = SuperuserEmailShare.objects.get_or_create(
                email_address=email_address,
                defaults={
                    'display_name': display_name,
                    'description': description,
                    'added_by': request.user,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing
                shared_email.display_name = display_name
                shared_email.description = description
                shared_email.is_active = True
                shared_email.save()
                
                action = 'aktualisiert'
            else:
                action = 'hinzugefügt'
            
            return JsonResponse({
                'success': True,
                'message': f'Email "{display_name}" erfolgreich {action}',
                'email': {
                    'email_address': shared_email.email_address,
                    'display_name': shared_email.display_name,
                    'description': shared_email.description,
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Hinzufügen der Email: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def update_email_config(request):
    """Legacy - redirect to save_email_config"""
    return save_email_config(request)


# Global Messages Views

@login_required
@user_passes_test(is_superuser)
def create_global_message(request):
    """Create a new global message"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Create new message
            message = GlobalMessage(
                title=data['title'],
                content=data['content'],
                display_position=data.get('display_position', 'popup_center'),
                display_type=data.get('display_type', 'info'),
                visibility=data.get('visibility', 'all'),
                duration_seconds=data.get('duration_seconds') or None,
                is_active=data.get('is_active', True),
                is_dismissible=data.get('is_dismissible', True),
                start_date=data.get('start_date') or None,
                end_date=data.get('end_date') or None,
                created_by=request.user
            )

            message.save()

            return JsonResponse({
                'success': True,
                'message': 'Nachricht erfolgreich erstellt',
                'message_data': {
                    'id': message.id,
                    'title': message.title,
                    'content': message.content,
                    'display_position': message.get_display_position_display(),
                    'display_type': message.get_display_type_display(),
                    'visibility': message.get_visibility_display(),
                    'is_active': message.is_active,
                    'created_at': message.created_at.strftime('%d.%m.%Y %H:%M')
                }
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Erstellen der Nachricht: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def list_global_messages(request):
    """List all global messages"""
    try:
        messages = GlobalMessage.objects.all().order_by('-created_at')

        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'title': msg.title,
                'content': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
                'display_position': msg.get_display_position_display(),
                'display_type': msg.get_display_type_display(),
                'visibility': msg.get_visibility_display(),
                'is_active': msg.is_active,
                'is_currently_active': msg.is_currently_active(),
                'duration_seconds': msg.duration_seconds,
                'start_date': msg.start_date.strftime('%d.%m.%Y %H:%M') if msg.start_date else None,
                'end_date': msg.end_date.strftime('%d.%m.%Y %H:%M') if msg.end_date else None,
                'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M'),
                'created_by': msg.created_by.username
            })

        return JsonResponse({
            'success': True,
            'messages': messages_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler beim Laden der Nachrichten: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
def toggle_message_status(request, message_id):
    """Toggle message active status"""
    if request.method == 'POST':
        try:
            message = GlobalMessage.objects.get(id=message_id)
            message.is_active = not message.is_active
            message.save()

            return JsonResponse({
                'success': True,
                'message': f'Nachricht wurde {"aktiviert" if message.is_active else "deaktiviert"}',
                'is_active': message.is_active
            })

        except GlobalMessage.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Nachricht nicht gefunden'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def delete_global_message(request, message_id):
    """Delete a global message"""
    if request.method == 'POST':
        try:
            message = GlobalMessage.objects.get(id=message_id)
            message.delete()

            return JsonResponse({
                'success': True,
                'message': 'Nachricht erfolgreich gelöscht'
            })

        except GlobalMessage.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Nachricht nicht gefunden'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Fehler beim Löschen: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@user_passes_test(is_superuser)
def get_message_for_preview(request, message_id):
    """Get message data for preview"""
    try:
        message = GlobalMessage.objects.get(id=message_id)

        return JsonResponse({
            'success': True,
            'message_data': {
                'id': message.id,
                'title': message.title,
                'content': message.content,
                'display_position': message.display_position,
                'display_type': message.display_type,
                'visibility': message.visibility,
                'duration_seconds': message.duration_seconds,
                'is_dismissible': message.is_dismissible,
                'is_active': message.is_active,
                'is_currently_active': message.is_currently_active()
            }
        })

    except GlobalMessage.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Nachricht nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })


def get_active_messages_for_user(request):
    """Get active messages for current user (for display on website)"""
    try:
        user = request.user if request.user.is_authenticated else None
        active_messages = GlobalMessage.get_active_messages_for_user(user)

        messages_data = []
        for msg in active_messages:
            messages_data.append({
                'id': msg.id,
                'title': msg.title,
                'content': msg.content,
                'display_position': msg.display_position,
                'display_type': msg.display_type,
                'duration_seconds': msg.duration_seconds,
                'is_dismissible': msg.is_dismissible
            })

        return JsonResponse({
            'success': True,
            'messages': messages_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })
