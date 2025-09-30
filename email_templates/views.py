import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ZohoMailServerConnection, 
    EmailTemplateCategory, 
    EmailTemplate, 
    EmailSendLog,
    EmailTrigger
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
    
    # WICHTIG: Email-Templates verwendet jetzt SuperConfig!
    # Check SuperConfig email status instead of own connections
    from superconfig.models import EmailConfiguration
    superconfig_active = EmailConfiguration.objects.filter(is_active=True).exists()
    if superconfig_active:
        config = EmailConfiguration.objects.filter(is_active=True).first()
        total_connections = 1  # SuperConfig connection
        active_connections = 1 if config.smtp_host else 0
    else:
        total_connections = 0
        active_connections = 0
    
    # NEW: Trigger statistics
    total_triggers = EmailTrigger.objects.count()
    active_triggers = EmailTrigger.objects.filter(is_active=True).count()
    templates_with_triggers = EmailTemplate.objects.filter(trigger__isnull=False, is_active=True).count()
    templates_without_triggers = EmailTemplate.objects.filter(trigger__isnull=True, is_active=True).count()
    
    # Recent email logs
    recent_logs = EmailSendLog.objects.select_related(
        'template', 'connection'
    ).order_by('-created_at')[:10]
    
    # Trigger categories with counts
    trigger_categories = []
    for category_key, category_name in EmailTrigger.CATEGORY_CHOICES:
        trigger_count = EmailTrigger.objects.filter(category=category_key, is_active=True).count()
        if trigger_count > 0:
            trigger_categories.append({
                'key': category_key,
                'name': category_name,
                'count': trigger_count
            })
    
    context = {
        'total_templates': total_templates,
        'active_templates': active_templates,
        'total_connections': total_connections,
        'active_connections': active_connections,
        'total_triggers': total_triggers,
        'active_triggers': active_triggers,
        'templates_with_triggers': templates_with_triggers,
        'templates_without_triggers': templates_without_triggers,
        'trigger_categories': trigger_categories,
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
    templates = EmailTemplate.objects.select_related('category', 'created_by', 'trigger').all()
    
    # Handle search and filters
    form = EmailTemplateSearchForm(request.GET)
    trigger_filter = request.GET.get('trigger')
    has_trigger = request.GET.get('has_trigger')
    
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
                Q(html_content__icontains=search) |
                Q(trigger__name__icontains=search)
            )
        
        if category:
            templates = templates.filter(category=category)
            
        if template_type:
            templates = templates.filter(template_type=template_type)
            
        if is_active:
            templates = templates.filter(is_active=is_active == 'true')
            
        if is_default:
            templates = templates.filter(is_default=is_default == 'true')
    
    # NEW: Trigger filters
    if trigger_filter:
        templates = templates.filter(trigger_id=trigger_filter)
    
    if has_trigger == 'true':
        templates = templates.filter(trigger__isnull=False)
    elif has_trigger == 'false':
        templates = templates.filter(trigger__isnull=True)
    
    templates = templates.order_by('-is_default', 'category__order', 'name')
    
    # Pagination
    paginator = Paginator(templates, 12)
    page_number = request.GET.get('page')
    templates = paginator.get_page(page_number)
    
    # Get all triggers for filter dropdown
    all_triggers = EmailTrigger.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'email_templates/templates/list.html', {
        'templates': templates,
        'search_form': form,
        'all_triggers': all_triggers,
        'selected_trigger': trigger_filter,
        'selected_has_trigger': has_trigger,
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
    
    # Get available AI models for the current user
    from .ai_service import EmailAIService
    ai_service = EmailAIService(user=request.user)
    
    return render(request, 'email_templates/templates/form.html', {
        'form': form,
        'title': 'Neue E-Mail-Vorlage',
        'available_ai_models': ai_service.get_available_models(),
        'default_ai_model': ai_service.get_default_model()
    })


@login_required
@user_passes_test(is_superuser)
def template_detail(request, pk):
    """View template details"""
    template = get_object_or_404(
        EmailTemplate.objects.select_related('category', 'created_by', 'last_modified_by', 'trigger'),
        pk=pk
    )
    
    # Get recent send logs
    recent_logs = template.send_logs.select_related('connection', 'sent_by').order_by('-created_at')[:10]
    
    # Get versions
    versions = template.versions.select_related('created_by').order_by('-version_number')[:5]
    
    # Get available triggers for assignment
    available_triggers = EmailTrigger.objects.filter(is_active=True).order_by('category', 'name')
    
    return render(request, 'email_templates/templates/detail.html', {
        'template': template,
        'recent_logs': recent_logs,
        'versions': versions,
        'available_triggers': available_triggers,
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
    
    # Get available AI models for the current user
    from .ai_service import EmailAIService
    ai_service = EmailAIService(user=request.user)
    
    return render(request, 'email_templates/templates/form.html', {
        'form': form,
        'template': template,
        'title': f'Vorlage bearbeiten: {template.name}',
        'available_ai_models': ai_service.get_available_models(),
        'default_ai_model': ai_service.get_default_model()
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
        # Handle both dict and string cases
        if isinstance(template.available_variables, str):
            try:
                variables = json.loads(template.available_variables)
            except json.JSONDecodeError:
                variables = {}
        elif isinstance(template.available_variables, dict):
            variables = template.available_variables
        else:
            variables = {}

        # Generate meaningful demo data based on variable names
        preview_data = {}
        for key in variables.keys():
            # User-related variables
            if key in ['user_name', 'customer_name', 'recipient_name', 'name']:
                preview_data[key] = 'Max Mustermann'
            elif key in ['first_name', 'vorname']:
                preview_data[key] = 'Max'
            elif key in ['last_name', 'nachname']:
                preview_data[key] = 'Mustermann'
            elif key in ['email', 'recipient_email', 'user_email']:
                preview_data[key] = 'max.mustermann@example.com'

            # Site/Company variables
            elif key in ['site_name', 'company_name']:
                preview_data[key] = 'Workloom'
            elif key in ['domain', 'site_url']:
                preview_data[key] = request.get_host()

            # URLs and Links
            elif 'verification_url' in key or 'confirm_url' in key:
                preview_data[key] = f"http://{request.get_host()}/verify/demo-token-abc123xyz/"
            elif 'reset_url' in key or 'password_url' in key:
                preview_data[key] = f"http://{request.get_host()}/reset-password/demo-token-abc123xyz/"
            elif 'activation_url' in key:
                preview_data[key] = f"http://{request.get_host()}/activate/demo-token-abc123xyz/"
            elif 'login_url' in key:
                preview_data[key] = f"http://{request.get_host()}/login/"
            elif 'url' in key or 'link' in key:
                preview_data[key] = f"http://{request.get_host()}/demo-link/"

            # Dates and Times
            elif 'date' in key or 'datum' in key:
                preview_data[key] = timezone.now().strftime('%d.%m.%Y')
            elif 'time' in key or 'zeit' in key:
                preview_data[key] = timezone.now().strftime('%H:%M')
            elif 'datetime' in key:
                preview_data[key] = timezone.now().strftime('%d.%m.%Y %H:%M')

            # Amounts and Prices
            elif 'amount' in key or 'price' in key or 'total' in key:
                preview_data[key] = '€ 29,90'
            elif 'currency' in key:
                preview_data[key] = 'EUR'

            # Order related
            elif 'order_number' in key or 'order_id' in key:
                preview_data[key] = 'ORD-2024-001234'
            elif 'invoice_number' in key:
                preview_data[key] = 'RE-2024-001234'

            # File/Transfer related
            elif 'file_name' in key or 'filename' in key:
                preview_data[key] = 'beispiel-dokument.pdf'
            elif 'file_size' in key or 'filesize' in key:
                preview_data[key] = '2.5 MB'
            elif 'download_url' in key:
                preview_data[key] = f"http://{request.get_host()}/download/demo-transfer-abc123/"
            elif 'expires' in key or 'expiry' in key:
                preview_data[key] = (timezone.now() + timedelta(days=7)).strftime('%d.%m.%Y')

            # Contact/Support
            elif 'support_email' in key:
                preview_data[key] = 'support@workloom.de'
            elif 'phone' in key or 'telefon' in key:
                preview_data[key] = '+49 123 456789'

            # Messages and Content
            elif 'message' in key or 'nachricht' in key:
                preview_data[key] = 'Dies ist eine Beispielnachricht für die Vorschau.'
            elif 'subject' in key or 'betreff' in key:
                preview_data[key] = 'Beispiel-Betreff'
            elif 'description' in key or 'beschreibung' in key:
                preview_data[key] = 'Dies ist eine Beispielbeschreibung für die Vorschau.'

            # Generic fallback
            else:
                # Use variable description if available, otherwise use variable name
                var_description = variables.get(key, key)
                preview_data[key] = f"[Demo: {var_description}]"
    
    # Render template
    render_result = EmailTemplateService.render_template(template, preview_data)
    
    if not render_result['success']:
        messages.error(request, f'Vorlagen-Rendering fehlgeschlagen: {render_result["error"]}')
        return redirect('email_templates:template_detail', pk=pk)
    
    rendered_subject = render_result['subject'] or ''

    # Highlight trailing action keywords (e.g. "ERFORDERLICH") as badges instead of plain text
    subject_badge = None
    subject_display = rendered_subject
    badge_suffixes = {
        'ERFORDERLICH': 'Erforderlich',
    }
    for suffix, label in badge_suffixes.items():
        token = f' {suffix}'
        if subject_display.endswith(token):
            subject_display = subject_display[: -len(token)].rstrip()
            subject_badge = label
            break

    return render(request, 'email_templates/templates/preview.html', {
        'template': template,
        'rendered_subject': rendered_subject,
        'rendered_html': render_result['html_content'],
        'rendered_text': render_result['text_content'],
        'raw_text_content': template.text_content,
        'subject_display': subject_display,
        'subject_badge': subject_badge,
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
            # Connection nicht mehr aus Form - verwende dummy für compatibility
            connection = None  # SuperConfig wird automatisch verwendet
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
            
            # Send email via SuperConfig (connection wird ignoriert)
            result = EmailTemplateService.send_template_email(
                template=template,
                connection=connection,  # wird von send_template_email ignoriert
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


# =============================================================================
# Email Trigger Views
# =============================================================================

@login_required
@user_passes_test(is_superuser)
def trigger_list(request):
    """List all email triggers"""
    triggers = EmailTrigger.objects.all()
    
    # Handle search and filters
    search = request.GET.get('search')
    category = request.GET.get('category')
    is_active = request.GET.get('is_active')
    
    if search:
        triggers = triggers.filter(
            Q(name__icontains=search) |
            Q(trigger_key__icontains=search) |
            Q(description__icontains=search)
        )
    
    if category:
        triggers = triggers.filter(category=category)
    
    if is_active:
        triggers = triggers.filter(is_active=is_active == 'true')
    
    triggers = triggers.order_by('category', 'name')
    
    # Pagination
    paginator = Paginator(triggers, 15)
    page_number = request.GET.get('page')
    triggers = paginator.get_page(page_number)
    
    # Categories for filter
    categories = EmailTrigger.CATEGORY_CHOICES
    
    context = {
        'triggers': triggers,
        'categories': categories,
        'search': search,
        'selected_category': category,
        'selected_is_active': is_active,
    }
    
    return render(request, 'email_templates/triggers/list.html', context)


@login_required
@user_passes_test(is_superuser)
def trigger_detail(request, pk):
    """View trigger details"""
    trigger = get_object_or_404(EmailTrigger, pk=pk)
    
    # Get associated templates
    templates = trigger.templates.all().order_by('-is_active', 'name')
    
    # Get recent logs for this trigger's templates
    recent_logs = EmailSendLog.objects.filter(
        template__trigger=trigger
    ).select_related('template', 'connection', 'sent_by').order_by('-created_at')[:10]
    
    context = {
        'trigger': trigger,
        'templates': templates,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'email_templates/triggers/detail.html', context)


@login_required
@user_passes_test(is_superuser)
def trigger_create(request):
    """Create new email trigger"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            trigger_key = request.POST.get('trigger_key')
            description = request.POST.get('description')
            category = request.POST.get('category')
            is_active = request.POST.get('is_active') == 'on'
            
            # Parse available variables
            variables_json = request.POST.get('available_variables', '{}')
            try:
                available_variables = json.loads(variables_json)
            except json.JSONDecodeError:
                available_variables = {}
            
            trigger = EmailTrigger.objects.create(
                name=name,
                trigger_key=trigger_key,
                description=description,
                category=category,
                is_active=is_active,
                available_variables=available_variables,
                is_system_trigger=False  # User-created triggers are not system triggers
            )
            
            messages.success(request, f'Trigger "{trigger.name}" wurde erstellt.')
            return redirect('email_templates:trigger_detail', pk=trigger.pk)
            
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen des Triggers: {str(e)}')
    
    context = {
        'categories': EmailTrigger.CATEGORY_CHOICES,
        'title': 'Neuen Trigger erstellen'
    }
    
    return render(request, 'email_templates/triggers/form.html', context)


@login_required
@user_passes_test(is_superuser)
def trigger_edit(request, pk):
    """Edit email trigger"""
    trigger = get_object_or_404(EmailTrigger, pk=pk)
    
    # Prevent editing system triggers
    if trigger.is_system_trigger:
        messages.warning(request, 'System-Trigger können nicht bearbeitet werden.')
        return redirect('email_templates:trigger_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            trigger.name = request.POST.get('name')
            trigger.description = request.POST.get('description')
            trigger.category = request.POST.get('category')
            trigger.is_active = request.POST.get('is_active') == 'on'
            
            # Parse available variables
            variables_json = request.POST.get('available_variables', '{}')
            try:
                trigger.available_variables = json.loads(variables_json)
            except json.JSONDecodeError:
                trigger.available_variables = {}
            
            trigger.save()
            
            messages.success(request, f'Trigger "{trigger.name}" wurde aktualisiert.')
            return redirect('email_templates:trigger_detail', pk=trigger.pk)
            
        except Exception as e:
            messages.error(request, f'Fehler beim Aktualisieren des Triggers: {str(e)}')
    
    context = {
        'trigger': trigger,
        'categories': EmailTrigger.CATEGORY_CHOICES,
        'title': f'Trigger bearbeiten: {trigger.name}',
        'variables_json': json.dumps(trigger.available_variables, indent=2)
    }
    
    return render(request, 'email_templates/triggers/form.html', context)


@login_required
@user_passes_test(is_superuser)
def trigger_delete(request, pk):
    """Delete email trigger"""
    trigger = get_object_or_404(EmailTrigger, pk=pk)
    
    # Prevent deleting system triggers
    if trigger.is_system_trigger:
        messages.error(request, 'System-Trigger können nicht gelöscht werden.')
        return redirect('email_templates:trigger_detail', pk=pk)
    
    if request.method == 'POST':
        name = trigger.name
        trigger.delete()
        messages.success(request, f'Trigger "{name}" wurde gelöscht.')
        return redirect('email_templates:trigger_list')
    
    context = {
        'trigger': trigger
    }
    
    return render(request, 'email_templates/triggers/delete.html', context)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def trigger_test(request, pk):
    """Test email trigger by firing it with sample data"""
    trigger = get_object_or_404(EmailTrigger, pk=pk)
    
    try:
        from .trigger_manager import trigger_manager
        
        # Get test data from request
        test_email = request.POST.get('test_email', request.user.email)
        test_name = request.POST.get('test_name', request.user.get_full_name() or request.user.username)
        
        # Create sample context data based on available variables
        context_data = {}
        for var_key, var_description in trigger.available_variables.items():
            if var_key in ['user_name', 'customer_name', 'recipient_name']:
                context_data[var_key] = test_name
            elif var_key in ['email', 'recipient_email']:
                context_data[var_key] = test_email
            elif var_key == 'domain':
                context_data[var_key] = request.get_host()
            elif var_key == 'site_name':
                context_data[var_key] = 'Workloom'
            elif 'url' in var_key:
                context_data[var_key] = f"http://{request.get_host()}/test-link/"
            elif 'date' in var_key:
                from django.utils import timezone
                context_data[var_key] = timezone.now().strftime('%d.%m.%Y')
            elif 'amount' in var_key or 'price' in var_key:
                context_data[var_key] = '€ 29.90'
            else:
                context_data[var_key] = f'[Test {var_description}]'
        
        # Fire the trigger
        results = trigger_manager.fire_trigger(
            trigger_key=trigger.trigger_key,
            context_data=context_data,
            recipient_email=test_email,
            recipient_name=test_name
        )
        
        if results and any(result['success'] for result in results):
            successful_templates = [r['template'] for r in results if r['success']]
            messages.success(
                request, 
                f'Trigger "{trigger.name}" erfolgreich getestet. '
                f'E-Mails gesendet via Templates: {", ".join(successful_templates)}'
            )
        elif results:
            failed_templates = [r['template'] for r in results if not r['success']]
            messages.error(
                request,
                f'Trigger-Test fehlgeschlagen. Fehlerhafte Templates: {", ".join(failed_templates)}'
            )
        else:
            messages.warning(request, f'Keine aktiven Templates für Trigger "{trigger.name}" gefunden.')
    
    except Exception as e:
        messages.error(request, f'Fehler beim Testen des Triggers: {str(e)}')
    
    return redirect('email_templates:trigger_detail', pk=pk)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def sync_triggers(request):
    """Sync triggers from trigger manager to database"""
    try:
        from .trigger_manager import trigger_manager
        
        synced_count = trigger_manager.sync_triggers_to_database()
        messages.success(request, f'{synced_count} Trigger wurden synchronisiert.')
        
    except Exception as e:
        messages.error(request, f'Fehler beim Synchronisieren der Trigger: {str(e)}')
    
    return redirect('email_templates:trigger_list')


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def assign_template_trigger(request, template_pk):
    """Assign a trigger to a template"""
    template = get_object_or_404(EmailTemplate, pk=template_pk)
    
    trigger_id = request.POST.get('trigger_id')
    if trigger_id:
        try:
            trigger = EmailTrigger.objects.get(pk=trigger_id)
            template.trigger = trigger
            template.save()
            messages.success(request, f'Template "{template.name}" wurde dem Trigger "{trigger.name}" zugeordnet.')
        except EmailTrigger.DoesNotExist:
            messages.error(request, 'Trigger nicht gefunden.')
    else:
        # Remove trigger assignment
        template.trigger = None
        template.save()
        messages.success(request, f'Trigger-Zuordnung für Template "{template.name}" wurde entfernt.')
    
    return redirect('email_templates:template_detail', pk=template_pk)


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def generate_ai_content(request):
    """Generate email content using AI."""
    try:
        from .ai_service import EmailAIService
        
        # Parse request data
        data = json.loads(request.body)
        description = data.get('description', '').strip()
        email_type = data.get('email_type', 'general')
        tone = data.get('tone', 'professional')
        include_variables = data.get('include_variables', True)
        model = data.get('model', None)  # NEW: Get selected model
        
        if not description:
            return JsonResponse({
                'success': False,
                'error': 'E-Mail-Beschreibung ist erforderlich.'
            })
        
        # Create user-specific AI service instance
        ai_service = EmailAIService(user=request.user)
        
        # Generate content using AI service
        result = ai_service.generate_email_content(
            description=description,
            email_type=email_type,
            tone=tone,
            include_variables=include_variables,
            model=model
        )
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten erhalten.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unerwarteter Fehler: {str(e)}'
        })


@require_http_methods(["POST"])
@login_required
def html_to_text_view(request):
    """
    Convert HTML content to plain text
    """
    try:
        data = json.loads(request.body)
        html_content = data.get('html_content', '')

        if not html_content:
            return JsonResponse({
                'success': False,
                'error': 'Kein HTML-Inhalt angegeben.'
            })

        # Import the conversion function
        from .utils import html_to_text

        # Convert HTML to text
        text_content = html_to_text(html_content)

        return JsonResponse({
            'success': True,
            'text_content': text_content
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige JSON-Daten erhalten.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Fehler bei der Konvertierung: {str(e)}'
        })
