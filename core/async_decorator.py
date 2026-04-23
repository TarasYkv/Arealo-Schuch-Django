"""
Zentraler Async-Decorator für lange API-Calls

Verwendung:
    from core.async_decorator import async_task_view
    
    @login_required
    @async_task_view(timeout=300)
    def api_generate_content(request, project_id):
        # Normaler Code - wird automatisch via Celery ausgeführt
        ...
        return JsonResponse({...})
"""

import functools
import logging
import time
import json
import pickle
import hashlib
from celery import shared_task
from django.http import JsonResponse, HttpResponse

logger = logging.getLogger(__name__)

# Cache für laufende Tasks (Redis-basiert wäre besser für Production)
_running_tasks = {}


@shared_task(bind=True, max_retries=1)
def execute_view_task(self, view_path, request_data, args, kwargs):
    """Führt eine View-Funktion als Celery Task aus"""
    import importlib
    from django.test import RequestFactory
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        # View-Funktion laden
        module_path, func_name = view_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        view_func = getattr(module, func_name)
        
        # Request rekonstruieren
        factory = RequestFactory()
        
        method = request_data.get('method', 'POST')
        path = request_data.get('path', '/')
        
        if method == 'POST':
            request = factory.post(path, data=request_data.get('POST', {}))
        else:
            request = factory.get(path, data=request_data.get('GET', {}))
        
        # User setzen
        user_id = request_data.get('user_id')
        if user_id:
            request.user = User.objects.get(id=user_id)
        
        # View ausführen (ohne Decorator!)
        # Wir müssen die ursprüngliche Funktion aufrufen
        original_func = getattr(view_func, '_original_func', view_func)
        response = original_func(request, *args, **kwargs)
        
        # Response serialisieren
        if isinstance(response, JsonResponse):
            return {
                'success': True,
                'status_code': response.status_code,
                'content': json.loads(response.content.decode())
            }
        elif isinstance(response, HttpResponse):
            return {
                'success': True,
                'status_code': response.status_code,
                'content': response.content.decode()
            }
        else:
            return {'success': True, 'result': str(response)}
            
    except Exception as e:
        logger.error(f'View task failed: {e}')
        return {'success': False, 'error': str(e)}


def async_task_view(timeout=300, poll_interval=0.5):
    """
    Decorator der eine View-Funktion via Celery ausführt.
    
    Die View wird synchron aufgerufen, aber intern via Celery verarbeitet.
    So wird der Gunicorn Worker nicht blockiert.
    
    Args:
        timeout: Max. Wartezeit in Sekunden (default: 5 Min)
        poll_interval: Polling-Intervall in Sekunden
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Request-Daten für Celery vorbereiten
            request_data = {
                'method': request.method,
                'path': request.path,
                'POST': dict(request.POST),
                'GET': dict(request.GET),
                'user_id': request.user.id if request.user.is_authenticated else None,
            }
            
            # View-Pfad für Import
            view_path = f'{view_func.__module__}.{view_func.__name__}'
            
            # Task starten
            task = execute_view_task.delay(
                view_path,
                request_data,
                args,
                {k: str(v) for k, v in kwargs.items()}  # UUID etc. als String
            )
            
            # Auf Ergebnis warten (synchron)
            start = time.time()
            while time.time() - start < timeout:
                if task.ready():
                    result = task.result
                    if result.get('success'):
                        content = result.get('content', {})
                        if isinstance(content, dict):
                            return JsonResponse(content)
                        else:
                            return HttpResponse(content)
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': result.get('error', 'Unknown error')
                        }, status=500)
                time.sleep(poll_interval)
            
            # Timeout
            return JsonResponse({
                'success': False,
                'error': 'Request dauerte zu lange. Bitte erneut versuchen.'
            }, status=504)
        
        # Original-Funktion speichern für Task-Ausführung
        wrapper._original_func = view_func
        return wrapper
    
    return decorator


# Einfachere Alternative: Task-basierte Ausführung
def run_in_celery(func, request, *args, **kwargs):
    """
    Führt eine Funktion via Celery aus und wartet auf das Ergebnis.
    
    Usage in View:
        result = run_in_celery(heavy_computation, request, param1, param2)
    """
    # Direkt ausführen wenn Celery nicht verfügbar
    try:
        from celery import current_app
        if not current_app.control.ping():
            return func(request, *args, **kwargs)
    except:
        return func(request, *args, **kwargs)
    
    # Via Celery
    task = execute_view_task.delay(
        f'{func.__module__}.{func.__name__}',
        {'user_id': request.user.id if hasattr(request, 'user') else None},
        args,
        kwargs
    )
    
    # Warten
    result = task.get(timeout=300)
    return result
