"""
Android APK Manager Views
Download Handler und Web Interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages

from .models import AndroidApp, AppVersion, DownloadLog, AppScreenshot
from .forms import AndroidAppForm, AppVersionForm, AppScreenshotForm, MultipleScreenshotForm


def download_apk(request, version_id):
    """
    APK-Download mit Logging
    Public Endpoint - keine Authentication erforderlich
    """
    try:
        # Finde Version
        version = get_object_or_404(AppVersion, id=version_id, is_active=True)

        # Check ob App öffentlich ist
        if not version.app.is_public:
            raise Http404("App not available")

        # Log the download
        download_log = DownloadLog.objects.create(
            app_version=version,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            android_version=request.GET.get('android_version', ''),
            device_model=request.GET.get('device_model', '')
        )

        # Öffne APK-Datei
        apk_file = version.apk_file.open('rb')

        # Erstelle Response
        response = FileResponse(
            apk_file,
            content_type='application/vnd.android.package-archive',
            as_attachment=True,
            filename=f"{version.app.package_name}_v{version.version_name}.apk"
        )

        # Aktualisiere Download-Counter
        version.download_count += 1
        version.save(update_fields=['download_count'])

        # Markiere Download als completed
        download_log.download_completed = True
        download_log.save(update_fields=['download_completed'])

        return response

    except AppVersion.DoesNotExist:
        raise Http404("APK version not found")
    except Exception as e:
        # Bei Fehler: Log als nicht completed markieren
        if 'download_log' in locals():
            download_log.download_completed = False
            download_log.save(update_fields=['download_completed'])
        raise


def dashboard(request):
    """
    Dashboard für App-Owner
    Zeigt alle eigenen Apps mit Statistiken
    Nicht eingeloggte User werden zur öffentlichen Liste weitergeleitet
    """
    # Nicht eingeloggte User zur öffentlichen Liste weiterleiten
    if not request.user.is_authenticated:
        return redirect('android_apk_manager:public_app_list')

    # Hole alle Apps des Users
    apps = AndroidApp.objects.filter(
        created_by=request.user
    ).select_related('created_by').prefetch_related('versions').order_by('-updated_at')

    # Statistiken berechnen
    stats = {
        'total_apps': apps.count(),
        'public_apps': apps.filter(is_public=True).count(),
        'private_apps': apps.filter(is_public=False).count(),
        'total_versions': AppVersion.objects.filter(app__created_by=request.user).count(),
        'total_downloads': apps.aggregate(total=Sum('versions__download_count'))['total'] or 0,
    }

    # Apps mit Latest Version anreichern
    apps_with_data = []
    for app in apps:
        versions = app.versions.all().order_by('-version_code')
        latest_version = versions.first()

        apps_with_data.append({
            'app': app,
            'latest_version': latest_version,
            'version_count': versions.count(),
            'total_downloads': app.total_downloads,
        })

    context = {
        'apps': apps_with_data,
        'stats': stats,
    }

    return render(request, 'android_apk_manager/dashboard.html', context)


@login_required
def app_detail(request, app_id):
    """
    App-Detail für Owner
    Zeigt alle Versionen, Statistiken und Logs
    """
    # Hole App (nur eigene)
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    # Hole alle Versionen
    versions = app.versions.all().order_by('-version_code')

    # Statistiken
    stats = {
        'total_versions': versions.count(),
        'active_versions': versions.filter(is_active=True).count(),
        'total_downloads': app.total_downloads,
        'downloads_by_channel': {},
        'recent_downloads': []
    }

    # Downloads per Channel
    for channel in ['alpha', 'beta', 'production']:
        channel_downloads = versions.filter(
            channel=channel
        ).aggregate(total=Sum('download_count'))['total'] or 0
        stats['downloads_by_channel'][channel] = channel_downloads

    # Letzte Downloads (Top 10)
    recent_downloads = DownloadLog.objects.filter(
        app_version__app=app
    ).select_related('app_version').order_by('-downloaded_at')[:10]
    stats['recent_downloads'] = recent_downloads

    # Screenshots
    screenshots = app.screenshots.all().order_by('order')
    screenshot_form = MultipleScreenshotForm(app=app)
    can_add_screenshots = AppScreenshot.can_add_more(app)

    context = {
        'app': app,
        'versions': versions,
        'stats': stats,
        'screenshots': screenshots,
        'screenshot_form': screenshot_form,
        'can_add_screenshots': can_add_screenshots,
    }

    return render(request, 'android_apk_manager/app_detail.html', context)


def public_app_list(request):
    """
    Öffentliche Liste aller verfügbaren Apps
    Kein Login erforderlich
    """
    # Hole alle öffentlichen Apps
    apps = AndroidApp.objects.filter(
        is_public=True
    ).select_related('created_by').prefetch_related('versions').order_by('name')

    # Apps mit Latest Version anreichern
    apps_with_data = []
    for app in apps:
        # Hole neueste production Version
        latest_version = app.versions.filter(
            channel='production',
            is_active=True
        ).order_by('-version_code').first()

        # Alternativ: neueste Version aus anderen Channels
        if not latest_version:
            latest_version = app.versions.filter(
                is_active=True
            ).order_by('-version_code').first()

        apps_with_data.append({
            'app': app,
            'latest_version': latest_version,
            'total_downloads': app.total_downloads,
        })

    context = {
        'apps': apps_with_data,
    }

    return render(request, 'android_apk_manager/public_app_list.html', context)


def public_app_detail(request, app_id):
    """
    Öffentliche App-Detail-Seite
    Zeigt alle verfügbaren Versionen für Download
    Kein Login erforderlich
    """
    # Hole App (nur öffentliche)
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        is_public=True
    )

    # Hole alle aktiven Versionen, sortiert nach Channel und Version
    versions = app.versions.filter(
        is_active=True
    ).order_by('channel', '-version_code')

    # Gruppiere nach Channel
    versions_by_channel = {
        'production': [],
        'beta': [],
        'alpha': []
    }

    for version in versions:
        versions_by_channel[version.channel].append(version)

    # Markiere aktuelle Versionen pro Channel
    for channel, channel_versions in versions_by_channel.items():
        for version in channel_versions:
            version.is_latest = (version == channel_versions[0]) if channel_versions else False

    # Screenshots
    screenshots = app.screenshots.all().order_by('order')

    context = {
        'app': app,
        'versions_by_channel': versions_by_channel,
        'total_downloads': app.total_downloads,
        'screenshots': screenshots,
    }

    return render(request, 'android_apk_manager/public_app_detail.html', context)


@login_required
def toggle_app_public(request, app_id):
    """
    Toggle public/private Status einer App
    POST-only view
    """
    if request.method != 'POST':
        return redirect('android_apk_manager:dashboard')

    # Hole App (nur eigene)
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    # Toggle
    app.is_public = not app.is_public
    app.save(update_fields=['is_public'])

    status = 'öffentlich' if app.is_public else 'privat'
    messages.success(request, f'App "{app.name}" ist jetzt {status}.')

    return redirect('android_apk_manager:app_detail', app_id=app_id)


@login_required
def delete_app(request, app_id):
    """
    Lösche App und alle zugehörigen Versionen
    POST-only view mit Bestätigung
    """
    if request.method != 'POST':
        return redirect('android_apk_manager:dashboard')

    # Hole App (nur eigene)
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    app_name = app.name
    app.delete()

    messages.success(request, f'App "{app_name}" wurde erfolgreich gelöscht.')

    return redirect('android_apk_manager:dashboard')


@login_required
def create_app(request):
    """
    Erstelle neue App über Web-Interface
    """
    if request.method == 'POST':
        form = AndroidAppForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.created_by = request.user
            app.save()

            messages.success(request, f'App "{app.name}" wurde erfolgreich erstellt!')
            return redirect('android_apk_manager:app_detail', app_id=app.id)
    else:
        form = AndroidAppForm()

    context = {
        'form': form,
    }

    return render(request, 'android_apk_manager/create_app.html', context)


@login_required
def upload_version(request, app_id=None):
    """
    Upload neue Version über Web-Interface
    """
    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            version = form.save()

            # Wenn "Als aktuell markieren" aktiviert, entferne Flag von anderen
            if version.is_current_for_channel:
                AppVersion.objects.filter(
                    app=version.app,
                    channel=version.channel
                ).exclude(id=version.id).update(is_current_for_channel=False)

            messages.success(
                request,
                f'Version {version.version_name} wurde erfolgreich hochgeladen!'
            )
            return redirect('android_apk_manager:app_detail', app_id=version.app.id)
    else:
        initial = {}
        if app_id:
            app = get_object_or_404(AndroidApp, id=app_id, created_by=request.user)
            initial['app'] = app

        form = AppVersionForm(initial=initial, user=request.user)

    context = {
        'form': form,
        'app_id': app_id,
    }

    return render(request, 'android_apk_manager/upload_version.html', context)


@login_required
def edit_app(request, app_id):
    """
    Bearbeite App über Web-Interface
    """
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    if request.method == 'POST':
        form = AndroidAppForm(request.POST, request.FILES, instance=app)
        if form.is_valid():
            form.save()
            messages.success(request, f'App "{app.name}" wurde aktualisiert!')
            return redirect('android_apk_manager:app_detail', app_id=app.id)
    else:
        form = AndroidAppForm(instance=app)

    context = {
        'form': form,
        'app': app,
    }

    return render(request, 'android_apk_manager/edit_app.html', context)


@login_required
def edit_version(request, version_id):
    """
    Bearbeite Version über Web-Interface
    """
    version = get_object_or_404(
        AppVersion,
        id=version_id,
        app__created_by=request.user
    )

    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES, instance=version, user=request.user)
        if form.is_valid():
            version = form.save()

            # Update "current" flag
            if version.is_current_for_channel:
                AppVersion.objects.filter(
                    app=version.app,
                    channel=version.channel
                ).exclude(id=version.id).update(is_current_for_channel=False)

            messages.success(request, f'Version {version.version_name} wurde aktualisiert!')
            return redirect('android_apk_manager:app_detail', app_id=version.app.id)
    else:
        form = AppVersionForm(instance=version, user=request.user)

    context = {
        'form': form,
        'version': version,
    }

    return render(request, 'android_apk_manager/edit_version.html', context)


@login_required
def delete_version(request, version_id):
    """
    Lösche Version
    POST-only view
    """
    if request.method != 'POST':
        return redirect('android_apk_manager:dashboard')

    version = get_object_or_404(
        AppVersion,
        id=version_id,
        app__created_by=request.user
    )

    app_id = version.app.id
    version_name = version.version_name
    version.delete()

    messages.success(request, f'Version {version_name} wurde gelöscht.')

    return redirect('android_apk_manager:app_detail', app_id=app_id)


@login_required
def upload_screenshots(request, app_id):
    """
    Upload Screenshots für eine App
    Unterstützt Mehrfach-Upload (bis zu 10 Screenshots)
    """
    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    if request.method != 'POST':
        return redirect('android_apk_manager:app_detail', app_id=app_id)

    # Prüfe ob noch Screenshots hinzugefügt werden können
    current_count = AppScreenshot.objects.filter(app=app).count()
    if current_count >= 10:
        messages.error(request, 'Maximale Anzahl von 10 Screenshots erreicht.')
        return redirect('android_apk_manager:app_detail', app_id=app_id)

    # Verarbeite alle hochgeladenen Dateien
    files = request.FILES.getlist('screenshots')
    if not files:
        messages.warning(request, 'Keine Dateien ausgewählt.')
        return redirect('android_apk_manager:app_detail', app_id=app_id)

    uploaded_count = 0
    for file in files:
        # Prüfe Limit
        if current_count + uploaded_count >= 10:
            messages.warning(request, f'Limit erreicht. {uploaded_count} von {len(files)} Screenshots hochgeladen.')
            break

        # Prüfe ob es ein Bild ist
        if not file.content_type.startswith('image/'):
            continue

        # Erstelle Screenshot
        screenshot = AppScreenshot(
            app=app,
            image=file,
            order=AppScreenshot.get_next_order(app)
        )
        screenshot.save()
        uploaded_count += 1

    if uploaded_count > 0:
        messages.success(request, f'{uploaded_count} Screenshot(s) erfolgreich hochgeladen.')
    else:
        messages.warning(request, 'Keine gültigen Bilder gefunden.')

    return redirect('android_apk_manager:app_detail', app_id=app_id)


@login_required
def delete_screenshot(request, screenshot_id):
    """
    Lösche Screenshot
    POST-only view
    """
    if request.method != 'POST':
        return redirect('android_apk_manager:dashboard')

    screenshot = get_object_or_404(
        AppScreenshot,
        id=screenshot_id,
        app__created_by=request.user
    )

    app_id = screenshot.app.id
    screenshot.delete()

    messages.success(request, 'Screenshot wurde gelöscht.')

    return redirect('android_apk_manager:app_detail', app_id=app_id)


@login_required
def reorder_screenshots(request, app_id):
    """
    Ändere die Reihenfolge von Screenshots
    POST mit JSON-Body: {"order": ["uuid1", "uuid2", ...]}
    """
    from django.http import JsonResponse
    import json

    app = get_object_or_404(
        AndroidApp,
        id=app_id,
        created_by=request.user
    )

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        order_list = data.get('order', [])

        for index, screenshot_id in enumerate(order_list):
            AppScreenshot.objects.filter(
                id=screenshot_id,
                app=app
            ).update(order=index)

        return JsonResponse({'success': True})
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid data'}, status=400)
