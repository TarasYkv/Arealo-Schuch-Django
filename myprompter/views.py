from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PrompterText
import json


@login_required
def teleprompter_view(request):
    """Main teleprompter view"""
    saved_texts = PrompterText.objects.filter(user=request.user)
    context = {
        'saved_texts': saved_texts,
        'page_title': 'MyPrompter - Teleprompter mit Spracherkennung',
        'page_description': 'Professioneller Teleprompter mit Echtzeit-Spracherkennung',
    }
    return render(request, 'myprompter/teleprompter.html', context)


@login_required
def saved_texts_view(request):
    """View for managing saved texts"""
    saved_texts = PrompterText.objects.filter(user=request.user)
    context = {
        'saved_texts': saved_texts,
        'page_title': 'Gespeicherte Texte - MyPrompter',
    }
    return render(request, 'myprompter/saved_texts.html', context)


@login_required
@require_POST
def save_text(request):
    """Save a new teleprompter text"""
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()

        if not title or not content:
            return JsonResponse({
                'success': False,
                'error': 'Titel und Inhalt sind erforderlich.'
            }, status=400)

        text = PrompterText.objects.create(
            user=request.user,
            title=title,
            content=content
        )

        return JsonResponse({
            'success': True,
            'text_id': text.id,
            'message': 'Text erfolgreich gespeichert.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_text(request, text_id):
    """Update an existing teleprompter text"""
    try:
        text = get_object_or_404(PrompterText, id=text_id, user=request.user)
        data = json.loads(request.body)

        title = data.get('title', '').strip()
        content = data.get('content', '').strip()

        if not title or not content:
            return JsonResponse({
                'success': False,
                'error': 'Titel und Inhalt sind erforderlich.'
            }, status=400)

        text.title = title
        text.content = content
        text.save()

        return JsonResponse({
            'success': True,
            'message': 'Text erfolgreich aktualisiert.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def delete_text(request, text_id):
    """Delete a teleprompter text"""
    try:
        text = get_object_or_404(PrompterText, id=text_id, user=request.user)
        text.delete()

        return JsonResponse({
            'success': True,
            'message': 'Text erfolgreich gelöscht.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def toggle_favorite(request, text_id):
    """Toggle favorite status of a text"""
    try:
        text = get_object_or_404(PrompterText, id=text_id, user=request.user)
        text.is_favorite = not text.is_favorite
        text.save()

        return JsonResponse({
            'success': True,
            'is_favorite': text.is_favorite,
            'message': 'Favoriten-Status aktualisiert.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_text(request, text_id):
    """Get a specific text as JSON"""
    try:
        text = get_object_or_404(PrompterText, id=text_id, user=request.user)
        return JsonResponse({
            'success': True,
            'text': {
                'id': text.id,
                'title': text.title,
                'content': text.content,
                'is_favorite': text.is_favorite,
                'word_count': text.word_count,
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
