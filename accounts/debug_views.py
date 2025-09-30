from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import AppPermissionForm

@login_required
def debug_app_permissions(request):
    """Debug view to test app permissions form"""
    can_manage_apps = request.user.is_superuser or request.user.can_manage_app_permissions
    app_permission_form = AppPermissionForm() if can_manage_apps else None

    context = {
        'app_permission_form': app_permission_form,
        'can_manage_apps': can_manage_apps,
        'user': request.user,
    }

    return render(request, '/tmp/debug_app_permissions.html', context)