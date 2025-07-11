"""
KI-Service für SEO-Optimierung
Unterstützt verschiedene AI-Modelle zur Generierung von SEO-optimierten Titeln und Beschreibungen
"""

import json
import requests
from typing import Dict, Tuple, Optional
from django.conf import settings


class AIService:
    """Basis-Klasse für AI-Services"""
    
    def generate_seo(self, product_title: str, product_description: str, keywords: list) -> Tuple[bool, Dict, str]:
        """
        Generiert SEO-Titel und -Beschreibung
        
        Returns:
            (success, {'seo_title': str, 'seo_description': str}, message)
        """
        raise NotImplementedError


class OpenAIService(AIService):
    """OpenAI GPT-basierter SEO-Service"""
    
    def __init__(self, model: str = "gpt-4", user=None):
        self.model = model
        self.user = user
        
        # Versuche API-Key aus verschiedenen Quellen zu holen
        self.api_key = self._get_api_key()
        if not self.api_key:
            raise ValueError("OpenAI API-Key nicht verfügbar. Bitte in den API-Einstellungen konfigurieren.")
    
    def _get_api_key(self):
        """Holt API-Key aus verschiedenen Quellen"""
        try:
            # 1. Aus Benutzer-API-Einstellungen (bevorzugt)
            if self.user and self.user.is_authenticated:
                from naturmacher.utils.api_helpers import get_user_api_key
                user_key = get_user_api_key(self.user, 'openai')
                if user_key:
                    return user_key
            
            # 2. Fallback zu gemeinsamer Hilfsfunktion
            from naturmacher.utils.api_helpers import get_env_api_key
            return get_env_api_key('openai')
                
        except ImportError:
            # Falls naturmacher.utils.api_helpers nicht verfügbar
            pass
        except Exception as e:
            print(f"Fehler beim API-Key Abruf: {e}")
        
        return None
    
    def generate_seo(self, product_title: str, product_description: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_prompt(product_title, product_description, keywords)
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'Du bist ein SEO-Experte. Erstelle optimierte SEO-Titel und -Beschreibungen für E-Commerce-Produkte. Verwende die "du"-Form für eine persönliche Ansprache. Antworte immer im JSON-Format.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'temperature': 0.7,
                    'max_tokens': 300
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                # Parse JSON response (remove markdown code blocks if present)
                try:
                    # Entferne Markdown-Code-Blöcke falls vorhanden
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```json'):
                        cleaned_content = cleaned_content[7:]  # Entferne ```json
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]  # Entferne ```
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]  # Entferne ```
                    cleaned_content = cleaned_content.strip()
                    
                    result = json.loads(cleaned_content)
                    return True, {
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'seo_title': result.get('seo_title', '')[:70],  # Limit zu 70 Zeichen
                        'seo_description': result.get('seo_description', '')[:160]  # Limit zu 160 Zeichen
                    }, "SEO-Inhalte erfolgreich generiert"
                except json.JSONDecodeError:
                    return False, {}, f"Ungültige JSON-Antwort: {content}"
            else:
                return False, {}, f"OpenAI API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei OpenAI-Request: {str(e)}"
    
    def _build_prompt(self, title: str, description: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        return f"""
Erstelle für folgendes Produkt einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Produkttitel:** {title}

**Produktbeschreibung:** {description[:500]}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- Titel: Optimierter Haupttitel für das Produkt, keyword-optimiert, ansprechend
- Beschreibung: Optimierte Produktbeschreibung, verkaufsfördernd, detailliert
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, ansprechend
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, verkaufsfördernd
- Natürlich wirkende Integration der Keywords
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"

**Antwortformat (nur JSON):**
{{
    "title": "Der optimierte Haupttitel hier",
    "description": "Die optimierte Hauptbeschreibung hier",
    "seo_title": "Der optimierte SEO-Titel hier",
    "seo_description": "Die optimierte SEO-Beschreibung hier"
}}
"""


class ClaudeService(AIService):
    """Anthropic Claude-basierter SEO-Service"""
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022", user=None):
        self.model = model
        self.user = user
        
        # Versuche API-Key aus verschiedenen Quellen zu holen
        self.api_key = self._get_api_key()
        if not self.api_key:
            raise ValueError("Anthropic API-Key nicht verfügbar. Bitte in den API-Einstellungen konfigurieren.")
    
    def _get_api_key(self):
        """Holt API-Key aus verschiedenen Quellen"""
        try:
            # 1. Aus Benutzer-API-Einstellungen (bevorzugt)
            if self.user and self.user.is_authenticated:
                from naturmacher.utils.api_helpers import get_user_api_key
                user_key = get_user_api_key(self.user, 'anthropic')
                if user_key:
                    return user_key
            
            # 2. Fallback zu gemeinsamer Hilfsfunktion
            from naturmacher.utils.api_helpers import get_env_api_key
            return get_env_api_key('anthropic')
                
        except ImportError:
            # Falls naturmacher.utils.api_helpers nicht verfügbar
            pass
        except Exception as e:
            print(f"Fehler beim API-Key Abruf: {e}")
        
        return None
    
    def generate_seo(self, product_title: str, product_description: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_prompt(product_title, product_description, keywords)
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': self.model,
                    'max_tokens': 300,
                    'messages': [
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['content'][0]['text']
                
                # Parse JSON response (remove markdown code blocks if present)
                try:
                    # Entferne Markdown-Code-Blöcke falls vorhanden
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```json'):
                        cleaned_content = cleaned_content[7:]  # Entferne ```json
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]  # Entferne ```
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]  # Entferne ```
                    cleaned_content = cleaned_content.strip()
                    
                    result = json.loads(cleaned_content)
                    return True, {
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'seo_title': result.get('seo_title', '')[:70],
                        'seo_description': result.get('seo_description', '')[:160]
                    }, "SEO-Inhalte erfolgreich generiert"
                except json.JSONDecodeError:
                    return False, {}, f"Ungültige JSON-Antwort: {content}"
            else:
                return False, {}, f"Claude API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei Claude-Request: {str(e)}"
    
    def _build_prompt(self, title: str, description: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        return f"""
Du bist ein SEO-Experte. Erstelle für folgendes E-Commerce-Produkt einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Produkttitel:** {title}

**Produktbeschreibung:** {description[:500]}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, ansprechend für Suchmaschinen
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, verkaufsfördernd
- Natürliche Integration der Keywords (kein Keyword-Stuffing)
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"
- Fokus auf Conversion-Optimierung

Antworte nur mit validem JSON in folgendem Format:
{{
    "title": "Der optimierte Haupttitel hier",
    "description": "Die optimierte Hauptbeschreibung hier",
    "seo_title": "Der optimierte SEO-Titel hier",
    "seo_description": "Die optimierte SEO-Beschreibung hier"
}}
"""


class GeminiService(AIService):
    """Google Gemini-basierter SEO-Service"""
    
    def __init__(self, model: str = "gemini-1.5-flash", user=None):
        self.model = model
        self.user = user
        
        # Versuche API-Key aus verschiedenen Quellen zu holen
        self.api_key = self._get_api_key()
        if not self.api_key:
            raise ValueError("Google Gemini API-Key nicht verfügbar. Bitte in den API-Einstellungen konfigurieren.")
    
    def _get_api_key(self):
        """Holt API-Key aus verschiedenen Quellen"""
        try:
            # 1. Aus Benutzer-API-Einstellungen (bevorzugt)
            if self.user and self.user.is_authenticated:
                from naturmacher.utils.api_helpers import get_user_api_key
                user_key = get_user_api_key(self.user, 'google')
                if user_key:
                    return user_key
            
            # 2. Fallback zu gemeinsamer Hilfsfunktion
            from naturmacher.utils.api_helpers import get_env_api_key
            return get_env_api_key('google')
                
        except ImportError:
            # Falls naturmacher.utils.api_helpers nicht verfügbar
            pass
        except Exception as e:
            print(f"Fehler beim API-Key Abruf: {e}")
        
        return None
    
    def generate_seo(self, product_title: str, product_description: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_prompt(product_title, product_description, keywords)
            
            # Gemini API Endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            response = requests.post(
                url,
                headers={
                    'Content-Type': 'application/json'
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 300,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    
                    # Parse JSON response (remove markdown code blocks if present)
                    try:
                        # Entferne Markdown-Code-Blöcke falls vorhanden
                        cleaned_content = content.strip()
                        if cleaned_content.startswith('```json'):
                            cleaned_content = cleaned_content[7:]  # Entferne ```json
                        if cleaned_content.startswith('```'):
                            cleaned_content = cleaned_content[3:]  # Entferne ```
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]  # Entferne ```
                        cleaned_content = cleaned_content.strip()
                        
                        result = json.loads(cleaned_content)
                        return True, {
                            'seo_title': result.get('seo_title', '')[:70],
                            'seo_description': result.get('seo_description', '')[:160]
                        }, "SEO-Inhalte erfolgreich generiert"
                    except json.JSONDecodeError:
                        return False, {}, f"Ungültige JSON-Antwort: {content}"
                else:
                    return False, {}, "Keine Antwort von Gemini erhalten"
            else:
                return False, {}, f"Gemini API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei Gemini-Request: {str(e)}"
    
    def _build_prompt(self, title: str, description: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        return f"""
Du bist ein SEO-Experte. Erstelle für folgendes E-Commerce-Produkt einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Produkttitel:** {title}

**Produktbeschreibung:** {description[:500]}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, ansprechend für Suchmaschinen
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, verkaufsfördernd
- Natürliche Integration der Keywords (kein Keyword-Stuffing)
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"
- Fokus auf Conversion-Optimierung

Antworte nur mit validem JSON in folgendem Format:
{{
    "title": "Der optimierte Haupttitel hier",
    "description": "Die optimierte Hauptbeschreibung hier",
    "seo_title": "Der optimierte SEO-Titel hier",
    "seo_description": "Die optimierte SEO-Beschreibung hier"
}}
"""


class MockAIService(AIService):
    """Mock-Service für Tests ohne echte API-Calls"""
    
    def generate_seo(self, product_title: str, product_description: str, keywords: list) -> Tuple[bool, Dict, str]:
        keywords_str = ', '.join(keywords[:3]) if keywords else ""
        
        # Einfache Mock-Generierung mit "du"-Form
        mock_title = f"{product_title[:50]} | {keywords_str}" if keywords_str else product_title[:60]
        mock_description = f"✅ {product_title} - Hochwertig & {keywords_str}. Jetzt günstig für dich ✅" if keywords_str else f"✅ {product_title} - Hochwertig & zuverlässig. Perfekt für dich ✅"
        
        return True, {
            'title': product_title,
            'description': product_description[:500] if product_description else "Hochwertige Produktbeschreibung",
            'seo_title': mock_title[:70],
            'seo_description': mock_description[:160]
        }, "Mock SEO-Inhalte generiert"


def get_ai_service(model_name: str, user=None) -> AIService:
    """Factory-Funktion für AI-Services mit aktuellen Modell-Mappings"""
    
    # OpenAI/ChatGPT Modelle
    if model_name.startswith('gpt-') or model_name.startswith('o'):
        if model_name == 'gpt-4.1':
            model = 'gpt-4-turbo'  # Neuestes verfügbares Modell
        elif model_name == 'gpt-4.1-mini':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4.1-nano':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4o':
            model = 'gpt-4o'
        elif model_name == 'gpt-4o-mini':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4-turbo':
            model = 'gpt-4-turbo'
        elif model_name == 'gpt-4':
            model = 'gpt-4'
        elif model_name == 'gpt-3.5-turbo':
            model = 'gpt-3.5-turbo'
        elif model_name == 'o3':
            model = 'o1-preview'  # Mapping to available model
        elif model_name == 'o4-mini':
            model = 'o1-mini'  # Mapping to available model
        else:
            model = 'gpt-4o'  # Default zu neuem Standardmodell
        return OpenAIService(model, user=user)
        
    # Claude (Anthropic) Modelle
    elif model_name.startswith('claude-'):
        if model_name == 'claude-opus-4':
            model = 'claude-3-opus-20240229'  # Mapping to available model
        elif model_name == 'claude-sonnet-4':
            model = 'claude-3-5-sonnet-20241022'  # Mapping to latest Sonnet
        elif model_name == 'claude-sonnet-3.7':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-sonnet-3.5-new':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-sonnet-3.5':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-haiku-3.5-new':
            model = 'claude-3-5-haiku-20241022'
        elif model_name == 'claude-haiku-3.5':
            model = 'claude-3-5-haiku-20241022'
        else:
            model = 'claude-3-5-sonnet-20241022'  # Default
        return ClaudeService(model, user=user)
        
    # Google Gemini Modelle
    elif model_name.startswith('gemini-') or model_name.startswith('google-') or model_name == 'gemini':
        if model_name == 'gemini-2.5-pro':
            model = 'gemini-1.5-pro'  # Mapping to available model
        elif model_name == 'gemini-2.5-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-2.0-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-2.0-pro':
            model = 'gemini-1.5-pro'
        elif model_name == 'gemini-1.5-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-1.5-pro':
            model = 'gemini-1.5-pro'
        elif model_name == 'gemini':
            model = 'gemini-1.5-flash'  # Kostenlose Option
        else:
            model = 'gemini-1.5-flash'  # Default zu kostenlosem Modell
        return GeminiService(model, user=user)
        
    elif model_name.startswith('mock'):
        return MockAIService()
    else:
        # Fallback zu Mock für unbekannte Modelle
        return MockAIService()


def generate_seo_with_ai(product_title: str, product_description: str, keywords: list, ai_model: str, user=None) -> Tuple[bool, Dict, str, str]:
    """
    Hauptfunktion zur SEO-Generierung mit KI
    
    Returns:
        (success, result_dict, message, raw_response)
    """
    try:
        ai_service = get_ai_service(ai_model, user=user)
        success, result, message = ai_service.generate_seo(product_title, product_description, keywords)
        
        return success, result, message, f"AI Model: {ai_model}"
        
    except Exception as e:
        return False, {}, f"Fehler beim Erstellen des AI-Service: {str(e)}", ""


class BlogPostAIService(AIService):
    """Erweiterte AI-Service-Klasse für Blog-Posts"""
    
    def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
        """
        Generiert SEO-Titel und -Beschreibung speziell für Blog-Posts
        
        Returns:
            (success, {'seo_title': str, 'seo_description': str}, message)
        """
        raise NotImplementedError


class BlogPostOpenAIService(OpenAIService, BlogPostAIService):
    """OpenAI-Service für Blog-Post SEO-Optimierung"""
    
    def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_blog_prompt(title, content, summary, keywords)
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'Du bist ein SEO-Experte für Blog-Content. Du erstellst SEO-optimierte Titel und Beschreibungen für Blog-Beiträge.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'max_tokens': 300,
                    'temperature': 0.7
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                # Parse JSON response (remove markdown code blocks if present)
                try:
                    # Entferne Markdown-Code-Blöcke falls vorhanden
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```json'):
                        cleaned_content = cleaned_content[7:]  # Entferne ```json
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]  # Entferne ```
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]  # Entferne ```
                    cleaned_content = cleaned_content.strip()
                    
                    result = json.loads(cleaned_content)
                    return True, {
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'seo_title': result.get('seo_title', '')[:70],
                        'seo_description': result.get('seo_description', '')[:160]
                    }, "Blog-Post SEO-Inhalte erfolgreich generiert"
                except json.JSONDecodeError:
                    return False, {}, f"Ungültige JSON-Antwort: {content}"
            else:
                return False, {}, f"OpenAI API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei OpenAI-Request für Blog-Post: {str(e)}"
    
    def _build_blog_prompt(self, title: str, content: str, summary: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        # Kürze den Content für den Prompt
        content_preview = content[:800] if content else ""
        summary_text = summary if summary else "Keine Zusammenfassung verfügbar"
        
        return f"""
Erstelle für folgenden Blog-Beitrag einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Blog-Titel:** {title}

**Zusammenfassung:** {summary_text}

**Inhalt (Vorschau):** {content_preview}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, neugierig machend für Suchmaschinen
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, informativ und einladend
- Natürliche Integration der Keywords (kein Keyword-Stuffing)  
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"
- Fokus auf Klick-Optimierung und Nutzerinteresse

Antworte nur mit validem JSON in folgendem Format:
{{
    "title": "Der optimierte Blog-Titel hier",
    "description": "Der optimierte Blog-Inhalt hier",
    "seo_title": "Der optimierte SEO-Titel für den Blog-Post hier",
    "seo_description": "Die optimierte SEO-Beschreibung für den Blog-Post hier"
}}
"""


class BlogPostClaudeService(ClaudeService, BlogPostAIService):
    """Claude-Service für Blog-Post SEO-Optimierung"""
    
    def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_blog_prompt(title, content, summary, keywords)
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': self.model,
                    'max_tokens': 300,
                    'messages': [
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['content'][0]['text']
                
                # Parse JSON response (remove markdown code blocks if present)
                try:
                    # Entferne Markdown-Code-Blöcke falls vorhanden
                    cleaned_content = content.strip()
                    if cleaned_content.startswith('```json'):
                        cleaned_content = cleaned_content[7:]  # Entferne ```json
                    if cleaned_content.startswith('```'):
                        cleaned_content = cleaned_content[3:]  # Entferne ```
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]  # Entferne ```
                    cleaned_content = cleaned_content.strip()
                    
                    result = json.loads(cleaned_content)
                    return True, {
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'seo_title': result.get('seo_title', '')[:70],
                        'seo_description': result.get('seo_description', '')[:160]
                    }, "Blog-Post SEO-Inhalte erfolgreich generiert"
                except json.JSONDecodeError:
                    return False, {}, f"Ungültige JSON-Antwort: {content}"
            else:
                return False, {}, f"Claude API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei Claude-Request für Blog-Post: {str(e)}"
    
    def _build_blog_prompt(self, title: str, content: str, summary: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        # Kürze den Content für den Prompt
        content_preview = content[:800] if content else ""
        summary_text = summary if summary else "Keine Zusammenfassung verfügbar"
        
        return f"""
Du bist ein SEO-Experte für Blog-Content. Erstelle für folgenden Blog-Beitrag einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Blog-Titel:** {title}

**Zusammenfassung:** {summary_text}

**Inhalt (Vorschau):** {content_preview}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, neugierig machend für Leser
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, informativ und klick-fördernd
- Natürliche Integration der Keywords (kein Keyword-Stuffing)  
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"
- Fokus auf Klick-Optimierung und Nutzerinteresse für Blog-Leser

Antworte nur mit validem JSON in folgendem Format:
{{
    "title": "Der optimierte Blog-Titel hier",
    "description": "Der optimierte Blog-Inhalt hier",
    "seo_title": "Der optimierte SEO-Titel für den Blog-Post hier",
    "seo_description": "Die optimierte SEO-Beschreibung für den Blog-Post hier"
}}
"""


class BlogPostGeminiService(GeminiService, BlogPostAIService):
    """Gemini-Service für Blog-Post SEO-Optimierung"""
    
    def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
        try:
            prompt = self._build_blog_prompt(title, content, summary, keywords)
            
            # Gemini API Endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            response = requests.post(
                url,
                headers={
                    'Content-Type': 'application/json'
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 300,
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    
                    # Parse JSON response (remove markdown code blocks if present)
                    try:
                        # Entferne Markdown-Code-Blöcke falls vorhanden
                        cleaned_content = content.strip()
                        if cleaned_content.startswith('```json'):
                            cleaned_content = cleaned_content[7:]  # Entferne ```json
                        if cleaned_content.startswith('```'):
                            cleaned_content = cleaned_content[3:]  # Entferne ```
                        if cleaned_content.endswith('```'):
                            cleaned_content = cleaned_content[:-3]  # Entferne ```
                        cleaned_content = cleaned_content.strip()
                        
                        result = json.loads(cleaned_content)
                        return True, {
                            'seo_title': result.get('seo_title', '')[:70],
                            'seo_description': result.get('seo_description', '')[:160]
                        }, "Blog-Post SEO-Inhalte erfolgreich generiert"
                    except json.JSONDecodeError:
                        return False, {}, f"Ungültige JSON-Antwort: {content}"
                else:
                    return False, {}, "Keine Antwort von Gemini erhalten"
            else:
                return False, {}, f"Gemini API Fehler: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, {}, f"Fehler bei Gemini-Request für Blog-Post: {str(e)}"
    
    def _build_blog_prompt(self, title: str, content: str, summary: str, keywords: list) -> str:
        keywords_str = ', '.join(keywords) if keywords else "keine spezifischen Keywords"
        
        # Kürze den Content für den Prompt
        content_preview = content[:800] if content else ""
        summary_text = summary if summary else "Keine Zusammenfassung verfügbar"
        
        return f"""
Du bist ein SEO-Experte für Blog-Content. Erstelle für folgenden Blog-Beitrag einen SEO-optimierten Titel und eine SEO-Beschreibung:

**Blog-Titel:** {title}

**Zusammenfassung:** {summary_text}

**Inhalt (Vorschau):** {content_preview}...

**Ziel-Keywords:** {keywords_str}

**Anforderungen:**
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, neugierig machend für Leser
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, informativ und klick-fördernd
- Natürliche Integration der Keywords (kein Keyword-Stuffing)  
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"
- Fokus auf Klick-Optimierung und Nutzerinteresse für Blog-Leser

Antworte nur mit validem JSON in folgendem Format:
{{
    "title": "Der optimierte Blog-Titel hier",
    "description": "Der optimierte Blog-Inhalt hier",
    "seo_title": "Der optimierte SEO-Titel für den Blog-Post hier",
    "seo_description": "Die optimierte SEO-Beschreibung für den Blog-Post hier"
}}
"""


def get_blog_ai_service(model_name: str, user=None) -> BlogPostAIService:
    """Factory-Funktion für Blog-Post AI-Services mit aktuellen Modell-Mappings"""
    
    # OpenAI/ChatGPT Modelle
    if model_name.startswith('gpt-') or model_name.startswith('o'):
        if model_name == 'gpt-4.1':
            model = 'gpt-4-turbo'  # Neuestes verfügbares Modell
        elif model_name == 'gpt-4.1-mini':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4.1-nano':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4o':
            model = 'gpt-4o'
        elif model_name == 'gpt-4o-mini':
            model = 'gpt-4o-mini'
        elif model_name == 'gpt-4-turbo':
            model = 'gpt-4-turbo'
        elif model_name == 'gpt-4':
            model = 'gpt-4'
        elif model_name == 'gpt-3.5-turbo':
            model = 'gpt-3.5-turbo'
        elif model_name == 'o3':
            model = 'o1-preview'  # Mapping to available model
        elif model_name == 'o4-mini':
            model = 'o1-mini'  # Mapping to available model
        else:
            model = 'gpt-4o'  # Default zu neuem Standardmodell
        return BlogPostOpenAIService(model, user=user)
        
    # Claude (Anthropic) Modelle
    elif model_name.startswith('claude-'):
        if model_name == 'claude-opus-4':
            model = 'claude-3-opus-20240229'  # Mapping to available model
        elif model_name == 'claude-sonnet-4':
            model = 'claude-3-5-sonnet-20241022'  # Mapping to latest Sonnet
        elif model_name == 'claude-sonnet-3.7':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-sonnet-3.5-new':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-sonnet-3.5':
            model = 'claude-3-5-sonnet-20241022'
        elif model_name == 'claude-haiku-3.5-new':
            model = 'claude-3-5-haiku-20241022'
        elif model_name == 'claude-haiku-3.5':
            model = 'claude-3-5-haiku-20241022'
        else:
            model = 'claude-3-5-sonnet-20241022'  # Default
        return BlogPostClaudeService(model, user=user)
        
    # Google Gemini Modelle
    elif model_name.startswith('gemini-') or model_name.startswith('google-') or model_name == 'gemini':
        if model_name == 'gemini-2.5-pro':
            model = 'gemini-1.5-pro'  # Mapping to available model
        elif model_name == 'gemini-2.5-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-2.0-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-2.0-pro':
            model = 'gemini-1.5-pro'
        elif model_name == 'gemini-1.5-flash':
            model = 'gemini-1.5-flash'
        elif model_name == 'gemini-1.5-pro':
            model = 'gemini-1.5-pro'
        elif model_name == 'gemini':
            model = 'gemini-1.5-flash'  # Kostenlose Option
        else:
            model = 'gemini-1.5-flash'  # Default zu kostenlosem Modell
        return BlogPostGeminiService(model, user=user)
        
    else:
        # Fallback zu Mock für andere Modelle
        class BlogPostMockService(MockAIService, BlogPostAIService):
            def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
                keywords_str = ', '.join(keywords[:3]) if keywords else ""
                
                # Mock-Generierung für Blog-Posts
                mock_title = f"{title[:50]} | {keywords_str}" if keywords_str else title[:60]
                mock_description = f"✅ {title} - Informativ & {keywords_str}. Jetzt lesen ✅" if keywords_str else f"✅ {title} - Informativer Blog-Beitrag. Jetzt entdecken ✅"
                
                return True, {
                    'title': title,
                    'description': content[:500] if content else summary[:500] if summary else "Informativer Blog-Beitrag",
                    'seo_title': mock_title[:70],
                    'seo_description': mock_description[:160]
                }, "Mock Blog-Post SEO-Inhalte generiert"
        
        return BlogPostMockService()


class BlogPostSEOService:
    """Service-Klasse für Blog-Post SEO-Optimierung"""
    
    def __init__(self, user=None):
        self.user = user
    
    def generate_seo_content(self, seo_optimization) -> Tuple[bool, str, str]:
        """
        Generiert SEO-Inhalte für eine BlogPostSEOOptimization
        
        Args:
            seo_optimization: BlogPostSEOOptimization instance
            
        Returns:
            (success, result_message, error_message)
        """
        try:
            blog_post = seo_optimization.blog_post
            keywords = seo_optimization.get_keywords_list()
            
            # Hole AI-Service
            ai_service = get_blog_ai_service(seo_optimization.ai_model, user=self.user)
            
            # Generiere SEO-Inhalte
            success, result, message = ai_service.generate_blog_seo(
                title=blog_post.title,
                content=blog_post.content or "",
                summary=blog_post.summary or "",
                keywords=keywords
            )
            
            if success:
                # Speichere generierte Inhalte
                seo_optimization.generated_seo_title = result.get('seo_title', '')
                seo_optimization.generated_seo_description = result.get('seo_description', '')
                seo_optimization.ai_response_raw = message
                
                # Erstelle AI-Prompt für Debugging
                ai_prompt = f"Titel: {blog_post.title}, Keywords: {', '.join(keywords)}, Modell: {seo_optimization.ai_model}"
                seo_optimization.ai_prompt_used = ai_prompt
                
                seo_optimization.save()
                
                return True, message, ""
            else:
                return False, "", message
                
        except Exception as e:
            return False, "", f"Fehler bei der Blog-Post SEO-Generierung: {str(e)}"