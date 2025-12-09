from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import QuestionSearch, SavedQuestion
from .services.question_scraper import GoogleQuestionScraper
from .services.question_ai import QuestionAIService
import logging

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    QuestionFinder Dashboard - Hauptseite mit Suchformular
    """
    # Prüfe API-Key Verfügbarkeit
    ai_service = QuestionAIService(request.user)
    has_api_key = ai_service.has_api_key()

    # Letzte Suchen des Users
    recent_searches = QuestionSearch.objects.filter(
        user=request.user
    ).order_by('-search_date')[:10]

    # Gespeicherte Fragen
    saved_count = SavedQuestion.objects.filter(
        user=request.user,
        is_saved=True
    ).count()

    context = {
        'has_api_key': has_api_key,
        'recent_searches': recent_searches,
        'saved_count': saved_count,
        'page_title': 'QuestionFinder - Fragen aus Google extrahieren'
    }

    return render(request, 'questionfinder/dashboard.html', context)


@login_required
@require_POST
def search_questions(request):
    """
    AJAX Endpoint: Sucht und analysiert Fragen zu einem Keyword
    Quellen: Google Autocomplete, Reddit, Quora
    """
    keyword = request.POST.get('keyword', '').strip()

    if not keyword:
        return JsonResponse({
            'success': False,
            'error': 'Bitte gib ein Keyword ein'
        })

    # 1. Multi-Source Scraping (Google, Reddit, Quora)
    scraper = GoogleQuestionScraper()
    scrape_result = scraper.search_questions(keyword)

    if not scrape_result['success']:
        return JsonResponse(scrape_result)

    # paa_questions ist jetzt eine Liste von dicts: {'question': str, 'source': str}
    scraped_questions = scrape_result['paa_questions']
    sources_used = scrape_result.get('sources', [])

    # Extrahiere nur die Frage-Texte für KI-Kategorisierung
    question_texts = [q['question'] if isinstance(q, dict) else q for q in scraped_questions]

    # 2. KI-Kategorisierung (wenn API-Key vorhanden)
    ai_service = QuestionAIService(request.user)
    categorized_questions = []
    ai_generated = []

    if ai_service.has_api_key():
        # Gefundene Fragen kategorisieren
        if question_texts:
            cat_result = ai_service.categorize_questions(question_texts, keyword)
            if cat_result['success']:
                # Füge Source-Info zu kategorisierten Fragen hinzu
                categorized = cat_result['categorized']
                for i, cat_q in enumerate(categorized):
                    if i < len(scraped_questions):
                        orig = scraped_questions[i]
                        if isinstance(orig, dict):
                            cat_q['source'] = orig['source']
                        else:
                            cat_q['source'] = 'google'
                categorized_questions = categorized

        # Zusätzliche Fragen generieren
        gen_result = ai_service.generate_additional_questions(
            keyword,
            existing_questions=question_texts,
            count=10
        )
        if gen_result['success']:
            ai_generated = gen_result['questions']
    else:
        # Ohne KI: Nur Basis-Kategorisierung mit Source
        categorized_questions = []
        for q in scraped_questions:
            if isinstance(q, dict):
                categorized_questions.append({
                    'question': q['question'],
                    'intent': 'informational',
                    'category': 'Allgemein',
                    'source': q['source']
                })
            else:
                categorized_questions.append({
                    'question': q,
                    'intent': 'informational',
                    'category': 'Allgemein',
                    'source': 'google'
                })

    # Suche speichern
    search = QuestionSearch.objects.create(
        user=request.user,
        keyword=keyword,
        questions_found=len(categorized_questions),
        ai_questions_generated=len(ai_generated)
    )

    return JsonResponse({
        'success': True,
        'keyword': keyword,
        'search_id': search.id,
        'scraped_questions': categorized_questions,
        'ai_generated_questions': ai_generated,
        'total_found': len(categorized_questions),
        'total_generated': len(ai_generated),
        'sources_used': sources_used
    })


@login_required
@require_POST
def save_question(request):
    """
    AJAX Endpoint: Speichert eine Frage zur Merkliste
    """
    question = request.POST.get('question', '').strip()
    keyword = request.POST.get('keyword', '').strip()
    intent = request.POST.get('intent', 'informational')
    category = request.POST.get('category', '')
    source = request.POST.get('source', 'google_paa')
    search_id = request.POST.get('search_id')

    if not question:
        return JsonResponse({
            'success': False,
            'error': 'Frage darf nicht leer sein'
        })

    try:
        search = None
        if search_id:
            search = QuestionSearch.objects.filter(id=search_id, user=request.user).first()

        saved, created = SavedQuestion.objects.get_or_create(
            user=request.user,
            question=question,
            defaults={
                'keyword': keyword,
                'intent': intent,
                'category': category,
                'source': source,
                'search': search,
                'is_saved': True
            }
        )

        if not created:
            saved.is_saved = True
            saved.save()
            return JsonResponse({
                'success': True,
                'message': 'Frage war bereits gespeichert',
                'already_saved': True
            })

        return JsonResponse({
            'success': True,
            'message': 'Frage gespeichert',
            'question_id': saved.id
        })

    except Exception as e:
        logger.error(f"Error saving question: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Speichern: {str(e)}'
        })


@login_required
def saved_questions(request):
    """
    Ansicht: Alle gespeicherten Fragen
    """
    questions = SavedQuestion.objects.filter(
        user=request.user,
        is_saved=True
    ).order_by('intent', '-created_at')

    # Nach Intent gruppieren
    grouped = {
        'informational': [],
        'commercial': [],
        'transactional': [],
        'navigational': []
    }

    for q in questions:
        if q.intent in grouped:
            grouped[q.intent].append(q)

    context = {
        'grouped_questions': grouped,
        'total_count': questions.count(),
        'page_title': 'QuestionFinder - Gespeicherte Fragen'
    }

    return render(request, 'questionfinder/saved_questions.html', context)


@login_required
@require_POST
def delete_question(request, question_id):
    """
    AJAX Endpoint: Löscht eine gespeicherte Frage
    """
    question = get_object_or_404(SavedQuestion, id=question_id, user=request.user)

    try:
        question.delete()
        return JsonResponse({
            'success': True,
            'message': 'Frage gelöscht'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def toggle_used(request, question_id):
    """
    AJAX Endpoint: Markiert Frage als verwendet/unverwendet
    """
    question = get_object_or_404(SavedQuestion, id=question_id, user=request.user)

    question.is_used = not question.is_used
    question.save()

    return JsonResponse({
        'success': True,
        'is_used': question.is_used
    })
