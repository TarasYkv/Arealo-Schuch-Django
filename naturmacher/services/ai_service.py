import json
import requests
from django.conf import settings


def generate_html_content(user, prompt):
    """
    Generiert HTML/CSS Content basierend auf einem Text-Prompt
    """
    try:
        # Prüfe ob User einen API-Key hat
        if not user.openai_api_key and not user.anthropic_api_key:
            return {
                'success': False,
                'error': 'Kein API-Key für KI-Service gefunden. Bitte fügen Sie einen OpenAI oder Anthropic API-Key in Ihren Einstellungen hinzu.'
            }
        
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

        # Versuche OpenAI zuerst
        if user.openai_api_key:
            result = call_openai_api(user.openai_api_key, system_prompt, user_prompt)
            if result['success']:
                return result
        
        # Fallback zu Anthropic
        if user.anthropic_api_key:
            result = call_anthropic_api(user.anthropic_api_key, system_prompt, user_prompt)
            if result['success']:
                return result
        
        return {
            'success': False,
            'error': 'Alle KI-Services fehlgeschlagen'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Fehler bei der KI-Generierung: {str(e)}'
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
            return {
                'success': False,
                'error': f'OpenAI API Fehler: {response.status_code}'
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
            return {
                'success': False,
                'error': f'Anthropic API Fehler: {response.status_code}'
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