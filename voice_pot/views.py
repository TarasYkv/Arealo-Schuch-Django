import io
import json
import subprocess
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse

from .models import VoiceRecording

# Bestehende Bausteine wiederverwenden (siehe Foto-Gravur-Pipeline)
from shopify_uploads.views import cors_headers

MAX_BYTES = 15 * 1024 * 1024            # 15 MB
MAX_DURATION = 130                      # Sekunden (etwas Puffer ueber 120)
ALLOWED_EXT = ('.webm', '.mp3', '.m4a', '.ogg', '.oga', '.wav', '.aac', '.mp4')

# Der Beschenkte hoert die Stimme auf der NATURMACHER-Seite (Branding/Vertrauen);
# Workloom hostet nur das Audio + liefert die Daten per API.
PLAY_BASE = 'https://naturmacher.de/pages/stimme'


def _play_url(uid):
    return f'{PLAY_BASE}?id={uid}'


def _is_superuser(u):
    return u.is_superuser


def _probe_duration(path):
    """Audiolaenge in Sekunden via ffprobe; 0 wenn nicht ermittelbar."""
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', path],
            capture_output=True, text=True, timeout=20)
        return int(float(out.stdout.strip()))
    except Exception:
        return 0


def _abs(request, path):
    return request.build_absolute_uri(path)


# ---------------------------------------------------------------------------
# Oeffentliche API (vom Shopify-Theme aufgerufen)
# ---------------------------------------------------------------------------
@csrf_exempt
@cors_headers
def upload_audio(request):
    """POST (multipart): audio_file [+ gift_message, sender_name, recipient_name,
    consent, shopify_product_id]. Legt eine (noch nicht freigegebene) Aufnahme an
    und gibt die nicht-erratbare unique_id + Abspiel-URL zurueck."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST erwartet'}, status=405)

    f = request.FILES.get('audio_file') or request.FILES.get('audio')
    if not f:
        return JsonResponse({'error': 'keine Audiodatei'}, status=400)
    if f.size > MAX_BYTES:
        return JsonResponse({'error': 'Datei zu groß (max. 15 MB)'}, status=400)
    name = (f.name or 'aufnahme.webm').lower()
    ctype = (getattr(f, 'content_type', '') or '')
    if not (ctype.startswith('audio/') or ctype in ('video/webm', 'application/octet-stream')
            or name.endswith(ALLOWED_EXT)):
        return JsonResponse({'error': 'kein gültiges Audioformat'}, status=400)

    rec = VoiceRecording(
        gift_message=(request.POST.get('gift_message', '') or '')[:300],
        sender_name=(request.POST.get('sender_name', '') or '')[:120],
        recipient_name=(request.POST.get('recipient_name', '') or '')[:120],
        consent=str(request.POST.get('consent', '')).lower() in ('1', 'true', 'on', 'yes', 'ja'),
        shopify_product_id=(request.POST.get('shopify_product_id', '') or '')[:100],
        file_size=f.size,
    )
    if request.user.is_authenticated:
        rec.uploaded_by = request.user
    # Dateiendung normalisieren
    ext = next((e for e in ALLOWED_EXT if name.endswith(e)), '.webm')
    rec.audio_file.save(f'{rec.unique_id}{ext}', f, save=False)
    rec.save()

    try:
        rec.duration_sec = _probe_duration(rec.audio_file.path)
        if rec.duration_sec and rec.duration_sec > MAX_DURATION:
            rec.delete()
            return JsonResponse({'error': f'Aufnahme zu lang (max. {MAX_DURATION//60} Min)'}, status=400)
        rec.save(update_fields=['duration_sec'])
    except Exception:
        pass

    return JsonResponse({
        'ok': True,
        'unique_id': rec.unique_id,
        'play_url': _play_url(rec.unique_id),
        'audio_url': _abs(request, rec.audio_file.url),
        'duration_sec': rec.duration_sec,
    })


@csrf_exempt
@cors_headers
def order_webhook(request):
    """Shopify 'orders/create'-Webhook: verknuepft die Aufnahmen (unique_id steckt
    in den Line-Item-Properties) mit der Bestellung."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST erwartet'}, status=405)
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        return JsonResponse({'error': 'kein JSON'}, status=400)
    order_id = str(data.get('id', ''))
    order_name = str(data.get('name', ''))
    n = 0
    for li in (data.get('line_items') or []):
        for prop in (li.get('properties') or []):
            key = (prop.get('name') or '').strip().lower()
            if key in ('sprachnachricht-id', 'sprachnachricht_id', 'voice-id', 'audio-id'):
                uid = (prop.get('value') or '').strip()
                rec = VoiceRecording.objects.filter(unique_id=uid).first()
                if rec:
                    rec.shopify_order_id = order_id
                    rec.order_name = order_name[:60]
                    rec.shopify_product_id = str(li.get('product_id', ''))[:100]
                    rec.save(update_fields=['shopify_order_id', 'order_name', 'shopify_product_id'])
                    n += 1
    return JsonResponse({'ok': True, 'linked': n})


@csrf_exempt
@cors_headers
def voice_get(request, unique_id):
    """JSON-API fuer die Naturmacher-Abspielseite (CORS): Audio-URL + Begleittexte.
    Zaehlt Abrufe. Liefert approved=False, solange noch nicht freigegeben."""
    rec = VoiceRecording.objects.filter(unique_id=unique_id).first()
    if not rec:
        return JsonResponse({'ok': False, 'found': False}, status=404)
    if not rec.is_public:
        return JsonResponse({'ok': True, 'approved': False})
    VoiceRecording.objects.filter(pk=rec.pk).update(
        play_count=rec.play_count + 1, last_played_at=timezone.now())
    return JsonResponse({
        'ok': True, 'approved': True,
        'audio_url': _abs(request, rec.audio_file.url),
        'gift_message': rec.gift_message,
        'sender_name': rec.sender_name,
        'recipient_name': rec.recipient_name,
        'duration_sec': rec.duration_sec,
    })


def play(request, unique_id):
    """Alte Workloom-URL -> leitet auf die Naturmacher-Abspielseite weiter
    (Branding). Haelt frueher gravierte/geteilte Links lauffaehig."""
    from django.shortcuts import redirect as _redirect
    return _redirect(_play_url(unique_id))


# ---------------------------------------------------------------------------
# Admin-Cockpit (Superuser): anhoeren, freigeben, QR, sperren/loeschen
# ---------------------------------------------------------------------------
@login_required
@user_passes_test(_is_superuser)
def admin_list(request):
    q = (request.GET.get('q') or '').strip()
    flt = request.GET.get('f') or ''
    recs = VoiceRecording.objects.all()
    if q:
        recs = recs.filter(order_name__icontains=q) | recs.filter(shopify_order_id__icontains=q) \
            | recs.filter(unique_id__icontains=q) | recs.filter(sender_name__icontains=q)
    if flt == 'pending':
        recs = recs.filter(is_approved=False, is_active=True)
    elif flt == 'approved':
        recs = recs.filter(is_approved=True)
    pending = VoiceRecording.objects.filter(is_approved=False, is_active=True).count()
    return render(request, 'voice_pot/list.html',
                  {'recs': recs[:200], 'q': q, 'f': flt, 'pending': pending})


@login_required
@user_passes_test(_is_superuser)
def admin_detail(request, unique_id):
    rec = get_object_or_404(VoiceRecording, unique_id=unique_id)
    from fileshare.utils import generate_qr_code
    qr_data_uri = generate_qr_code(_play_url(rec.unique_id))
    return render(request, 'voice_pot/detail.html', {'rec': rec, 'qr': qr_data_uri})


@login_required
@user_passes_test(_is_superuser)
@require_POST
def admin_action(request, unique_id):
    rec = get_object_or_404(VoiceRecording, unique_id=unique_id)
    action = request.POST.get('action')
    if action == 'approve':
        rec.is_approved = True
        rec.approved_at = timezone.now()
        rec.save(update_fields=['is_approved', 'approved_at'])
    elif action == 'unapprove':
        rec.is_approved = False
        rec.save(update_fields=['is_approved'])
    elif action == 'toggle_active':
        rec.is_active = not rec.is_active
        rec.save(update_fields=['is_active'])
    elif action == 'delete':
        try:
            if rec.audio_file:
                rec.audio_file.delete(save=False)
        except Exception:
            pass
        rec.delete()
        return redirect('voice_pot:admin_list')
    return redirect('voice_pot:admin_detail', unique_id=rec.unique_id)


@login_required
@user_passes_test(_is_superuser)
def qr_png(request, unique_id):
    """Hochaufloesendes QR-PNG zum Download (Gravur-Vorlage)."""
    rec = get_object_or_404(VoiceRecording, unique_id=unique_id)
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20, border=2)
    qr.add_data(_play_url(rec.unique_id))
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    resp = HttpResponse(buf.getvalue(), content_type='image/png')
    resp['Content-Disposition'] = f'attachment; filename="qr_{rec.unique_id}.png"'
    return resp
