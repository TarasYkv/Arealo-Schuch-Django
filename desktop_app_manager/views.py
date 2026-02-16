"""
Desktop App Manager Views
Download Handler und Web Interface
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages

from .models import DesktopApp, AppVersion, DownloadLog, AppScreenshot
from .forms import DesktopAppForm, AppVersionForm, MultipleScreenshotForm

import json


def download_exe(request, version_id):
    """
    EXE-Download mit Logging
    Public Endpoint - keine Authentication erforderlich
    """
    try:
        version = get_object_or_404(AppVersion, id=version_id, is_active=True)

        if not version.app.is_public:
            raise Http404("App not available")

        download_log = DownloadLog.objects.create(
            app_version=version,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            windows_version=request.GET.get('windows_version', ''),
        )

        exe_file = version.exe_file.open('rb')

        response = FileResponse(
            exe_file,
            content_type='application/octet-stream',
            as_attachment=True,
            filename=f"{version.app.app_identifier}_v{version.version_name}.exe"
        )

        version.download_count += 1
        version.save(update_fields=['download_count'])

        download_log.download_completed = True
        download_log.save(update_fields=['download_completed'])

        return response

    except AppVersion.DoesNotExist:
        raise Http404("EXE version not found")
    except Exception as e:
        if 'download_log' in locals():
            download_log.download_completed = False
            download_log.save(update_fields=['download_completed'])
        raise


def dashboard(request):
    """Dashboard fuer App-Owner"""
    if not request.user.is_authenticated:
        return redirect('desktop_app_manager:public_app_list')

    apps = DesktopApp.objects.filter(
        created_by=request.user
    ).select_related('created_by').prefetch_related('versions').order_by('-updated_at')

    stats = {
        'total_apps': apps.count(),
        'public_apps': apps.filter(is_public=True).count(),
        'private_apps': apps.filter(is_public=False).count(),
        'total_versions': AppVersion.objects.filter(app__created_by=request.user).count(),
        'total_downloads': apps.aggregate(total=Sum('versions__download_count'))['total'] or 0,
    }

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

    return render(request, 'desktop_app_manager/dashboard.html', context)


@login_required
def app_detail(request, app_id):
    """App-Detail fuer Owner"""
    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)

    versions = app.versions.all().order_by('-version_code')

    stats = {
        'total_versions': versions.count(),
        'active_versions': versions.filter(is_active=True).count(),
        'total_downloads': app.total_downloads,
        'downloads_by_channel': {},
        'recent_downloads': []
    }

    for channel in ['alpha', 'beta', 'production']:
        channel_downloads = versions.filter(
            channel=channel
        ).aggregate(total=Sum('download_count'))['total'] or 0
        stats['downloads_by_channel'][channel] = channel_downloads

    recent_downloads = DownloadLog.objects.filter(
        app_version__app=app
    ).select_related('app_version').order_by('-downloaded_at')[:10]
    stats['recent_downloads'] = recent_downloads

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

    return render(request, 'desktop_app_manager/app_detail.html', context)


def public_app_list(request):
    """Oeffentliche Liste aller verfuegbaren Apps"""
    apps = DesktopApp.objects.filter(
        is_public=True
    ).select_related('created_by').prefetch_related('versions', 'screenshots').order_by('name')

    apps_with_data = []
    for app in apps:
        latest_version = app.versions.filter(
            channel='production', is_active=True
        ).order_by('-version_code').first()

        if not latest_version:
            latest_version = app.versions.filter(
                is_active=True
            ).order_by('-version_code').first()

        first_screenshot = app.screenshots.order_by('order').first()

        apps_with_data.append({
            'app': app,
            'latest_version': latest_version,
            'total_downloads': app.total_downloads,
            'first_screenshot': first_screenshot,
        })

    context = {
        'apps': apps_with_data,
    }

    return render(request, 'desktop_app_manager/public_app_list.html', context)


def public_app_detail(request, app_id):
    """Oeffentliche App-Detail-Seite"""
    app = get_object_or_404(DesktopApp, id=app_id, is_public=True)

    versions = app.versions.filter(is_active=True).order_by('channel', '-version_code')

    versions_by_channel = {
        'production': [],
        'beta': [],
        'alpha': []
    }

    for version in versions:
        versions_by_channel[version.channel].append(version)

    for channel, channel_versions in versions_by_channel.items():
        for version in channel_versions:
            version.is_latest = (version == channel_versions[0]) if channel_versions else False

    screenshots = app.screenshots.all().order_by('order')

    context = {
        'app': app,
        'versions_by_channel': versions_by_channel,
        'total_downloads': app.total_downloads,
        'screenshots': screenshots,
    }

    return render(request, 'desktop_app_manager/public_app_detail.html', context)


@login_required
def toggle_app_public(request, app_id):
    """Toggle public/private Status"""
    if request.method != 'POST':
        return redirect('desktop_app_manager:dashboard')

    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)
    app.is_public = not app.is_public
    app.save(update_fields=['is_public'])

    status_text = 'öffentlich' if app.is_public else 'privat'
    messages.success(request, f'App "{app.name}" ist jetzt {status_text}.')

    return redirect('desktop_app_manager:app_detail', app_id=app_id)


@login_required
def delete_app(request, app_id):
    """Loesche App und alle zugehoerigen Versionen"""
    if request.method != 'POST':
        return redirect('desktop_app_manager:dashboard')

    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)
    app_name = app.name
    app.delete()

    messages.success(request, f'App "{app_name}" wurde erfolgreich gelöscht.')
    return redirect('desktop_app_manager:dashboard')


@login_required
def create_app(request):
    """Erstelle neue App"""
    if request.method == 'POST':
        form = DesktopAppForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.created_by = request.user
            app.save()
            messages.success(request, f'App "{app.name}" wurde erfolgreich erstellt!')
            return redirect('desktop_app_manager:app_detail', app_id=app.id)
    else:
        form = DesktopAppForm()

    return render(request, 'desktop_app_manager/create_app.html', {'form': form})


@login_required
def upload_version(request, app_id=None):
    """Upload neue Version"""
    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            version = form.save()

            if version.is_current_for_channel:
                AppVersion.objects.filter(
                    app=version.app,
                    channel=version.channel
                ).exclude(id=version.id).update(is_current_for_channel=False)

            messages.success(request, f'Version {version.version_name} wurde erfolgreich hochgeladen!')
            return redirect('desktop_app_manager:app_detail', app_id=version.app.id)
    else:
        initial = {}
        if app_id:
            app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)
            initial['app'] = app
        form = AppVersionForm(initial=initial, user=request.user)

    return render(request, 'desktop_app_manager/upload_version.html', {'form': form, 'app_id': app_id})


@login_required
def edit_app(request, app_id):
    """Bearbeite App"""
    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)

    if request.method == 'POST':
        form = DesktopAppForm(request.POST, request.FILES, instance=app)
        if form.is_valid():
            form.save()
            messages.success(request, f'App "{app.name}" wurde aktualisiert!')
            return redirect('desktop_app_manager:app_detail', app_id=app.id)
    else:
        form = DesktopAppForm(instance=app)

    return render(request, 'desktop_app_manager/edit_app.html', {'form': form, 'app': app})


@login_required
def edit_version(request, version_id):
    """Bearbeite Version"""
    version = get_object_or_404(AppVersion, id=version_id, app__created_by=request.user)

    if request.method == 'POST':
        form = AppVersionForm(request.POST, request.FILES, instance=version, user=request.user)
        if form.is_valid():
            version = form.save()

            if version.is_current_for_channel:
                AppVersion.objects.filter(
                    app=version.app,
                    channel=version.channel
                ).exclude(id=version.id).update(is_current_for_channel=False)

            messages.success(request, f'Version {version.version_name} wurde aktualisiert!')
            return redirect('desktop_app_manager:app_detail', app_id=version.app.id)
    else:
        form = AppVersionForm(instance=version, user=request.user)

    return render(request, 'desktop_app_manager/edit_version.html', {'form': form, 'version': version})


@login_required
def delete_version(request, version_id):
    """Loesche Version"""
    if request.method != 'POST':
        return redirect('desktop_app_manager:dashboard')

    version = get_object_or_404(AppVersion, id=version_id, app__created_by=request.user)
    app_id = version.app.id
    version_name = version.version_name
    version.delete()

    messages.success(request, f'Version {version_name} wurde gelöscht.')
    return redirect('desktop_app_manager:app_detail', app_id=app_id)


@login_required
def upload_screenshots(request, app_id):
    """Upload Screenshots fuer eine App"""
    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)

    if request.method != 'POST':
        return redirect('desktop_app_manager:app_detail', app_id=app_id)

    current_count = AppScreenshot.objects.filter(app=app).count()
    if current_count >= 10:
        messages.error(request, 'Maximale Anzahl von 10 Screenshots erreicht.')
        return redirect('desktop_app_manager:app_detail', app_id=app_id)

    files = request.FILES.getlist('screenshots')
    if not files:
        messages.warning(request, 'Keine Dateien ausgewählt.')
        return redirect('desktop_app_manager:app_detail', app_id=app_id)

    uploaded_count = 0
    for file in files:
        if current_count + uploaded_count >= 10:
            messages.warning(request, f'Limit erreicht. {uploaded_count} von {len(files)} Screenshots hochgeladen.')
            break

        if not file.content_type.startswith('image/'):
            continue

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

    return redirect('desktop_app_manager:app_detail', app_id=app_id)


@login_required
def delete_screenshot(request, screenshot_id):
    """Loesche Screenshot"""
    if request.method != 'POST':
        return redirect('desktop_app_manager:dashboard')

    screenshot = get_object_or_404(AppScreenshot, id=screenshot_id, app__created_by=request.user)
    app_id = screenshot.app.id
    screenshot.delete()

    messages.success(request, 'Screenshot wurde gelöscht.')
    return redirect('desktop_app_manager:app_detail', app_id=app_id)


@login_required
def reorder_screenshots(request, app_id):
    """Aendere die Reihenfolge von Screenshots"""
    app = get_object_or_404(DesktopApp, id=app_id, created_by=request.user)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        order_list = data.get('order', [])

        for index, screenshot_id in enumerate(order_list):
            AppScreenshot.objects.filter(id=screenshot_id, app=app).update(order=index)

        return JsonResponse({'success': True})
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid data'}, status=400)
