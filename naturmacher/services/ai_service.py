import json
import requests
from django.conf import settings


def generate_html_content(user, prompt):
    """
    Generiert HTML/CSS Content basierend auf einem Text-Prompt
    """
    try:
        # Prüfe ob User einen API-Key hat - fallback zu Demo-Content
        if not user.openai_api_key and not user.anthropic_api_key:
            return generate_demo_content(prompt)
        
        # Erstelle System-Prompt für HTML/CSS Generierung
        system_prompt = """Du bist ein Experte für moderne Web-Entwicklung. Erstelle HTML und CSS Code basierend auf der Beschreibung des Users.

WICHTIGE REGELN:
1. Erstelle nur RESPONSIVEN, modernen Code
2. Verwende Bootstrap 5 Klassen wenn möglich
3. Inline CSS nur wenn nötig, sonst separate CSS
4. Verwende moderne CSS Features (Flexbox, Grid, etc.)
5. Achte auf Accessibility
6. Der Code muss in eine bestehende Bootstrap-Seite integrierbar sein
7. Verwende schöne Farben und moderne Designs
8. Font Awesome Icons sind verfügbar

ANTWORT FORMAT (JSON):
{
  "html": "Der HTML Code hier",
  "css": "Der CSS Code hier (ohne <style> Tags)",
  "description": "Kurze Beschreibung was erstellt wurde"
}"""

        user_prompt = f"""Erstelle einen HTML/CSS Block für folgende Beschreibung:

{prompt}

Der Code soll modern, responsiv und ansprechend sein. Verwende Bootstrap 5 Klassen und erstelle schöne, professionelle Designs."""

        errors = []
        
        # Versuche OpenAI zuerst
        if user.openai_api_key:
            result = call_openai_api(user.openai_api_key, system_prompt, user_prompt)
            if result['success']:
                return result
            else:
                errors.append(f"OpenAI: {result.get('error', 'Unbekannter Fehler')}")
        
        # Fallback zu Anthropic
        if user.anthropic_api_key:
            result = call_anthropic_api(user.anthropic_api_key, system_prompt, user_prompt)
            if result['success']:
                return result
            else:
                errors.append(f"Anthropic: {result.get('error', 'Unbekannter Fehler')}")
        
        if errors:
            error_details = " | ".join(errors)
            return {
                'success': False,
                'error': f'Alle KI-Services fehlgeschlagen: {error_details}'
            }
        else:
            return {
                'success': False,
                'error': 'Keine API-Keys konfiguriert'
            }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Fehler bei der KI-Generierung: {str(e)}'
        }


def generate_demo_content(prompt):
    """
    Generiert Demo-Content für Nutzer ohne API-Keys
    """
    import random
    
    # Demo-Inhalt basierend auf häufigen Prompt-Typen
    demo_templates = {
        'hero': {
            'html': '''<div class="hero-section text-center py-5 bg-primary text-white">
                <div class="container">
                    <h1 class="display-4 fw-bold mb-4">Willkommen bei unserem Service</h1>
                    <p class="lead mb-4">Entdecken Sie die Zukunft mit unseren innovativen Lösungen</p>
                    <button class="btn btn-light btn-lg">Jetzt starten</button>
                </div>
            </div>''',
            'css': '''.hero-section {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 60vh;
                display: flex;
                align-items: center;
            }'''
        },
        'feature': {
            'html': '''<div class="features-section py-5">
                <div class="container">
                    <div class="row">
                        <div class="col-md-4 text-center mb-4">
                            <div class="feature-icon mb-3">
                                <i class="fas fa-rocket fa-3x text-primary"></i>
                            </div>
                            <h4>Schnell</h4>
                            <p class="text-muted">Blitzschnelle Performance für optimale Nutzererfahrung</p>
                        </div>
                        <div class="col-md-4 text-center mb-4">
                            <div class="feature-icon mb-3">
                                <i class="fas fa-shield-alt fa-3x text-success"></i>
                            </div>
                            <h4>Sicher</h4>
                            <p class="text-muted">Höchste Sicherheitsstandards zum Schutz Ihrer Daten</p>
                        </div>
                        <div class="col-md-4 text-center mb-4">
                            <div class="feature-icon mb-3">
                                <i class="fas fa-heart fa-3x text-danger"></i>
                            </div>
                            <h4>Benutzerfreundlich</h4>
                            <p class="text-muted">Intuitive Bedienung für alle Nutzergruppen</p>
                        </div>
                    </div>
                </div>
            </div>''',
            'css': '''.feature-icon {
                transition: transform 0.3s ease;
            }
            .feature-icon:hover {
                transform: translateY(-10px);
            }'''
        },
        'testimonial': {
            'html': '''<div class="testimonial-section py-5 bg-light">
                <div class="container">
                    <div class="row justify-content-center">
                        <div class="col-lg-8 text-center">
                            <blockquote class="blockquote">
                                <p class="fs-4 mb-4">"Ein fantastischer Service, der unser Business transformiert hat!"</p>
                                <footer class="blockquote-footer">
                                    <cite title="Source Title">Maria Schmidt, CEO</cite>
                                </footer>
                            </blockquote>
                        </div>
                    </div>
                </div>
            </div>''',
            'css': '''.testimonial-section blockquote {
                border-left: 4px solid #667eea;
                padding-left: 1.5rem;
            }'''
        },
        'default': {
            'html': '''<div class="content-section py-4">
                <div class="container">
                    <div class="row">
                        <div class="col-lg-8 mx-auto">
                            <div class="card border-0 shadow-sm">
                                <div class="card-body p-4">
                                    <h3 class="card-title text-primary mb-3">Demo Content</h3>
                                    <p class="card-text">Dies ist ein Demo-Inhalt, da kein API-Key konfiguriert ist. Fügen Sie einen OpenAI oder Anthropic API-Key in Ihren Einstellungen hinzu, um echte KI-Generierung zu nutzen.</p>
                                    <div class="alert alert-info">
                                        <i class="fas fa-info-circle me-2"></i>
                                        <strong>Hinweis:</strong> Mit einem API-Key können Sie beliebige Inhalte per KI generieren lassen.
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>''',
            'css': '''.content-section .card {
                transition: transform 0.2s ease;
            }
            .content-section .card:hover {
                transform: translateY(-2px);
            }'''
        }
    }
    
    # Bestimme Template basierend auf Prompt-Keywords
    template_type = 'default'
    prompt_lower = prompt.lower()
    
    if any(word in prompt_lower for word in ['hero', 'header', 'titel', 'willkommen']):
        template_type = 'hero'
    elif any(word in prompt_lower for word in ['feature', 'eigenschaft', 'funktion', 'vorteil']):
        template_type = 'feature'
    elif any(word in prompt_lower for word in ['testimonial', 'bewertung', 'kundenstimme', 'referenz']):
        template_type = 'testimonial'
    
    selected_template = demo_templates[template_type]
    
    return {
        'success': True,
        'html': selected_template['html'],
        'css': selected_template['css'],
        'description': f'Demo-Inhalt generiert (Typ: {template_type}). Für echte KI-Generierung fügen Sie einen API-Key hinzu.',
        'is_demo': True
    }


def call_openai_api(api_key, system_prompt, user_prompt):
    """Ruft OpenAI API auf"""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Parse JSON response
            try:
                parsed = json.loads(content)
                return {
                    'success': True,
                    'html': parsed.get('html', ''),
                    'css': parsed.get('css', ''),
                    'description': parsed.get('description', '')
                }
            except json.JSONDecodeError:
                # Fallback: Extract HTML and CSS from text response
                return extract_html_css_from_text(content)
        else:
            error_text = response.text if response.text else 'Keine Antwort erhalten'
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {error_text}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'OpenAI API Aufruf fehlgeschlagen: {str(e)}'
        }


def call_anthropic_api(api_key, system_prompt, user_prompt):
    """Ruft Anthropic API auf"""
    try:
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-sonnet-20240229',
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': 2000
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            
            # Parse JSON response
            try:
                parsed = json.loads(content)
                return {
                    'success': True,
                    'html': parsed.get('html', ''),
                    'css': parsed.get('css', ''),
                    'description': parsed.get('description', '')
                }
            except json.JSONDecodeError:
                # Fallback: Extract HTML and CSS from text response
                return extract_html_css_from_text(content)
        else:
            error_text = response.text if response.text else 'Keine Antwort erhalten'
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {error_text}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Anthropic API Aufruf fehlgeschlagen: {str(e)}'
        }


def extract_html_css_from_text(text):
    """Extrahiert HTML und CSS aus Textantwort als Fallback"""
    try:
        html = ''
        css = ''
        
        # Suche nach HTML Code-Blöcken
        import re
        
        # HTML extrahieren
        html_match = re.search(r'```html\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if html_match:
            html = html_match.group(1).strip()
        else:
            # Fallback: Suche nach <div> oder anderen HTML Tags
            div_match = re.search(r'(<div.*?</div>)', text, re.DOTALL)
            if div_match:
                html = div_match.group(1)
        
        # CSS extrahieren
        css_match = re.search(r'```css\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if css_match:
            css = css_match.group(1).strip()
        else:
            # Fallback: Suche nach <style> Tags
            style_match = re.search(r'<style>(.*?)</style>', text, re.DOTALL)
            if style_match:
                css = style_match.group(1).strip()
        
        return {
            'success': True,
            'html': html,
            'css': css,
            'description': 'KI-generierter Content'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Fehler beim Extrahieren von HTML/CSS: {str(e)}'
        }


def generate_alt_text_with_ai(image_url, context_title, context_description, user, content_type='product'):
    """
    Generiert Alt-Text für Bilder mit KI-Unterstützung und echter Bildanalyse
    """
    try:
        # Prüfe ob User einen API-Key hat
        if not user.openai_api_key and not user.anthropic_api_key:
            return False, "", 'Kein API-Key für KI-Service gefunden. Bitte fügen Sie einen OpenAI oder Anthropic API-Key in Ihren Einstellungen hinzu.'
        
        # Erstelle Context-basiertes System-Prompt für Alt-Text-Generierung
        content_type_german = {
            'product': 'Produkt',
            'collection': 'Kategorie',
            'blog': 'Blog-Beitrag'
        }.get(content_type, 'Inhalt')
        
        system_prompt = f"""Du bist ein Experte für Barrierefreiheit und Alt-Text-Generierung. Analysiere das bereitgestellte Bild und erstelle einen beschreibenden Alt-Text.

WICHTIGE REGELN für Alt-Text:
1. Beschreibe WAS auf dem Bild zu sehen ist (nicht WIE es aussieht)
2. Halte es kurz und prägnant (maximal 125 Zeichen)
3. Verwende keine Phrasen wie "Bild von", "Foto von", "Abbildung zeigt"
4. Konzentriere dich auf die wichtigsten visuellen Inhalte
5. Berücksichtige den Kontext ({content_type_german})
6. Verwende eine natürliche, beschreibende Sprache
7. Integriere relevante Keywords natürlich
8. Fokussiere dich auf die Hauptelemente im Bild

ANTWORT FORMAT:
Gib nur den Alt-Text zurück, ohne weitere Erklärungen oder Formatierung."""

        user_prompt = f"""Analysiere dieses {content_type_german}-Bild und erstelle einen Alt-Text basierend auf dem was du siehst.

Kontext:
- Titel: {context_title}
- Beschreibung: {context_description}

Erstelle einen präzisen, beschreibenden Alt-Text von maximal 125 Zeichen basierend auf dem Bildinhalt."""

        # Versuche OpenAI Vision zuerst (falls Bild-URL vorhanden)
        if user.openai_api_key and image_url:
            result = call_openai_vision_api(user.openai_api_key, system_prompt, user_prompt, image_url)
            if result['success']:
                alt_text = result['content'].strip()
                # Kürze auf maximal 125 Zeichen
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + "..."
                return True, alt_text, "Alt-Text erfolgreich mit Bildanalyse generiert"
        
        # Fallback zu Anthropic Vision
        if user.anthropic_api_key and image_url:
            result = call_anthropic_vision_api(user.anthropic_api_key, system_prompt, user_prompt, image_url)
            if result['success']:
                alt_text = result['content'].strip()
                # Kürze auf maximal 125 Zeichen
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + "..."
                return True, alt_text, "Alt-Text erfolgreich mit Bildanalyse generiert"
        
        # Fallback zu textbasierter Generierung
        if user.openai_api_key:
            result = call_openai_api_for_text(user.openai_api_key, system_prompt, user_prompt)
            if result['success']:
                alt_text = result['content'].strip()
                if len(alt_text) > 125:
                    alt_text = alt_text[:122] + "..."
                return True, alt_text, "Alt-Text erfolgreich generiert (ohne Bildanalyse)"
        
        return False, "", "Keine gültige KI-Antwort erhalten"
        
    except Exception as e:
        return False, "", f'KI-Alt-Text-Generierung fehlgeschlagen: {str(e)}'


def call_openai_api_for_text(api_key, system_prompt, user_prompt):
    """Ruft OpenAI API für reine Textgenerierung auf"""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 200  # Weniger Tokens für Alt-Text
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return {
                'success': True,
                'content': content
            }
        else:
            return {
                'success': False,
                'error': f'OpenAI API Fehler: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'OpenAI API Aufruf fehlgeschlagen: {str(e)}'
        }


def call_anthropic_api_for_text(api_key, system_prompt, user_prompt):
    """Ruft Anthropic API für reine Textgenerierung auf"""
    try:
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-sonnet-20240229',
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': 200  # Weniger Tokens für Alt-Text
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            
            return {
                'success': True,
                'content': content
            }
        else:
            return {
                'success': False,
                'error': f'Anthropic API Fehler: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Anthropic API Aufruf fehlgeschlagen: {str(e)}'
        }


def call_openai_vision_api(api_key, system_prompt, user_prompt, image_url):
    """Ruft OpenAI Vision API für Bildanalyse auf"""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o-mini',  # GPT-4o-mini hat Vision-Capabilities
            'messages': [
                {
                    'role': 'system', 
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': user_prompt
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': image_url,
                                'detail': 'low'  # Kostengünstiger für Alt-Text
                            }
                        }
                    ]
                }
            ],
            'temperature': 0.7,
            'max_tokens': 200
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=60  # Längere Timeout für Bildanalyse
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return {
                'success': True,
                'content': content
            }
        else:
            return {
                'success': False,
                'error': f'OpenAI Vision API Fehler: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'OpenAI Vision API Aufruf fehlgeschlagen: {str(e)}'
        }


def call_anthropic_vision_api(api_key, system_prompt, user_prompt, image_url):
    """Ruft Anthropic Vision API für Bildanalyse auf"""
    try:
        import base64
        import io
        from PIL import Image
        
        # Lade das Bild
        img_response = requests.get(image_url, timeout=30)
        if img_response.status_code != 200:
            return {
                'success': False,
                'error': f'Fehler beim Laden des Bildes: {img_response.status_code}'
            }
        
        # Konvertiere zu Base64
        img = Image.open(io.BytesIO(img_response.content))
        # Resize für Effizienz
        img.thumbnail((1024, 1024))
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-sonnet-20240229',
            'system': system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': user_prompt
                        },
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': 'image/png',
                                'data': img_b64
                            }
                        }
                    ]
                }
            ],
            'max_tokens': 200
        }
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['content'][0]['text']
            
            return {
                'success': True,
                'content': content
            }
        else:
            return {
                'success': False,
                'error': f'Anthropic Vision API Fehler: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Anthropic Vision API Aufruf fehlgeschlagen: {str(e)}'
        }