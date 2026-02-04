from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import IntegrityError
from django.core.serializers.json import DjangoJSONEncoder
import json
import io

# PDF Generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import PDFBook, PDFNote, TranslationHighlight, Vocabulary, ReadingProgress
from .services import PDFService, TranslationService
from core.models import StorageLog


# ============================================================================
# Page Views
# ============================================================================

@login_required
def index(request):
    """Kachelübersicht aller PDFs des Users"""
    books = PDFBook.objects.filter(user=request.user)

    # Statistiken
    total_books = books.count()
    total_vocabulary = Vocabulary.objects.filter(user=request.user).count()
    learned_vocabulary = Vocabulary.objects.filter(user=request.user, is_learned=True).count()

    context = {
        'books': books,
        'total_books': total_books,
        'total_vocabulary': total_vocabulary,
        'learned_vocabulary': learned_vocabulary,
    }
    return render(request, 'learnloom/index.html', context)


@login_required
def pdf_viewer(request, book_id):
    """PDF-Viewer Seite"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    # Letzten Zugriff aktualisieren
    book.last_opened_at = timezone.now()
    book.save(update_fields=['last_opened_at'])

    # Lesefortschritt laden oder erstellen
    progress, _ = ReadingProgress.objects.get_or_create(book=book)

    # Markierungen für alle Seiten laden
    highlights = TranslationHighlight.objects.filter(book=book)

    # Highlights als JSON serialisieren (UUIDs werden zu Strings konvertiert)
    highlights_list = []
    for h in highlights:
        highlights_list.append({
            'id': str(h.id),
            'original_text': h.original_text,
            'translated_text': h.translated_text,
            'page_number': h.page_number,
            'position_data': h.position_data,
        })

    highlights_json = json.dumps(highlights_list, cls=DjangoJSONEncoder)

    context = {
        'book': book,
        'progress': progress,
        'highlights_json': highlights_json,
    }
    return render(request, 'learnloom/pdf_viewer.html', context)


@login_required
def notes_view(request, book_id):
    """Standalone Notizen-Seite"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    notes = PDFNote.objects.filter(book=book)

    context = {
        'book': book,
        'notes': notes,
    }
    return render(request, 'learnloom/notes.html', context)


@login_required
def vocabulary_list(request, book_id):
    """Vokabelliste für ein PDF"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    vocabulary = Vocabulary.objects.filter(book=book)

    # Statistiken
    total = vocabulary.count()
    learned = vocabulary.filter(is_learned=True).count()

    context = {
        'book': book,
        'vocabulary': vocabulary,
        'total': total,
        'learned': learned,
    }
    return render(request, 'learnloom/vocabulary.html', context)


@login_required
def all_vocabulary(request):
    """Globale Vokabelliste - alle Vokabeln aus allen PDFs"""
    filter_status = request.GET.get('filter', 'all')

    vocabulary = Vocabulary.objects.filter(user=request.user).select_related('book')

    if filter_status == 'learned':
        vocabulary = vocabulary.filter(is_learned=True)
    elif filter_status == 'unlearned':
        vocabulary = vocabulary.filter(is_learned=False)

    # Statistiken
    total = Vocabulary.objects.filter(user=request.user).count()
    learned = Vocabulary.objects.filter(user=request.user, is_learned=True).count()

    # Gruppieren nach Buch
    books_with_vocab = {}
    for vocab in vocabulary:
        book_id = str(vocab.book.id)
        if book_id not in books_with_vocab:
            books_with_vocab[book_id] = {
                'book': vocab.book,
                'vocabulary': []
            }
        books_with_vocab[book_id]['vocabulary'].append(vocab)

    context = {
        'books_with_vocab': books_with_vocab.values(),
        'total': total,
        'learned': learned,
        'filter_status': filter_status,
    }
    return render(request, 'learnloom/all_vocabulary.html', context)


@login_required
def all_notes(request):
    """Globale Notizliste - alle Notizen sortiert nach PDF"""
    notes = PDFNote.objects.filter(user=request.user).select_related('book').order_by('book__title', '-updated_at')

    # Gruppieren nach Buch
    books_with_notes = {}
    for note in notes:
        book_id = str(note.book.id)
        if book_id not in books_with_notes:
            books_with_notes[book_id] = {
                'book': note.book,
                'notes': []
            }
        books_with_notes[book_id]['notes'].append(note)

    # Statistiken
    total_notes = notes.count()
    total_books = len(books_with_notes)

    context = {
        'books_with_notes': books_with_notes.values(),
        'total_notes': total_notes,
        'total_books': total_books,
    }
    return render(request, 'learnloom/all_notes.html', context)


# ============================================================================
# PDF API
# ============================================================================

@login_required
@require_POST
def api_upload_pdf(request):
    """PDF hochladen"""
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Keine Datei hochgeladen'}, status=400)

    pdf_file = request.FILES['file']

    # Prüfen ob es ein PDF ist
    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'success': False, 'error': 'Nur PDF-Dateien erlaubt'}, status=400)

    title = request.POST.get('title', pdf_file.name.rsplit('.', 1)[0])
    category = request.POST.get('category', 'book')
    tags = request.POST.get('tags', '')

    try:
        # PDF-Informationen extrahieren
        pdf_service = PDFService()
        page_count = pdf_service.get_page_count(pdf_file)
        pdf_file.seek(0)  # Reset file pointer

        # Thumbnail generieren
        thumbnail = pdf_service.generate_thumbnail(pdf_file)
        pdf_file.seek(0)  # Reset file pointer

        # Book erstellen
        book = PDFBook.objects.create(
            user=request.user,
            title=title,
            original_filename=pdf_file.name,
            file=pdf_file,
            file_size=pdf_file.size,
            page_count=page_count,
            category=category,
            tags=tags,
        )

        # Thumbnail speichern
        if thumbnail:
            book.thumbnail.save(f'{book.id}_thumb.png', thumbnail, save=True)

        # StorageLog erstellen
        StorageLog.objects.create(
            user=request.user,
            app_name='learnloom',
            action='upload',
            size_bytes=pdf_file.size,
            metadata={
                'filename': pdf_file.name,
                'book_id': str(book.id),
                'page_count': page_count,
            }
        )

        return JsonResponse({
            'success': True,
            'book': {
                'id': str(book.id),
                'title': book.title,
                'thumbnail_url': book.thumbnail.url if book.thumbnail else None,
                'page_count': book.page_count,
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_GET
def api_serve_pdf(request, book_id):
    """PDF für PDF.js bereitstellen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        response = FileResponse(book.file.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{book.original_filename}"'
        return response
    except FileNotFoundError:
        raise Http404("PDF nicht gefunden")


@login_required
@require_POST
def api_delete_pdf(request, book_id):
    """PDF löschen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    file_size = book.file_size
    filename = book.original_filename

    # Dateien löschen
    if book.file:
        book.file.delete(save=False)
    if book.thumbnail:
        book.thumbnail.delete(save=False)

    # StorageLog erstellen
    StorageLog.objects.create(
        user=request.user,
        app_name='learnloom',
        action='delete',
        size_bytes=file_size,
        metadata={
            'filename': filename,
            'book_id': str(book_id),
        }
    )

    book.delete()

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_update_metadata(request, book_id):
    """Metadaten eines PDFs aktualisieren"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    if 'title' in data:
        book.title = data['title']
    if 'category' in data:
        book.category = data['category']
    if 'tags' in data:
        book.tags = data['tags']

    book.save()

    return JsonResponse({'success': True})


@login_required
@require_POST
def api_update_reading_status(request, book_id):
    """Lesestatus eines PDFs aktualisieren"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    status = data.get('status')
    valid_statuses = ['unread', 'reading', 'completed']

    if status not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Ungültiger Status'}, status=400)

    book.reading_status = status
    book.save(update_fields=['reading_status'])

    # Status-Labels für Response
    status_labels = {
        'unread': 'Noch nicht gelesen',
        'reading': 'Gerade dabei',
        'completed': 'Bereits gelesen',
    }

    return JsonResponse({
        'success': True,
        'status': status,
        'status_label': status_labels[status]
    })


# ============================================================================
# Notes API
# ============================================================================

@login_required
@require_GET
def api_get_notes(request, book_id):
    """Notizen für ein PDF abrufen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    notes = PDFNote.objects.filter(book=book)

    return JsonResponse({
        'success': True,
        'notes': list(notes.values('id', 'content', 'page_reference', 'marker_position', 'created_at', 'updated_at'))
    })


@login_required
@require_POST
def api_save_note(request, book_id):
    """Notiz speichern oder aktualisieren"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    note_id = data.get('note_id')
    content = data.get('content', '').strip()
    page_reference = data.get('page_reference')
    marker_position = data.get('marker_position')

    if not content:
        return JsonResponse({'success': False, 'error': 'Inhalt darf nicht leer sein'}, status=400)

    if note_id:
        # Bestehende Notiz aktualisieren
        note = get_object_or_404(PDFNote, id=note_id, book=book, user=request.user)
        note.content = content
        note.page_reference = page_reference
        note.marker_position = marker_position
        note.save()
    else:
        # Neue Notiz erstellen
        note = PDFNote.objects.create(
            book=book,
            user=request.user,
            content=content,
            page_reference=page_reference,
            marker_position=marker_position,
        )

    return JsonResponse({
        'success': True,
        'note': {
            'id': str(note.id),
            'content': note.content,
            'page_reference': note.page_reference,
            'marker_position': note.marker_position,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat(),
        }
    })


@login_required
@require_POST
def api_delete_note(request, note_id):
    """Notiz löschen"""
    note = get_object_or_404(PDFNote, id=note_id, user=request.user)
    note.delete()
    return JsonResponse({'success': True})


# ============================================================================
# Translation API
# ============================================================================

@login_required
@require_POST
def api_translate(request):
    """Text übersetzen"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    text = data.get('text', '').strip()
    source_lang = data.get('source_lang', 'en')
    target_lang = data.get('target_lang', 'de')
    provider = data.get('provider', 'openai')

    if not text:
        return JsonResponse({'success': False, 'error': 'Text darf nicht leer sein'}, status=400)

    try:
        translation_service = TranslationService(request.user)
        translation = translation_service.translate(text, source_lang, target_lang, provider)

        return JsonResponse({
            'success': True,
            'translation': translation,
            'provider': provider,
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Übersetzungsfehler: {str(e)}'}, status=500)


@login_required
@require_GET
def api_get_highlights(request, book_id):
    """Markierungen für ein PDF abrufen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    page = request.GET.get('page')
    highlights = TranslationHighlight.objects.filter(book=book)

    if page:
        highlights = highlights.filter(page_number=int(page))

    return JsonResponse({
        'success': True,
        'highlights': list(highlights.values(
            'id', 'original_text', 'translated_text', 'page_number',
            'position_data', 'source_language', 'target_language', 'created_at'
        ))
    })


@login_required
@require_POST
def api_save_highlight(request, book_id):
    """Markierung speichern"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    original_text = data.get('original_text', '').strip()
    translated_text = data.get('translated_text', '').strip()
    page_number = data.get('page_number')
    position_data = data.get('position_data', {})
    source_language = data.get('source_language', 'en')
    target_language = data.get('target_language', 'de')
    provider = data.get('provider', 'openai')

    if not original_text or not translated_text or page_number is None:
        return JsonResponse({'success': False, 'error': 'Pflichtfelder fehlen'}, status=400)

    highlight = TranslationHighlight.objects.create(
        book=book,
        user=request.user,
        original_text=original_text,
        translated_text=translated_text,
        page_number=page_number,
        position_data=position_data,
        source_language=source_language,
        target_language=target_language,
        translation_provider=provider,
    )

    # Optional: Automatisch zur Vokabelliste hinzufügen
    add_to_vocabulary = data.get('add_to_vocabulary', True)
    vocab_entry = None

    if add_to_vocabulary:
        try:
            vocab_entry = Vocabulary.objects.create(
                book=book,
                user=request.user,
                english_word=original_text,
                german_translation=translated_text,
                from_highlight=highlight,
                page_reference=page_number,
            )
        except IntegrityError:
            # Vokabel existiert bereits
            pass

    return JsonResponse({
        'success': True,
        'highlight': {
            'id': str(highlight.id),
            'original_text': highlight.original_text,
            'translated_text': highlight.translated_text,
            'page_number': highlight.page_number,
        },
        'vocabulary_added': vocab_entry is not None,
    })


# ============================================================================
# Vocabulary API
# ============================================================================

@login_required
@require_GET
def api_get_vocabulary(request, book_id):
    """Vokabelliste für ein PDF abrufen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    vocabulary = Vocabulary.objects.filter(book=book)

    return JsonResponse({
        'success': True,
        'vocabulary': list(vocabulary.values(
            'id', 'english_word', 'german_translation', 'page_reference',
            'is_learned', 'times_reviewed', 'created_at'
        )),
        'total': vocabulary.count(),
        'learned': vocabulary.filter(is_learned=True).count(),
    })


@login_required
@require_POST
def api_add_vocabulary(request, book_id):
    """Vokabel manuell hinzufügen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    english_word = data.get('english_word', '').strip()
    german_translation = data.get('german_translation', '').strip()
    page_reference = data.get('page_reference')

    if not english_word or not german_translation:
        return JsonResponse({'success': False, 'error': 'Englisch und Deutsch sind Pflichtfelder'}, status=400)

    try:
        vocab = Vocabulary.objects.create(
            book=book,
            user=request.user,
            english_word=english_word,
            german_translation=german_translation,
            page_reference=page_reference,
        )

        return JsonResponse({
            'success': True,
            'vocabulary': {
                'id': str(vocab.id),
                'english_word': vocab.english_word,
                'german_translation': vocab.german_translation,
            }
        })
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Vokabel existiert bereits'}, status=400)


@login_required
@require_POST
def api_delete_vocabulary(request, vocab_id):
    """Vokabel löschen"""
    vocab = get_object_or_404(Vocabulary, id=vocab_id, user=request.user)
    vocab.delete()
    return JsonResponse({'success': True})


@login_required
@require_GET
def api_vocabulary_pdf(request, book_id):
    """Vokabelliste als PDF herunterladen (für ein Buch)"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    vocabulary = Vocabulary.objects.filter(book=book).order_by('english_word')

    # PDF erstellen
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    elements = []
    styles = getSampleStyleSheet()

    # Titel
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=1  # Center
    )
    elements.append(Paragraph(f"Vokabeln: {book.title}", title_style))
    elements.append(Spacer(1, 0.5*cm))

    # Statistik
    total = vocabulary.count()
    learned = vocabulary.filter(is_learned=True).count()
    stats_style = ParagraphStyle('Stats', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph(f"Gesamt: {total} | Gelernt: {learned} | Noch zu lernen: {total - learned}", stats_style))
    elements.append(Spacer(1, 0.5*cm))

    if vocabulary.exists():
        # Tabellen-Daten
        data = [['Englisch', 'Deutsch']]  # Header
        for vocab in vocabulary:
            data.append([vocab.english_word, vocab.german_translation])

        # Tabelle erstellen
        col_widths = [8*cm, 8*cm]
        table = Table(data, colWidths=col_widths, repeatRows=1)

        # Tabellen-Style mit Rahmen
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),

            # Rahmen für alle Zellen
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),

            # Abwechselnde Zeilenfarben
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),

            # Ausrichtung
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
    else:
        elements.append(Paragraph("Keine Vokabeln vorhanden.", styles['Normal']))

    # PDF generieren
    doc.build(elements)

    # Response
    buffer.seek(0)
    filename = f"vokabeln_{book.title[:30].replace(' ', '_')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_GET
def api_all_vocabulary_pdf(request):
    """Alle Vokabeln als PDF herunterladen"""
    vocabulary = Vocabulary.objects.filter(user=request.user).select_related('book').order_by('book__title', 'english_word')

    # PDF erstellen
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    elements = []
    styles = getSampleStyleSheet()

    # Titel
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=1
    )
    elements.append(Paragraph("Alle Vokabeln", title_style))
    elements.append(Spacer(1, 0.5*cm))

    # Statistik
    total = vocabulary.count()
    learned = vocabulary.filter(is_learned=True).count()
    stats_style = ParagraphStyle('Stats', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph(f"Gesamt: {total} | Gelernt: {learned} | Noch zu lernen: {total - learned}", stats_style))
    elements.append(Spacer(1, 0.5*cm))

    if vocabulary.exists():
        # Gruppieren nach Buch
        current_book = None
        book_vocab = []

        for vocab in vocabulary:
            if current_book != vocab.book:
                # Vorheriges Buch abschließen
                if current_book and book_vocab:
                    _add_vocabulary_table(elements, styles, current_book.title, book_vocab)
                    elements.append(Spacer(1, 0.8*cm))

                current_book = vocab.book
                book_vocab = []

            book_vocab.append(vocab)

        # Letztes Buch
        if current_book and book_vocab:
            _add_vocabulary_table(elements, styles, current_book.title, book_vocab)
    else:
        elements.append(Paragraph("Keine Vokabeln vorhanden.", styles['Normal']))

    # PDF generieren
    doc.build(elements)

    # Response
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="alle_vokabeln.pdf"'
    return response


def _add_vocabulary_table(elements, styles, book_title, vocabulary_list):
    """Hilfsfunktion: Fügt eine Vokabeltabelle für ein Buch hinzu"""
    # Buch-Titel
    book_style = ParagraphStyle(
        'BookTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=10,
        spaceAfter=10,
        textColor=colors.HexColor('#1f2937')
    )
    elements.append(Paragraph(f"📖 {book_title}", book_style))

    # Tabellen-Daten
    data = [['Englisch', 'Deutsch']]
    for vocab in vocabulary_list:
        data.append([vocab.english_word, vocab.german_translation])

    # Tabelle erstellen
    col_widths = [8*cm, 8*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # Rahmen
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),

        # Abwechselnde Farben
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),

        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)


# ============================================================================
# Progress API
# ============================================================================

@login_required
@require_GET
def api_get_progress(request, book_id):
    """Lesefortschritt abrufen"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)
    progress, _ = ReadingProgress.objects.get_or_create(book=book)

    return JsonResponse({
        'success': True,
        'progress': {
            'current_page': progress.current_page,
            'last_scroll_position': progress.last_scroll_position,
            'zoom_level': progress.zoom_level,
        }
    })


@login_required
@require_POST
def api_save_progress(request, book_id):
    """Lesefortschritt speichern"""
    book = get_object_or_404(PDFBook, id=book_id, user=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)

    progress, _ = ReadingProgress.objects.get_or_create(book=book)

    if 'current_page' in data:
        progress.current_page = data['current_page']
    if 'last_scroll_position' in data:
        progress.last_scroll_position = data['last_scroll_position']
    if 'zoom_level' in data:
        progress.zoom_level = data['zoom_level']

    progress.save()

    return JsonResponse({'success': True})
