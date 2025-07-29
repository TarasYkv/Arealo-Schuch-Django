import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ZohoMailServerConnection, 
    EmailTemplateCategory, 
    EmailTemplate, 
    EmailSendLog
)
from .forms import (
    ZohoMailServerConnectionForm,
    EmailTemplateCategoryForm,
    EmailTemplateForm,
    TestEmailForm,
    EmailTemplateSearchForm,
    ConnectionTestForm
)
from .services import ZohoMailService, EmailTemplateService


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_superuser)
def dashboard(request):
    """Email templates dashboard"""
    # Get statistics
    total_templates = EmailTemplate.objects.count()
    active_templates = EmailTemplate.objects.filter(is_active=True).count()
    total_connections = ZohoMailServerConnection.objects.count()
    active_connections = ZohoMailServerConnection.objects.filter(is_active=True, is_configured=True).count()
    
    # Recent email logs
    recent_logs = EmailSendLog.objects.select_related(
        'template', 'connection'
    ).order_by('-created_at')[:10]
    
    context = {
        'total_templates': total_templates,
        'active_templates': active_templates,
        'total_connections': total_connections,
        'active_connections': active_connections,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'email_templates/dashboard.html', context)


# =============================================================================
# Zoho Mail Connection Views
# =============================================================================

@login_required
@user_passes_test(is_superuser)
def connection_list(request):
    """List all Zoho mail connections"""
    connections = ZohoMailServerConnection.objects.all().order_by('-created_at')
    
    # Handle search
    search = request.GET.get('search')
    if search:
        connections = connections.filter(
            Q(name__icontains=search) |
            Q(email_address__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(connections, 10)
    page_number = request.GET.get('page')
    connections = paginator.get_page(page_number)
    
    return render(request, 'email_templates/connections/list.html', {
        'connections': connections,
        'search': search
    })


@login_required
@user_passes_test(is_superuser)
def connection_create(request):
    """Create new Zoho mail connection"""
    if request.method == 'POST':
        form = ZohoMailServerConnectionForm(request.POST)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.created_by = request.user
            connection.save()
            messages.success(request, f'Verbindung "{connection.name}" wurde erstellt.')
            return redirect('email_templates:connection_detail', pk=connection.pk)
    else:
        form = ZohoMailServerConnectionForm()
    
    return render(request, 'email_templates/connections/form.html', {
        'form': form,
        'title': 'Neue Zoho Mail Verbindung'
    })


@login_required
@user_passes_test(is_superuser)
def connection_detail(request, pk):
    """View connection details"""
    connection = get_object_or_404(ZohoMailServerConnection, pk=pk)
    
    # Get authorization URL
    zoho_service = ZohoMailService(connection)
    auth_url = zoho_service.get_auth_url()
    
    # Debug info
    debug_info = {
        'stored_redirect_uri': connection.redirect_uri,
        'current_redirect_uri': f"{request.scheme}://{request.get_host()}{reverse('email_templates:oauth_callback')}",
        'auth_url': auth_url,
    }
    
    return render(request, 'email_templates/connections/detail.html', {
        'connection': connection,
        'auth_url': auth_url,
        'debug_info': debug_info
    })


@login_required
@user_passes_test(is_superuser)
def connection_edit(request, pk):
    """Edit Zoho mail connection"""
    connection = get_object_or_404(ZohoMailServerConnection, pk=pk)
    
    if request.method == 'POST':
        form = ZohoMailServerConnectionForm(request.POST, instance=connection)
        if form.is_valid():
            form.save()
            messages.success(request, f'Verbindung "{connection.name}" wurde aktualisiert.')
            return redirect('email_templates:connection_detail', pk=connection.pk)
    else:
        form = ZohoMailServerConnectionForm(instance=connection)
    
    return render(request, 'email_templates/connections/form.html', {
        'form': form,
        'connection': connection,
        'title': f'Verbindung bearbeiten: {connection.name}'
    })


@login_required
@user_passes_test(is_superuser)
def connection_delete(request, pk):
    """Delete Zoho mail connection"""
    connection = get_object_or_404(ZohoMailServerConnection, pk=pk)
    
    if request.method == 'POST':
        name = connection.name
        connection.delete()
        messages.success(request, f'Verbindung "{name}" wurde gelöscht.')
        return redirect('email_templates:connection_list')
    
    return render(request, 'email_templates/connections/delete.html', {
        'connection': connection
    })


def oauth_callback(request):
    """Handle OAuth callback from Zoho"""
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    # Handle OAuth error response
    if error:
        error_description = request.GET.get('error_description', 'Unbekannter OAuth-Fehler')
        return render(request, 'email_templates/oauth_error.html', {
            'error_message': f'{error}: {error_description}'
        })
    
    if not code:
        return render(request, 'email_templates/oauth_error.html', {
            'error_message': 'Kein Autorisierungscode erhalten. Möglicherweise wurde die Autorisierung abgebrochen.'
        })
    
    # Parse state to identify the connection
    connection = None
    if state and state.startswith('email_templates_'):
        try:
            connection_id = int(state.split('_')[2])
            connection = ZohoMailServerConnection.objects.get(id=connection_id)
        except (ValueError, ZohoMailServerConnection.DoesNotExist):
            pass
    
    # Fallback: find the most recent unconfigured connection or connection needing reauth
    if not connection:
        connection = ZohoMailServerConnection.objects.filter(
            Q(is_configured=False) | Q(access_token__isnull=True) | Q(needs_reauth=True)
        ).order_by('-created_at').first()
    
    if not connection:
        return render(request, 'email_templates/oauth_error.html', {
            'error_message': 'Keine Verbindung gefunden, die eine Autorisierung benötigt.'
        })
    
    try:
        zoho_service = ZohoMailService(connection)
        zoho_service.exchange_code_for_tokens(code)
        
        # Success - show success page that will auto-close
        return render(request, 'email_templates/oauth_success.html', {
            'connection': connection
        })
        
    except Exception as e:
        return render(request, 'email_templates/oauth_error.html', {
            'error_message': f'Token-Austausch fehlgeschlagen: {str(e)}'
        })


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def connection_test(request, pk):
    """Test Zoho mail connection"""
    connection = get_object_or_404(ZohoMailServerConnection, pk=pk)
    
    try:
        zoho_service = ZohoMailService(connection)
        result = zoho_service.test_connection()
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
            
    except Exception as e:
        messages.error(request, f'Verbindungstest fehlgeschlagen: {str(e)}')
    
    return redirect('email_templates:connection_detail', pk=pk)


# =============================================================================
# Email Template Views
# =============================================================================

@login_required
@user_passes_test(is_superuser)
def template_list(request):
    """List all email templates"""
    templates = EmailTemplate.objects.select_related('category', 'created_by').all()
    
    # Handle search and filters
    form = EmailTemplateSearchForm(request.GET)
    if form.is_valid():
        search = form.cleaned_data.get('search')
        category = form.cleaned_data.get('category')
        template_type = form.cleaned_data.get('template_type')
        is_active = form.cleaned_data.get('is_active')
        is_default = form.cleaned_data.get('is_default')
        
        if search:
            templates = templates.filter(
                Q(name__icontains=search) |
                Q(subject__icontains=search) |
                Q(html_content__icontains=search)
            )
        
        if category:
            templates = templates.filter(category=category)
            
        if template_type:
            templates = templates.filter(template_type=template_type)
            
        if is_active:
            templates = templates.filter(is_active=is_active == 'true')
            
        if is_default:
            templates = templates.filter(is_default=is_default == 'true')
    
    templates = templates.order_by('-is_default', 'category__order', 'name')
    
    # Pagination
    paginator = Paginator(templates, 12)
    page_number = request.GET.get('page')
    templates = paginator.get_page(page_number)
    
    return render(request, 'email_templates/templates/list.html', {
        'templates': templates,
        'search_form': form
    })


@login_required
@user_passes_test(is_superuser)
def template_create(request):
    """Create new email template"""
    if request.method == 'POST':
        form = EmailTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.last_modified_by = request.user
            template.save()
            
            # Create initial version
            EmailTemplateService.create_template_version(
                template, request.user, 'Initial version'
            )
            
            messages.success(request, f'Vorlage "{template.name}" wurde erstellt.')
            return redirect('email_templates:template_detail', pk=template.pk)
    else:
        form = EmailTemplateForm()
    
    return render(request, 'email_templates/templates/form.html', {
        'form': form,
        'title': 'Neue E-Mail-Vorlage'
    })


@login_required
@user_passes_test(is_superuser)
def template_detail(request, pk):
    """View template details"""
    template = get_object_or_404(
        EmailTemplate.objects.select_related('category', 'created_by', 'last_modified_by'),
        pk=pk
    )
    
    # Get recent send logs
    recent_logs = template.send_logs.select_related('connection', 'sent_by').order_by('-created_at')[:10]
    
    # Get versions
    versions = template.versions.select_related('created_by').order_by('-version_number')[:5]
    
    return render(request, 'email_templates/templates/detail.html', {
        'template': template,
        'recent_logs': recent_logs,
        'versions': versions
    })


@login_required
@user_passes_test(is_superuser)
def template_edit(request, pk):
    """Edit email template"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    if request.method == 'POST':
        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            # Create version before saving changes
            EmailTemplateService.create_template_version(
                template, request.user, 'Updated template'
            )
            
            template = form.save(commit=False)
            template.last_modified_by = request.user
            template.save()
            
            messages.success(request, f'Vorlage "{template.name}" wurde aktualisiert.')
            return redirect('email_templates:template_detail', pk=template.pk)
    else:
        form = EmailTemplateForm(instance=template)
    
    return render(request, 'email_templates/templates/form.html', {
        'form': form,
        'template': template,
        'title': f'Vorlage bearbeiten: {template.name}'
    })


@login_required
@user_passes_test(is_superuser)
def template_delete(request, pk):
    """Delete email template"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    if request.method == 'POST':
        name = template.name
        template.delete()
        messages.success(request, f'Vorlage "{name}" wurde gelöscht.')
        return redirect('email_templates:template_list')
    
    return render(request, 'email_templates/templates/delete.html', {
        'template': template
    })


@login_required
@user_passes_test(is_superuser)
def template_preview(request, pk):
    """Preview email template"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    # Get preview data from request
    preview_data = {}
    if request.method == 'POST':
        try:
            preview_data = json.loads(request.POST.get('preview_data', '{}'))
        except json.JSONDecodeError:
            messages.error(request, 'Ungültige Vorschau-Daten.')
    
    # Add default preview data if available_variables exist
    if template.available_variables and not preview_data:
        preview_data = {key: f"[{key}]" for key in template.available_variables.keys()}
    
    # Render template
    render_result = EmailTemplateService.render_template(template, preview_data)
    
    if not render_result['success']:
        messages.error(request, f'Vorlagen-Rendering fehlgeschlagen: {render_result["error"]}')
        return redirect('email_templates:template_detail', pk=pk)
    
    return render(request, 'email_templates/templates/preview.html', {
        'template': template,
        'rendered_subject': render_result['subject'],
        'rendered_html': render_result['html_content'],
        'rendered_text': render_result['text_content'],
        'preview_data': json.dumps(preview_data, indent=2) if preview_data else ''
    })


@login_required
@user_passes_test(is_superuser)
def send_test_email(request):
    """Send test email"""
    if request.method == 'POST':
        form = TestEmailForm(request.POST)
        if form.is_valid():
            template = form.cleaned_data['template']
            connection = form.cleaned_data['connection']
            recipient_email = form.cleaned_data['recipient_email']
            recipient_name = form.cleaned_data['recipient_name']
            test_data = form.cleaned_data['test_data']
            
            # Parse test data
            context_data = {}
            if test_data:
                try:
                    context_data = json.loads(test_data)
                except json.JSONDecodeError:
                    messages.error(request, 'Ungültige Test-Daten.')
                    return render(request, 'email_templates/test_email.html', {'form': form})
            
            # Send email
            result = EmailTemplateService.send_template_email(
                template=template,
                connection=connection,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                context_data=context_data,
                sent_by=request.user
            )
            
            if result['success']:
                messages.success(request, result['message'])
                return redirect('email_templates:dashboard')
            else:
                messages.error(request, result['message'])
    else:
        form = TestEmailForm()
    
    return render(request, 'email_templates/test_email.html', {'form': form})


# =============================================================================
# Category Views
# =============================================================================

@login_required
@user_passes_test(is_superuser)
def category_list(request):
    """List all template categories"""
    categories = EmailTemplateCategory.objects.all().order_by('order', 'name')
    return render(request, 'email_templates/categories/list.html', {
        'categories': categories
    })


@login_required
@user_passes_test(is_superuser)
def category_create(request):
    """Create new template category"""
    if request.method == 'POST':
        form = EmailTemplateCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Kategorie "{category.name}" wurde erstellt.')
            return redirect('email_templates:category_list')
    else:
        form = EmailTemplateCategoryForm()
    
    return render(request, 'email_templates/categories/form.html', {
        'form': form,
        'title': 'Neue Kategorie'
    })


@login_required
@user_passes_test(is_superuser)
def category_edit(request, pk):
    """Edit template category"""
    category = get_object_or_404(EmailTemplateCategory, pk=pk)
    
    if request.method == 'POST':
        form = EmailTemplateCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kategorie "{category.name}" wurde aktualisiert.')
            return redirect('email_templates:category_list')
    else:
        form = EmailTemplateCategoryForm(instance=category)
    
    return render(request, 'email_templates/categories/form.html', {
        'form': form,
        'category': category,
        'title': f'Kategorie bearbeiten: {category.name}'
    })


@login_required
@user_passes_test(is_superuser)
def category_delete(request, pk):
    """Delete template category"""
    category = get_object_or_404(EmailTemplateCategory, pk=pk)
    
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Kategorie "{name}" wurde gelöscht.')
        return redirect('email_templates:category_list')
    
    return render(request, 'email_templates/categories/delete.html', {
        'category': category
    })


# =============================================================================
# API Views
# =============================================================================

@login_required
@user_passes_test(is_superuser)
def api_template_variables(request, pk):
    """Get template variables as JSON"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    return JsonResponse(template.available_variables or {})


@login_required
@user_passes_test(is_superuser)
@csrf_exempt
def api_render_preview(request, pk):
    """Render template with given data"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    try:
        data = json.loads(request.body)
        context_data = data.get('context', {})
        
        result = EmailTemplateService.render_template(template, context_data)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'subject': result['subject'],
                'html_content': result['html_content'],
                'text_content': result['text_content']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
