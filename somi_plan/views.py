from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from .models import PostingPlan, PostContent, Platform, PlanningSession, PostSchedule
from .services import SomiPlanAIService
import json


@login_required
def dashboard(request):
    """SoMi-Plan Dashboard"""
    from datetime import datetime, timedelta
    from django.db.models import Count, Q, Avg
    from django.utils import timezone
    
    user = request.user
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # Basis-Statistiken
    total_plans = PostingPlan.objects.filter(user=user).count()
    active_plans = PostingPlan.objects.filter(user=user, status='active')
    total_posts = PostContent.objects.filter(posting_plan__user=user).count()
    
    # Scheduled Posts Statistiken
    scheduled_posts = PostSchedule.objects.filter(post_content__posting_plan__user=user)
    upcoming_posts = scheduled_posts.filter(
        scheduled_date__gte=today,
        status='scheduled'
    ).order_by('scheduled_date', 'scheduled_time')[:8]
    
    completed_this_week = scheduled_posts.filter(
        scheduled_date__gte=week_start,
        scheduled_date__lt=today,
        status='completed'
    ).count()
    
    pending_today = scheduled_posts.filter(
        scheduled_date=today,
        status='scheduled'
    ).count()
    
    # Plattform-Verteilung
    platform_stats = PostingPlan.objects.filter(user=user).values(
        'platform__name', 'platform__icon', 'platform__color'
    ).annotate(
        plan_count=Count('id'),
        post_count=Count('posts'),
        scheduled_count=Count('posts__schedule', filter=Q(posts__schedule__status='scheduled'))
    ).order_by('-plan_count')
    
    # Wöchentliche Aktivität (letzte 4 Wochen)
    weekly_activity = []
    for i in range(4):
        week_start_date = week_start - timedelta(weeks=i)
        week_end_date = week_start_date + timedelta(days=6)
        
        week_posts = scheduled_posts.filter(
            scheduled_date__range=[week_start_date, week_end_date]
        ).count()
        
        weekly_activity.append({
            'week': f"KW {week_start_date.isocalendar()[1]}",
            'posts': week_posts,
            'start_date': week_start_date,
            'end_date': week_end_date
        })
    
    weekly_activity.reverse()  # Chronologische Reihenfolge
    
    # Content-Performance (Mock für jetzt)
    content_performance = []
    for content_type in ['tips', 'behind_scenes', 'motivational', 'product']:
        type_posts = PostContent.objects.filter(
            posting_plan__user=user,
            post_type=content_type
        )
        
        if type_posts.exists():
            content_performance.append({
                'type': content_type,
                'count': type_posts.count(),
                'scheduled': type_posts.filter(schedule__isnull=False).count(),
                'type_display': {
                    'tips': 'Tipps & Tricks',
                    'behind_scenes': 'Behind the Scenes',
                    'motivational': 'Motivation',
                    'product': 'Produkte'
                }.get(content_type, content_type.title())
            })
    
    # Neueste Pläne
    recent_plans = PostingPlan.objects.filter(user=user).order_by('-created_at')[:3]
    
    # Quick Actions basierend auf User-Status
    quick_actions = []
    
    if total_plans == 0:
        quick_actions.append({
            'title': 'Ersten Plan erstellen',
            'description': 'Starte mit deinem ersten Social Media Plan',
            'url': 'somi_plan:create_plan_step1',
            'icon': 'fas fa-plus-circle',
            'color': 'primary'
        })
    else:
        if pending_today > 0:
            quick_actions.append({
                'title': f'{pending_today} Posts heute',
                'description': 'Überprüfe deine heutigen Posts',
                'url': 'somi_plan:calendar',
                'icon': 'fas fa-calendar-day',
                'color': 'warning'
            })
        
        unscheduled_posts = PostContent.objects.filter(
            posting_plan__user=user,
            schedule__isnull=True
        ).count()
        
        if unscheduled_posts > 0:
            quick_actions.append({
                'title': f'{unscheduled_posts} Posts terminieren',
                'description': 'Plane deine unbeplanten Posts',
                'url': 'somi_plan:calendar',
                'icon': 'fas fa-clock',
                'color': 'info'
            })
        
        quick_actions.append({
            'title': 'Neuen Plan erstellen',
            'description': 'Weitere Plattform oder Kampagne',
            'url': 'somi_plan:create_plan_step1',
            'icon': 'fas fa-plus',
            'color': 'success'
        })
    
    context = {
        'total_plans': total_plans,
        'active_plans_count': active_plans.count(),
        'total_posts': total_posts,
        'upcoming_posts': upcoming_posts,
        'completed_this_week': completed_this_week,
        'pending_today': pending_today,
        'platform_stats': platform_stats,
        'weekly_activity': weekly_activity,
        'content_performance': content_performance,
        'recent_plans': recent_plans,
        'quick_actions': quick_actions,
        'active_plans': active_plans,
    }
    return render(request, 'somi_plan/dashboard.html', context)


@login_required
def plan_list(request):
    """Liste aller Posting-Pläne des Users"""
    plans = PostingPlan.objects.filter(user=request.user)
    paginator = Paginator(plans, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {'page_obj': page_obj}
    return render(request, 'somi_plan/plan_list.html', context)


@login_required
def create_plan_step1(request):
    """Schritt 1: Basis-Setup"""
    from .forms import Step1Form
    
    platforms = Platform.objects.filter(is_active=True)
    
    if request.method == 'POST':
        form = Step1Form(request.POST)
        if form.is_valid():
            # Create PostingPlan
            plan = form.save(commit=False)
            plan.user = request.user
            plan.save()
            
            # Create PlanningSession
            session = PlanningSession.objects.create(
                posting_plan=plan,
                current_step=2
            )
            session.complete_step(1)
            
            messages.success(request, f'✅ Plan "{plan.title}" wurde erstellt! Weiter zur Strategie-Entwicklung.')
            return redirect('somi_plan:create_plan_step2', plan_id=plan.id)
    else:
        form = Step1Form()
    
    context = {
        'form': form,
        'platforms': platforms
    }
    return render(request, 'somi_plan/create_step1.html', context)


@login_required
def create_plan_step2(request, plan_id):
    """Schritt 2: Strategie-Entwicklung"""
    from .forms import Step2StrategyForm
    
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    session = get_object_or_404(PlanningSession, posting_plan=plan)
    
    if request.method == 'POST':
        form = Step2StrategyForm(request.POST)
        if form.is_valid():
            use_ai = form.cleaned_data.get('use_ai_strategy', True)
            
            if use_ai:
                # Use AI to generate strategy
                ai_service = SomiPlanAIService(request.user)
                result = ai_service.generate_strategy(plan)
                
                if result['success']:
                    strategy_data = result['strategy_data']
                    # Override with form data if provided
                    if form.cleaned_data['posting_frequency']:
                        strategy_data['posting_frequency'] = form.cleaned_data['posting_frequency']
                    if form.cleaned_data['best_times']:
                        strategy_data['best_times'] = form.cleaned_data['best_times']
                    if form.cleaned_data['content_types']:
                        strategy_data['content_types'] = form.cleaned_data['content_types']
                    strategy_data['cross_platform'] = form.cleaned_data['cross_platform']
                    strategy_data['additional_notes'] = form.cleaned_data['additional_notes']
                    
                    messages.success(request, '🤖 KI hat eine optimale Strategie für dich erstellt!')
                else:
                    # Fallback to manual strategy
                    strategy_data = {
                        'posting_frequency': form.cleaned_data['posting_frequency'],
                        'best_times': form.cleaned_data['best_times'],
                        'content_types': form.cleaned_data['content_types'],
                        'cross_platform': form.cleaned_data['cross_platform'],
                        'additional_notes': form.cleaned_data['additional_notes'],
                        'ai_generated_at': timezone.now().isoformat(),
                        'fallback_used': True,
                        'ai_error': result.get('error', 'Unbekannter Fehler')
                    }
                    messages.warning(request, f'⚠️ KI-Strategiegenerierung fehlgeschlagen: {result.get("error", "Unbekannter Fehler")}. Manuelle Strategie wurde gespeichert.')
            else:
                # Manual strategy
                strategy_data = {
                    'posting_frequency': form.cleaned_data['posting_frequency'],
                    'best_times': form.cleaned_data['best_times'],
                    'content_types': form.cleaned_data['content_types'],
                    'cross_platform': form.cleaned_data['cross_platform'],
                    'additional_notes': form.cleaned_data['additional_notes'],
                    'ai_generated_at': timezone.now().isoformat(),
                    'manual_strategy': True
                }
            
            plan.strategy_data = strategy_data
            plan.save()
            
            # Update session
            session.current_step = 3
            session.complete_step(2)
            session.save()
            
            messages.success(request, '✅ Strategie wurde gespeichert! Jetzt werden die Content-Posts erstellt.')
            return redirect('somi_plan:create_plan_step3', plan_id=plan.id)
    else:
        form = Step2StrategyForm()
    
    context = {
        'plan': plan, 
        'form': form,
        'session': session
    }
    return render(request, 'somi_plan/create_step2.html', context)


@login_required
def create_plan_step3(request, plan_id):
    """Schritt 3: Content-Erstellung"""
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    session = get_object_or_404(PlanningSession, posting_plan=plan)
    posts = plan.posts.all()
    
    # Generate initial posts if none exist
    if not posts.exists() and plan.strategy_data:
        ai_service = SomiPlanAIService(request.user)
        result = ai_service.generate_posts(plan, count=5)
        
        if result['success']:
            posts = result['posts']
            messages.success(request, f'🤖 KI hat {result["count"]} Content-Posts für dich erstellt!')
        else:
            messages.warning(request, f'⚠️ Content-Generierung fehlgeschlagen: {result.get("error", "Unbekannter Fehler")}. Du kannst Posts manuell hinzufügen.')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate':
            plan.status = 'active'
            plan.save()
            
            session.current_step = 3
            session.complete_step(3)
            session.save()
            
            messages.success(request, f'🎉 Plan "{plan.title}" wurde aktiviert! Du kannst jetzt deine Posts terminieren.')
            return redirect('somi_plan:plan_detail', pk=plan.id)
            
        elif action == 'save_draft':
            plan.status = 'draft'
            plan.save()
            
            messages.success(request, f'✅ Plan "{plan.title}" wurde als Entwurf gespeichert.')
            return redirect('somi_plan:dashboard')
    
    context = {
        'plan': plan, 
        'posts': posts,
        'session': session
    }
    return render(request, 'somi_plan/create_step3.html', context)


@login_required
def plan_detail(request, pk):
    """Plan Detail-Ansicht"""
    plan = get_object_or_404(PostingPlan, pk=pk, user=request.user)
    posts = plan.posts.all()
    
    context = {'plan': plan, 'posts': posts}
    return render(request, 'somi_plan/plan_detail.html', context)


@login_required
def plan_edit(request, pk):
    """Plan bearbeiten"""
    plan = get_object_or_404(PostingPlan, pk=pk, user=request.user)
    # Placeholder
    return render(request, 'somi_plan/plan_edit.html', {'plan': plan})


@login_required
def plan_delete(request, pk):
    """Plan löschen"""
    plan = get_object_or_404(PostingPlan, pk=pk, user=request.user)
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Plan wurde erfolgreich gelöscht.')
        return redirect('somi_plan:dashboard')
    return render(request, 'somi_plan/plan_delete.html', {'plan': plan})


@login_required
def post_create(request, plan_id):
    """Neuen Post erstellen"""
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    
    if request.method == 'POST':
        try:
            # Extract form data
            topic = request.POST.get('topic', '').strip()
            post_type = request.POST.get('post_type', 'tips')
            ai_provider = request.POST.get('ai_provider', 'openai')
            ai_model = request.POST.get('ai_model', 'gpt-4o-mini')
            creativity_level = request.POST.get('creativity_level', 'balanced')
            priority = int(request.POST.get('priority', 2))
            
            # Content elements flags
            include_hashtags = request.POST.get('include_hashtags') == 'on'
            include_cta = request.POST.get('include_cta') == 'on'
            include_script = request.POST.get('include_script') == 'on'
            
            if not topic:
                return JsonResponse({
                    'success': False,
                    'error': 'Bitte gib ein Thema oder eine Richtung an.'
                })
            
            # Analyze existing posts to avoid repetition
            existing_posts = plan.postcontent_set.all()
            existing_content = []
            for post in existing_posts:
                existing_content.append({
                    'title': post.title,
                    'content': post.content[:200],  # First 200 chars
                    'hashtags': post.hashtags,
                    'post_type': post.post_type
                })
            
            # Initialize AI service
            ai_service = SomiPlanAIService(request.user)
            
            # Create comprehensive prompt for unique content generation
            creativity_prompts = {
                'conservative': 'Verwende bewährte, sichere Ansätze und bekannte Strukturen.',
                'balanced': 'Mische bewährte Ansätze mit einigen neuen, innovativen Ideen.',
                'creative': 'Sei kreativ und experimentiere mit neuen, ungewöhnlichen Ansätzen.',
                'experimental': 'Verwende sehr innovative, experimentelle Ansätze und neue Perspektiven.'
            }
            
            post_type_descriptions = {
                'tips': 'Praktische Tipps und nützliche Tricks',
                'behind_scenes': 'Einblicke hinter die Kulissen',
                'product': 'Produktvorstellungen und -präsentationen',
                'educational': 'Lehrreiche, bildende Inhalte',
                'motivational': 'Motivierende und inspirierende Posts',
                'testimonials': 'Kundenstimmen und Erfahrungsberichte',
                'news': 'Neuigkeiten und aktuelle Updates',
                'questions': 'Fragen zur Community-Interaktion'
            }
            
            prompt = f"""
Erstelle einen einzigartigen, spannenden Social Media Post für {plan.platform.name} basierend auf folgenden Vorgaben:

THEMA/RICHTUNG: {topic}

POST-TYP: {post_type_descriptions.get(post_type, post_type)}

KREATIVITÄTSLEVEL: {creativity_prompts.get(creativity_level, creativity_prompts['balanced'])}

WICHTIGE ANFORDERUNGEN:
- Zeichenlimit: {plan.platform.character_limit} Zeichen für den Hauptinhalt
- Der Post MUSS sich von bestehenden Posts unterscheiden
- Sei spannend und einzigartig, aber relevant zum Thema
- Berücksichtige die Zielgruppe von {plan.platform.name}

BESTEHENDE POSTS (NICHT WIEDERHOLEN):
{chr(10).join([f"- {post['title']}: {post['content'][:100]}..." for post in existing_content[-5:]])}

AUSGABE-FORMAT:
Erstelle einen JSON-Response mit folgenden Feldern:
{{
    "title": "Aussagekräftiger Titel (max. 100 Zeichen)",
    "content": "Hauptinhalt des Posts (max. {plan.platform.character_limit} Zeichen)",
    {"hashtags": "Relevante Hashtags mit # getrennt durch Leerzeichen"," if include_hashtags else ""}
    {"call_to_action": "Klare Handlungsaufforderung"," if include_cta else ""}
    {"script": "Detaillierte Umsetzungsanweisungen für den Post"" if include_script else ""}
}}

Der Content soll {creativity_level} sein und sich klar von den bestehenden Posts unterscheiden.
"""
            
            # Generate content using selected AI model
            system_prompt = f"Du bist ein kreativer Social Media Content-Experte für {plan.platform.name}. Erstelle einzigartige, ansprechende Posts die perfekt zur Plattform passen."
            
            if ai_provider == 'openai':
                result = ai_service._call_openai_api(system_prompt, prompt, model=ai_model)
            elif ai_provider == 'anthropic':
                result = ai_service._call_anthropic_api(system_prompt, prompt, model=ai_model)
            else:  # gemini
                result = ai_service._call_gemini_api(system_prompt, prompt)
            
            if not result.get('success'):
                return JsonResponse({
                    'success': False,
                    'error': f'AI-Fehler: {result.get("error", "Unbekannter Fehler")}'
                })
            
            # Parse AI response
            ai_content = result.get('content', '')
            try:
                # Try to extract JSON from AI response
                import re
                json_match = re.search(r'\{.*\}', ai_content, re.DOTALL)
                if json_match:
                    content_data = json.loads(json_match.group())
                else:
                    # Fallback: create structured content from AI response
                    content_data = {
                        'title': f'Neuer Post: {topic[:50]}...',
                        'content': ai_content[:plan.platform.character_limit],
                        'hashtags': '' if not include_hashtags else '#motivation #tips #inspiration',
                        'call_to_action': '' if not include_cta else 'Was denkst du darüber? Teile deine Meinung!',
                        'script': '' if not include_script else 'Post wie geplant veröffentlichen und auf Kommentare reagieren.'
                    }
            except json.JSONDecodeError:
                # Fallback parsing
                content_data = {
                    'title': f'KI-Post: {topic[:50]}',
                    'content': ai_content[:plan.platform.character_limit],
                    'hashtags': '' if not include_hashtags else '#ai #content #social',
                    'call_to_action': '' if not include_cta else 'Lass uns diskutieren!',
                    'script': '' if not include_script else 'Post veröffentlichen und Community einbinden.'
                }
            
            # Create new post
            new_post = PostContent.objects.create(
                posting_plan=plan,
                title=content_data.get('title', f'Neuer Post: {topic[:50]}'),
                content=content_data.get('content', ''),
                hashtags=content_data.get('hashtags', '') if include_hashtags else '',
                call_to_action=content_data.get('call_to_action', '') if include_cta else '',
                script=content_data.get('script', '') if include_script else '',
                post_type=post_type,
                priority=priority,
                ai_generated=True,
                ai_model_used=f"{ai_provider}:{ai_model}",
                character_count=len(content_data.get('content', ''))
            )
            
            return JsonResponse({
                'success': True,
                'redirect_url': f'/somi-plan/post/{new_post.pk}/edit/',
                'message': 'Post wurde erfolgreich erstellt!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Fehler bei der Post-Erstellung: {str(e)}'
            })
    
    return render(request, 'somi_plan/post_create.html', {'plan': plan})


@login_required
def post_detail(request, pk):
    """Post Detail-Ansicht"""
    post = get_object_or_404(PostContent, pk=pk, posting_plan__user=request.user)
    return render(request, 'somi_plan/post_detail.html', {'post': post})


@login_required
def post_edit(request, pk):
    """Post bearbeiten"""
    from .forms import PostContentForm
    
    post = get_object_or_404(PostContent, pk=pk, posting_plan__user=request.user)
    
    if request.method == 'POST':
        form = PostContentForm(request.POST, instance=post)
        if form.is_valid():
            # Update character count before saving
            updated_post = form.save(commit=False)
            updated_post.character_count = len(updated_post.content)
            updated_post.save()
            
            messages.success(request, f'✅ Post "{updated_post.title}" wurde erfolgreich aktualisiert.')
            return redirect('somi_plan:plan_detail', pk=post.posting_plan.pk)
    else:
        form = PostContentForm(instance=post)
    
    context = {
        'post': post,
        'form': form,
        'plan': post.posting_plan,
        'character_limit': post.posting_plan.platform.character_limit
    }
    return render(request, 'somi_plan/post_edit.html', context)


@login_required
def post_delete(request, pk):
    """Post löschen"""
    post = get_object_or_404(PostContent, pk=pk, posting_plan__user=request.user)
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Post wurde erfolgreich gelöscht.')
        return redirect('somi_plan:plan_detail', pk=post.posting_plan.pk)
    return render(request, 'somi_plan/post_delete.html', {'post': post})


@login_required
def calendar_view(request):
    """Kalender-Ansicht"""
    from datetime import datetime, timedelta
    from django.utils import timezone
    from calendar import monthrange
    
    # Aktueller Monat oder aus URL-Parameter
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Validierung
    if month < 1: 
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    
    # Kalender-Daten berechnen
    current_date = datetime(year, month, 1).date()
    days_in_month = monthrange(year, month)[1]
    first_day_weekday = current_date.weekday()  # 0=Montag, 6=Sonntag
    
    # Vorheriger und nächster Monat
    prev_month = current_date - timedelta(days=1)
    next_month = (current_date.replace(day=days_in_month) + timedelta(days=1))
    
    # Posts für diesen Monat laden
    start_date = current_date
    end_date = current_date.replace(day=days_in_month)
    
    scheduled_posts = PostSchedule.objects.filter(
        post_content__posting_plan__user=request.user,
        scheduled_date__range=[start_date, end_date]
    ).select_related('post_content', 'post_content__posting_plan', 'post_content__posting_plan__platform')
    
    # Posts für JavaScript-Rendering vorbereiten
    posts_data = []
    for post_schedule in scheduled_posts:
        post_data = {
            'id': post_schedule.post_content.id,
            'title': post_schedule.post_content.title,
            'content': post_schedule.post_content.content,
            'hashtags': post_schedule.post_content.hashtags,
            'call_to_action': post_schedule.post_content.call_to_action,
            'date': post_schedule.scheduled_date.strftime('%Y-%m-%d'),
            'time': post_schedule.scheduled_time.strftime('%H:%M') if post_schedule.scheduled_time else '12:00',
            'platform': post_schedule.post_content.posting_plan.platform.name,
            'platform_icon': post_schedule.post_content.posting_plan.platform.icon,
            'platform_color': post_schedule.post_content.posting_plan.platform.color,
        }
        posts_data.append(post_data)
    
    # Alle aktiven Pläne des Users
    active_plans = PostingPlan.objects.filter(
        user=request.user, 
        status__in=['active', 'draft']
    ).select_related('platform')
    
    context = {
        'current_date': current_date,
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
        'first_day_weekday': first_day_weekday,
        'prev_month': prev_month,
        'next_month': next_month,
        'posts_json': json.dumps(posts_data),
        'active_plans': active_plans,
        'today': today,
    }
    return render(request, 'somi_plan/calendar.html', context)


@login_required
def calendar_month(request, year, month):
    """Monats-Kalender"""
    # Placeholder - wird in Phase 4 implementiert
    return render(request, 'somi_plan/calendar_month.html')


@login_required
def schedule_post(request, post_id):
    """Post terminieren"""
    from .forms import PostScheduleForm
    
    post = get_object_or_404(PostContent, id=post_id, posting_plan__user=request.user)
    existing_schedule = getattr(post, 'schedule', None)
    
    if request.method == 'POST':
        form = PostScheduleForm(request.POST, instance=existing_schedule)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.post_content = post
            schedule.save()
            
            messages.success(request, f'✅ Post "{post.title}" wurde für {schedule.scheduled_date} um {schedule.scheduled_time} terminiert.')
            return redirect('somi_plan:calendar')
    else:
        form = PostScheduleForm(instance=existing_schedule)
    
    context = {
        'post': post,
        'form': form,
        'existing_schedule': existing_schedule
    }
    return render(request, 'somi_plan/schedule_post.html', context)


@login_required
def mark_completed(request, pk):
    """Post als erledigt markieren"""
    schedule = get_object_or_404(PostSchedule, pk=pk, post_content__posting_plan__user=request.user)
    if request.method == 'POST':
        url = request.POST.get('url', '')
        schedule.mark_completed(url)
        messages.success(request, 'Post wurde als erledigt markiert.')
    return redirect('somi_plan:calendar')


@login_required
def generate_more_ideas(request, plan_id):
    """Mehr kreative Ideen generieren"""
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    
    try:
        ai_service = SomiPlanAIService(request.user)
        existing_posts_count = plan.posts.count()
        result = ai_service.generate_more_ideas(plan, existing_posts_count)
        
        if result['success']:
            # Check if fallback was used
            message = f'{result["count"]} neue kreative Ideen wurden hinzugefügt!'
            if result.get('fallback_used'):
                message += ' (Fallback-Parser verwendet - Posts wurden erfolgreich erstellt trotz KI-Formatierungsproblem)'
            
            return JsonResponse({
                'status': 'success', 
                'message': message,
                'posts_count': result['count'],
                'fallback_used': result.get('fallback_used', False),
                'new_posts': [{
                    'id': post.id,
                    'title': post.title,
                    'content': post.content[:120] + '...',
                    'hashtags': post.hashtags,
                    'post_type': post.post_type,
                    'character_count': post.character_count
                } for post in result['posts']]
            })
        else:
            error_message = result.get("error", "Unbekannter Fehler")
            
            # More user-friendly error messages
            if "konnte nicht geparst werden" in error_message:
                user_message = "Die KI-Antwort war nicht im erwarteten Format. Bitte versuche es erneut oder kontaktiere den Support."
            elif "API-Key" in error_message:
                user_message = "Kein gültiger API-Schlüssel gefunden. Bitte konfiguriere deinen OpenAI oder Anthropic API-Key in den Einstellungen."
            elif "fehlgeschlagen" in error_message:
                user_message = "Die KI-Generierung ist fehlgeschlagen. Bitte versuche es in ein paar Minuten erneut."
            else:
                user_message = f"Fehler bei der Ideengenerierung: {error_message}"
            
            return JsonResponse({
                'status': 'error', 
                'message': user_message,
                'can_retry': True,
                'technical_error': error_message  # For debugging
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'Unerwarteter Fehler: {str(e)}'
        })


@login_required
def regenerate_strategy(request, plan_id):
    """Strategie neu generieren"""
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    
    try:
        ai_service = SomiPlanAIService(request.user)
        result = ai_service.generate_strategy(plan)
        
        if result['success']:
            # Keep additional_notes from current strategy if they exist
            if plan.strategy_data and 'additional_notes' in plan.strategy_data:
                result['strategy_data']['additional_notes'] = plan.strategy_data['additional_notes']
            
            plan.strategy_data = result['strategy_data']
            plan.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Strategie wurde erfolgreich neu generiert!',
                'strategy_data': result['strategy_data']
            })
        else:
            return JsonResponse({
                'status': 'error', 
                'message': f'Fehler bei der Strategiegenerierung: {result.get("error", "Unbekannter Fehler")}'
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'Unerwarteter Fehler: {str(e)}'
        })


@login_required
@require_POST
def ajax_toggle_schedule(request, pk):
    """AJAX: Post-Terminierung umschalten"""
    post = get_object_or_404(PostContent, pk=pk, posting_plan__user=request.user)
    
    try:
        if hasattr(post, 'schedule') and post.schedule:
            # Terminierung löschen
            post.schedule.delete()
            return JsonResponse({
                'status': 'success',
                'action': 'unscheduled',
                'message': 'Post-Terminierung wurde entfernt'
            })
        else:
            # Quick scheduling für heute 12:00
            from datetime import datetime, time
            from django.utils import timezone
            
            today = timezone.now().date()
            default_time = time(12, 0)
            
            schedule = PostSchedule.objects.create(
                post_content=post,
                scheduled_date=today,
                scheduled_time=default_time,
                status='scheduled'
            )
            
            return JsonResponse({
                'status': 'success',
                'action': 'scheduled',
                'message': f'Post wurde für heute 12:00 Uhr terminiert',
                'schedule_id': schedule.id,
                'date': today.isoformat(),
                'time': default_time.strftime('%H:%M')
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Fehler beim Terminieren: {str(e)}'
        })


@login_required
@require_POST
def ajax_save_session(request, plan_id):
    """AJAX: Session-Daten speichern"""
    plan = get_object_or_404(PostingPlan, id=plan_id, user=request.user)
    # Placeholder
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def ajax_update_position(request, pk):
    """AJAX: Post-Position im Kalender aktualisieren (Drag & Drop)"""
    import json
    from datetime import datetime
    
    post = get_object_or_404(PostContent, pk=pk, posting_plan__user=request.user)
    
    try:
        data = json.loads(request.body)
        new_date = data.get('date')
        new_time = data.get('time', '12:00')
        
        if not new_date:
            return JsonResponse({
                'status': 'error',
                'message': 'Datum ist erforderlich'
            })
        
        # Parse date
        try:
            scheduled_date = datetime.strptime(new_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Ungültiges Datumsformat'
            })
        
        # Parse time
        try:
            scheduled_time = datetime.strptime(new_time, '%H:%M').time()
        except ValueError:
            scheduled_time = datetime.strptime('12:00', '%H:%M').time()
        
        # Update oder erstelle Schedule
        schedule, created = PostSchedule.objects.get_or_create(
            post_content=post,
            defaults={
                'scheduled_date': scheduled_date,
                'scheduled_time': scheduled_time,
                'status': 'scheduled'
            }
        )
        
        if not created:
            schedule.scheduled_date = scheduled_date
            schedule.scheduled_time = scheduled_time
            schedule.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Post wurde auf {scheduled_date.strftime("%d.%m.%Y")} um {scheduled_time.strftime("%H:%M")} verschoben',
            'schedule_id': schedule.id,
            'date': scheduled_date.isoformat(),
            'time': scheduled_time.strftime('%H:%M')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Ungültige JSON-Daten'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Fehler beim Verschieben: {str(e)}'
        })


@login_required
def template_list(request):
    """Template-Liste"""
    # Placeholder
    return render(request, 'somi_plan/template_list.html')


@login_required
def template_category(request, category_id):
    """Templates einer Kategorie"""
    # Placeholder
    return render(request, 'somi_plan/template_category.html')


@login_required
def ajax_calendar_data(request, year, month):
    """AJAX: Lädt Kalender-Daten für einen bestimmten Monat"""
    from datetime import datetime
    from calendar import monthrange
    
    try:
        # Validierung
        if month < 1 or month > 12:
            return JsonResponse({'status': 'error', 'message': 'Ungültiger Monat'})
        
        current_date = datetime(year, month, 1).date()
        days_in_month = monthrange(year, month)[1]
        
        # Posts für diesen Monat laden
        start_date = current_date
        end_date = current_date.replace(day=days_in_month)
        
        scheduled_posts = PostSchedule.objects.filter(
            post_content__posting_plan__user=request.user,
            scheduled_date__range=[start_date, end_date]
        ).select_related('post_content', 'post_content__posting_plan', 'post_content__posting_plan__platform')
        
        # Posts nach Datum gruppieren
        posts_by_date = {}
        for post_schedule in scheduled_posts:
            date_str = post_schedule.scheduled_date.strftime('%Y-%m-%d')
            if date_str not in posts_by_date:
                posts_by_date[date_str] = []
            posts_by_date[date_str].append({
                'id': post_schedule.post_content.id,
                'schedule_id': post_schedule.id,
                'title': post_schedule.post_content.title,
                'time': post_schedule.scheduled_time.strftime('%H:%M'),
                'platform': {
                    'name': post_schedule.post_content.posting_plan.platform.name,
                    'icon': post_schedule.post_content.posting_plan.platform.icon,
                    'color': post_schedule.post_content.posting_plan.platform.color,
                },
                'status': post_schedule.status,
                'plan_title': post_schedule.post_content.posting_plan.title
            })
        
        return JsonResponse({
            'status': 'success',
            'year': year,
            'month': month,
            'days_in_month': days_in_month,
            'posts_by_date': posts_by_date
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Fehler beim Laden der Kalender-Daten: {str(e)}'
        })
