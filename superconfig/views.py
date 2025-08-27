import os
import json
import shutil
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.management import call_command
from django.db import connection
import sqlite3


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
