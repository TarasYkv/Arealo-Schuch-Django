"""API views for GPU server management (JarvisLabs + RunPod backend)."""
import json, logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ServerStatusView(View):
    def get(self, request):
        from .tasks import get_server_status
        status = get_server_status()
        return JsonResponse(status)


@method_decorator(csrf_exempt, name='dispatch')
class ServerStartView(View):
    def post(self, request):
        import json
        from .tasks import start_gpu_server
        try:
            body = json.loads(request.body) if request.body else {}
        except Exception:
            body = {}
        provider = body.get('provider', 'runpod')
        result = start_gpu_server.delay(provider=provider)
        return JsonResponse({"status": "starting", "task_id": result.id, "provider": provider})


@method_decorator(csrf_exempt, name='dispatch')
class ServerStopView(View):
    def post(self, request):
        from .tasks import stop_gpu_server
        result = stop_gpu_server.delay()
        return JsonResponse({"status": "stopping", "task_id": result.id})


@method_decorator(csrf_exempt, name='dispatch')
class SetAutoShutdownView(View):
    def post(self, request):
        from .models import GPUServerState
        try:
            data = json.loads(request.body)
            minutes = int(data.get("minutes", 10))
            if minutes not in (3, 5, 10, 15):
                minutes = 10
            state = GPUServerState.get()
            state.auto_shutdown_minutes = minutes
            state.save(update_fields=["auto_shutdown_minutes"])
            return JsonResponse({"status": "ok", "minutes": minutes})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
