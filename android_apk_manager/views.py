"""
Android APK Manager Views
Download Handler und Web Interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages

from .models import AndroidApp, AppVersion, DownloadLog


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


@login_required
def dashboard(request):
    """
    Dashboard für App-Owner
    Zeigt alle eigenen Apps mit Statistiken
    """
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

    context = {
        'app': app,
        'versions': versions,
        'stats': stats,
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

    context = {
        'app': app,
        'versions_by_channel': versions_by_channel,
        'total_downloads': app.total_downloads,
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
