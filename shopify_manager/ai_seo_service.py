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
                
                # Parse JSON response
                try:
                    result = json.loads(content)
                    return True, {
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
- SEO-Titel: maximal 70 Zeichen, keyword-optimiert, ansprechend
- SEO-Beschreibung: maximal 160 Zeichen, keyword-optimiert, verkaufsfördernd
- Natürlich wirkende Integration der Keywords
- Deutsche Sprache mit "du"-Form für persönliche Ansprache
- Verwende "du", "dein", "dir" statt "Sie", "Ihr", "Ihnen"

**Antwortformat (nur JSON):**
{{
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
                
                # Parse JSON response
                try:
                    result = json.loads(content)
                    return True, {
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
            'seo_title': mock_title[:70],
            'seo_description': mock_description[:160]
        }, "Mock SEO-Inhalte generiert"


def get_ai_service(model_name: str, user=None) -> AIService:
    """Factory-Funktion für AI-Services"""
    
    if model_name.startswith('openai-'):
        model = 'gpt-4' if 'gpt4' in model_name else 'gpt-3.5-turbo'
        return OpenAIService(model, user=user)
    elif model_name.startswith('claude-'):
        if 'sonnet' in model_name:
            model = 'claude-3-5-sonnet-20241022'
        elif 'haiku' in model_name:
            model = 'claude-3-5-haiku-20241022'
        else:
            model = 'claude-3-5-sonnet-20241022'  # Default to latest Sonnet
        return ClaudeService(model, user=user)
    elif model_name.startswith('gemini-') or model_name.startswith('google-'):
        # Für jetzt als Mock, kann später durch echten Google AI Service ersetzt werden
        return MockAIService()
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
                
                # Parse JSON response
                try:
                    result = json.loads(content)
                    return True, {
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
                
                # Parse JSON response
                try:
                    result = json.loads(content)
                    return True, {
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
    "seo_title": "Der optimierte SEO-Titel für den Blog-Post hier",
    "seo_description": "Die optimierte SEO-Beschreibung für den Blog-Post hier"
}}
"""


def get_blog_ai_service(model_name: str, user=None) -> BlogPostAIService:
    """Factory-Funktion für Blog-Post AI-Services"""
    
    if model_name.startswith('openai-'):
        model = 'gpt-4' if 'gpt4' in model_name else 'gpt-3.5-turbo'
        return BlogPostOpenAIService(model, user=user)
    elif model_name.startswith('claude-'):
        if 'sonnet' in model_name:
            model = 'claude-3-5-sonnet-20241022'
        elif 'haiku' in model_name:
            model = 'claude-3-5-haiku-20241022'
        else:
            model = 'claude-3-5-sonnet-20241022'  # Default to latest Sonnet
        return BlogPostClaudeService(model, user=user)
    else:
        # Fallback zu Mock für andere Modelle
        class BlogPostMockService(MockAIService, BlogPostAIService):
            def generate_blog_seo(self, title: str, content: str, summary: str, keywords: list) -> Tuple[bool, Dict, str]:
                keywords_str = ', '.join(keywords[:3]) if keywords else ""
                
                # Mock-Generierung für Blog-Posts
                mock_title = f"{title[:50]} | {keywords_str}" if keywords_str else title[:60]
                mock_description = f"✅ {title} - Informativ & {keywords_str}. Jetzt lesen ✅" if keywords_str else f"✅ {title} - Informativer Blog-Beitrag. Jetzt entdecken ✅"
                
                return True, {
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