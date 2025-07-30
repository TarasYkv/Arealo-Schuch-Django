"""
AI-powered Email Content Generation Service
"""
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    
import json
import requests
from django.conf import settings
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class EmailAIService:
    """Service for generating email content using AI."""
    
    def __init__(self, user=None):
        """Initialize the AI service with user-specific API keys."""
        self.user = user
        self.available_models = self._get_available_models()
        self.available = len(self.available_models) > 0
        
        if not self.available:
            logger.warning("No AI models available. Email generation will use fallback templates.")
    
    def _get_available_models(self):
        """Get available AI models based on user configuration and installed packages."""
        models = {}
        
        if self.user and self.user.is_authenticated:
            # Check user's API keys
            if OPENAI_AVAILABLE and self.user.openai_api_key:
                models.update({
                    'gpt-4o-2025-01-07': {
                        'name': 'GPT-4o (2025-01-07) ⭐',
                        'provider': 'openai',
                        'description': 'Neueste GPT-4o Version Januar 2025',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'gpt-4o-2024-12-17': {
                        'name': 'GPT-4o (2024-12-17)',
                        'provider': 'openai',
                        'description': 'GPT-4o Version Dezember 2024',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'gpt-4o': {
                        'name': 'GPT-4o (Standard)',
                        'provider': 'openai',
                        'description': 'Bewährtes leistungsstarkes OpenAI Modell',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'o1-2024-12-17': {
                        'name': 'o1 (2024-12-17) 🧠⭐',
                        'provider': 'openai',
                        'description': 'Neueste o1 Version mit verbessertem Reasoning',
                        'cost': 'Sehr hoch',
                        'speed': 'Langsam'
                    },
                    'o1-preview': {
                        'name': 'o1-preview (Reasoning) 🧠',
                        'provider': 'openai',
                        'description': 'Fortgeschrittenes Reasoning-Modell für komplexe Aufgaben',
                        'cost': 'Sehr hoch',
                        'speed': 'Langsam'
                    },
                    'o1-mini-2024-12-17': {
                        'name': 'o1-mini (2024-12-17)',
                        'provider': 'openai',
                        'description': 'Neueste kompakte o1 Version',
                        'cost': 'Mittel',
                        'speed': 'Mittel'
                    },
                    'o1-mini': {
                        'name': 'o1-mini (Reasoning Light)',
                        'provider': 'openai',
                        'description': 'Kompaktes Reasoning-Modell',
                        'cost': 'Mittel',
                        'speed': 'Mittel'
                    },
                    'gpt-4o-mini': {
                        'name': 'GPT-4o Mini (Effizient)',
                        'provider': 'openai', 
                        'description': 'Ausgewogenes Preis-Leistungs-Verhältnis',
                        'cost': 'Niedrig',
                        'speed': 'Schnell'
                    },
                })
            
            if ANTHROPIC_AVAILABLE and self.user.anthropic_api_key:
                models.update({
                    'claude-sonnet-4-20250514': {
                        'name': 'Claude Sonnet 4 (2025-05-14) ⭐🚀',
                        'provider': 'anthropic',
                        'description': 'Neueste Claude 4 Generation - höchste Leistung',
                        'cost': 'Sehr hoch',
                        'speed': 'Mittel'
                    },
                    'claude-3-5-sonnet-20241022': {
                        'name': 'Claude 3.5 Sonnet (Latest)',
                        'provider': 'anthropic',
                        'description': 'Bewährte Claude 3.5 Version mit Computer Use',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'claude-3-5-haiku-20241022': {
                        'name': 'Claude 3.5 Haiku (Latest) ⚡',
                        'provider': 'anthropic',
                        'description': 'Neueste schnelle Claude Version',
                        'cost': 'Niedrig',
                        'speed': 'Sehr schnell'
                    },
                    'claude-3-opus-20240229': {
                        'name': 'Claude 3 Opus (Most Powerful) 🚀',
                        'provider': 'anthropic',
                        'description': 'Stärkstes Claude 3 Modell für komplexe Aufgaben',
                        'cost': 'Sehr hoch',
                        'speed': 'Langsam'
                    },
                    'claude-3-sonnet-20240229': {
                        'name': 'Claude 3 Sonnet (Balanced)',
                        'provider': 'anthropic',
                        'description': 'Ausgewogenes Claude 3 Modell',
                        'cost': 'Mittel',
                        'speed': 'Mittel'
                    }
                })
            
            if GEMINI_AVAILABLE and self.user.google_api_key:
                models.update({
                    'gemini-1.5-pro-002': {
                        'name': 'Gemini 1.5 Pro-002 ⭐',
                        'provider': 'google',
                        'description': 'Neueste Gemini Pro Version mit verbesserter Leistung',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'gemini-1.5-pro': {
                        'name': 'Gemini 1.5 Pro (Stable)',
                        'provider': 'google',
                        'description': 'Bewährtes leistungsstarkes Gemini-Modell',
                        'cost': 'Hoch',
                        'speed': 'Mittel'
                    },
                    'gemini-2.0-flash-exp': {
                        'name': 'Gemini 2.0 Flash Experimental 🚀',
                        'provider': 'google',
                        'description': 'Experimentelle Gemini 2.0 Version mit neuesten Features',
                        'cost': 'Mittel',
                        'speed': 'Sehr schnell'
                    },
                    'gemini-1.5-flash': {
                        'name': 'Gemini 1.5 Flash (Efficient)',
                        'provider': 'google',
                        'description': 'Bewährtes schnelles Gemini-Modell',
                        'cost': 'Niedrig',
                        'speed': 'Sehr schnell'
                    },
                    'gemini-1.5-flash-8b': {
                        'name': 'Gemini 1.5 Flash-8B (Ultra-Fast) ⚡',
                        'provider': 'google',
                        'description': 'Ultraschnelles kompaktes Modell',
                        'cost': 'Sehr niedrig',
                        'speed': 'Extrem schnell'
                    },
                    'gemini-1.5-flash-002': {
                        'name': 'Gemini 1.5 Flash-002 (Free Tier) 🆓',
                        'provider': 'google',
                        'description': 'Kostenloses Gemini-Modell mit täglichem Limit',
                        'cost': 'Kostenlos',
                        'speed': 'Sehr schnell'
                    }
                })
        
        # Add fallback template option
        models['fallback'] = {
            'name': 'Template-basiert (Kostenlos)',
            'provider': 'fallback',
            'description': 'Verwendet vordefinierte Templates ohne KI',
            'cost': 'Kostenlos',
            'speed': 'Sofort'
        }
        
        return models
    
    def get_available_models(self):
        """Returns available models for the user."""
        return self.available_models
    
    def get_library_status(self):
        """Get status of AI libraries and user API keys."""
        status = {
            'libraries': {
                'openai': OPENAI_AVAILABLE,
                'anthropic': ANTHROPIC_AVAILABLE,
                'gemini': GEMINI_AVAILABLE
            },
            'api_keys': {
                'openai': bool(self.user and self.user.openai_api_key),
                'anthropic': bool(self.user and self.user.anthropic_api_key),
                'google': bool(self.user and self.user.google_api_key)
            },
            'available_providers': []
        }
        
        if OPENAI_AVAILABLE and self.user and self.user.openai_api_key:
            status['available_providers'].append('OpenAI')
        if ANTHROPIC_AVAILABLE and self.user and self.user.anthropic_api_key:
            status['available_providers'].append('Anthropic')
        if GEMINI_AVAILABLE and self.user and self.user.google_api_key:
            status['available_providers'].append('Google')
            
        return status
    
    def get_default_model(self):
        """Get the user's preferred model or a sensible default."""
        if not self.user or not self.user.is_authenticated:
            return 'fallback'
        
        # Check user's preferred models
        if hasattr(self.user, 'preferred_openai_model') and self.user.preferred_openai_model:
            if self.user.preferred_openai_model in self.available_models:
                return self.user.preferred_openai_model
        
        if hasattr(self.user, 'preferred_anthropic_model') and self.user.preferred_anthropic_model:
            if self.user.preferred_anthropic_model in self.available_models:
                return self.user.preferred_anthropic_model
        
        # Fallback to first available AI model (not fallback)
        available_keys = list(self.available_models.keys())
        if 'fallback' in available_keys:
            available_keys.remove('fallback')
        
        # Prefer newest/best models first (including free options)
        model_priority = [
            # Newest OpenAI models first
            'gpt-4o-2025-01-07', 'o1-2024-12-17', 'gpt-4o-2024-12-17', 'o1-mini-2024-12-17', 'gpt-4o', 'o1-mini', 'gpt-4o-mini',
            # Newest Anthropic models (Claude 4 first!)
            'claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-5-haiku-20241022',
            # Newest Google models (stable models first)
            'gemini-1.5-pro-002', 'gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash-002', 'gemini-1.5-flash', 'gemini-1.5-flash-8b'
        ]
        
        # Return first available model in priority order
        for model in model_priority:
            if model in available_keys:
                return model
                
        # Fallback to any available model
        if available_keys:
            return available_keys[0]
        else:
            return 'fallback'
    
    def generate_email_content(
        self, 
        description: str, 
        email_type: str = 'general',
        language: str = 'german',
        tone: str = 'professional',
        include_variables: bool = True,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Generate email content based on description.
        
        Args:
            description: Description of the email content to generate
            email_type: Type of email (welcome, notification, marketing, etc.)
            language: Language for the email (german, english)
            tone: Tone of the email (professional, friendly, formal)
            include_variables: Whether to include template variables
            model: AI model to use (if None, uses default)
            
        Returns:
            Dict containing generated content, model used, and error if any
        """
        # Determine which model to use
        if not model:
            model = self.get_default_model()
        
        if model not in self.available_models:
            model = 'fallback'
        
        model_info = self.available_models[model]
        
        # Use fallback if no AI model available or explicitly requested
        if model == 'fallback' or model_info['provider'] == 'fallback':
            result = self._generate_fallback_content(description, email_type, tone, include_variables)
            result['model_used'] = model
            result['model_info'] = model_info
            result['fallback_reason'] = 'User selected template-based generation'
            return result
        
        # Try AI generation
        try:
            if model_info['provider'] == 'openai':
                result = self._generate_with_openai(model, description, email_type, language, tone, include_variables)
            elif model_info['provider'] == 'anthropic':
                result = self._generate_with_anthropic(model, description, email_type, language, tone, include_variables)
            elif model_info['provider'] == 'google':
                result = self._generate_with_gemini(model, description, email_type, language, tone, include_variables)
            else:
                # Fallback to template generation
                result = self._generate_fallback_content(description, email_type, tone, include_variables)
            
            result['model_used'] = model
            result['model_info'] = model_info
            return result
            
        except Exception as e:
            logger.error(f"AI email generation failed with {model}: {str(e)}")
            # Fallback to template generation on error
            result = self._generate_fallback_content(description, email_type, tone, include_variables)
            result['model_used'] = 'fallback'
            result['model_info'] = self.available_models['fallback'] 
            result['ai_error'] = str(e)
            result['fallback_reason'] = f'AI generation failed with {model_info["name"]}: {str(e)}'
            return result
    
    def _generate_with_openai(self, model, description, email_type, language, tone, include_variables):
        """Generate content using OpenAI API."""
        if not OPENAI_AVAILABLE or not self.user.openai_api_key:
            raise Exception("OpenAI not available or no API key configured")
        
        # Create OpenAI client
        client = openai.OpenAI(api_key=self.user.openai_api_key)
        
        # Create the prompt
        prompt = self._build_prompt(description, email_type, language, tone, include_variables)
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "Du bist ein Experte für E-Mail-Marketing und erstellst professionelle E-Mail-Templates."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=1500,
            temperature=0.7
        )
        
        # Parse the response
        content = response.choices[0].message.content.strip()
        parsed_content = self._parse_ai_response(content)
        
        return {
            'success': True,
            'content': parsed_content
        }
    
    def _generate_with_anthropic(self, model, description, email_type, language, tone, include_variables):
        """Generate content using Anthropic Claude API."""
        if not ANTHROPIC_AVAILABLE or not self.user.anthropic_api_key:
            raise Exception("Anthropic not available or no API key configured")
        
        # Create Anthropic client
        client = anthropic.Anthropic(api_key=self.user.anthropic_api_key)
        
        # Create the prompt
        prompt = self._build_prompt(description, email_type, language, tone, include_variables)
        system_prompt = "Du bist ein Experte für E-Mail-Marketing und erstellst professionelle E-Mail-Templates."
        
        # Call Claude API
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Parse the response
        content = response.content[0].text.strip()
        parsed_content = self._parse_ai_response(content)
        
        return {
            'success': True,
            'content': parsed_content
        }
    
    def _generate_with_gemini(self, model, description, email_type, language, tone, include_variables):
        """Generate content using Google Gemini API."""
        if not GEMINI_AVAILABLE or not self.user.google_api_key:
            raise Exception("Gemini not available or no API key configured")
        
        # Configure Gemini
        genai.configure(api_key=self.user.google_api_key)
        
        # Create the prompt
        prompt = self._build_prompt(description, email_type, language, tone, include_variables)
        system_prompt = "Du bist ein Experte für E-Mail-Marketing und erstellst professionelle E-Mail-Templates."
        
        try:
            # Create Gemini model with error handling for model names
            try:
                gemini_model = genai.GenerativeModel(
                    model_name=model,
                    system_instruction=system_prompt
                )
            except Exception as model_error:
                logger.warning(f"Failed to create Gemini model {model}, trying without system instruction: {model_error}")
                # Fallback: try without system instruction for older models
                gemini_model = genai.GenerativeModel(model_name=model)
                # Add system prompt to the main prompt instead
                prompt = f"{system_prompt}\n\n{prompt}"
            
            # Call Gemini API with robust error handling  
            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1500,
                    temperature=0.7,
                )
            )
            
            # Check if response is blocked
            if not response.text:
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    block_reason = getattr(response.prompt_feedback, 'block_reason', 'Unknown')
                    raise Exception(f"Gemini blocked the request: {block_reason}")
                else:
                    raise Exception("Gemini returned empty response")
            
            # Parse the response
            content = response.text.strip()
            parsed_content = self._parse_ai_response(content)
            
            return {
                'success': True,
                'content': parsed_content
            }
            
        except Exception as e:
            logger.error(f"Gemini API error with model {model}: {str(e)}")
            # Try to provide more specific error messages
            if "not found" in str(e).lower():
                raise Exception(f"Gemini model '{model}' not found. Check if model name is correct.")
            elif "quota" in str(e).lower() or "rate" in str(e).lower():
                raise Exception(f"Gemini API quota exceeded or rate limited: {str(e)}")
            elif "api key" in str(e).lower():
                raise Exception("Invalid Gemini API key. Please check your API key settings.")
            else:
                raise Exception(f"Gemini API error: {str(e)}")
    
    def _build_prompt(
        self, 
        description: str, 
        email_type: str, 
        language: str, 
        tone: str, 
        include_variables: bool
    ) -> str:
        """Build the prompt for AI generation."""
        
        base_prompt = f"""
Erstelle eine professionelle E-Mail-Vorlage basierend auf folgender Beschreibung:

BESCHREIBUNG: {description}

ANFORDERUNGEN:
- E-Mail-Typ: {email_type}
- Sprache: Deutsch
- Ton: {tone}
- Format: HTML mit inline CSS für bessere E-Mail-Client-Kompatibilität
- Breite: Maximal 600px
- Responsive Design für mobile Geräte

Erstelle die E-Mail mit folgender Struktur:
1. Aussagekräftiger Betreff
2. HTML-Inhalt mit ansprechendem Design
3. Optional: Text-Version
"""

        if include_variables:
            base_prompt += """
4. Template-Variablen für dynamische Inhalte (z.B. {{kunde_name}}, {{datum}}, etc.)

WICHTIG: Verwende Django-Template-Syntax für Variablen: {{ variable_name }}
Beispiele für häufige Variablen:
- {{ kunde_name }} für Kundennamen
- {{ firma }} für Firmenname  
- {{ email }} für E-Mail-Adresse
- {{ datum }} für Datum
- {{ betrag }} für Geldbeträge
- {{ bestellnummer }} für Bestellnummern
- {{ link_url }} für Links
"""

        base_prompt += """

AUSGABEFORMAT:
Gib die Antwort als JSON zurück mit folgender Struktur:
{
  "subject": "E-Mail Betreff hier",
  "html_content": "HTML Inhalt hier mit inline CSS",
  "text_content": "Optional: Nur-Text Version hier",
  "suggested_variables": {
    "variable_name": "Beschreibung der Variable"
  }
}

Achte darauf, dass der HTML-Code für E-Mail-Clients optimiert ist (Tabellen-Layout, inline CSS, etc.).
"""

        return base_prompt
    
    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse AI response and extract content."""
        try:
            # Clean up content first
            content = content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Try to find JSON within the content
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_content = content[json_start:json_end+1]
                try:
                    parsed = json.loads(json_content)
                    # Validate that we have the expected structure
                    if isinstance(parsed, dict):
                        return {
                            'subject': parsed.get('subject', ''),
                            'html_content': parsed.get('html_content', ''),
                            'text_content': parsed.get('text_content', ''),
                            'suggested_variables': parsed.get('suggested_variables', {})
                        }
                except json.JSONDecodeError:
                    pass
            
            # Try parsing as complete JSON
            if content.startswith('{') and content.endswith('}'):
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    return {
                        'subject': parsed.get('subject', ''),
                        'html_content': parsed.get('html_content', ''),
                        'text_content': parsed.get('text_content', ''),
                        'suggested_variables': parsed.get('suggested_variables', {})
                    }
            
            # If JSON parsing fails, try manual extraction
            result = {
                'subject': 'KI-generierte E-Mail',
                'html_content': '',
                'text_content': '',
                'suggested_variables': {}
            }
            
            # If no structured content found, use entire content as HTML
            if not result['html_content'] and not result['subject']:
                result['subject'] = 'KI-generierte E-Mail'
                result['html_content'] = content
                result['text_content'] = self._html_to_text(content)
            
            return result
            
        except Exception as e:
            logger.error(f"AI response parsing failed: {str(e)}")
            # Final fallback: return content as HTML
            return {
                'subject': 'KI-generierte E-Mail',
                'html_content': content,
                'text_content': self._html_to_text(content) if content else '',
                'suggested_variables': {}
            }
    
    def get_email_type_suggestions(self) -> Dict[str, str]:
        """Get suggestions for email types."""
        return {
            'welcome': 'Willkommens-E-Mail für neue Benutzer',
            'notification': 'Benachrichtigungs-E-Mail für Updates',
            'marketing': 'Marketing-E-Mail für Werbezwecke',
            'transactional': 'Transaktions-E-Mail für Bestellungen',
            'reminder': 'Erinnerungs-E-Mail für Termine',
            'newsletter': 'Newsletter für regelmäßige Updates',
            'confirmation': 'Bestätigungs-E-Mail für Aktionen',
            'invitation': 'Einladungs-E-Mail für Events',
            'feedback': 'Feedback-E-Mail für Bewertungen',
            'support': 'Support-E-Mail für Kundenservice'
        }
    
    def get_tone_suggestions(self) -> Dict[str, str]:
        """Get suggestions for email tones."""
        return {
            'professional': 'Professionell und sachlich',
            'friendly': 'Freundlich und persönlich',
            'formal': 'Formal und höflich',
            'casual': 'Locker und ungezwungen',
            'enthusiastic': 'Begeistert und motivierend',
            'empathetic': 'Einfühlsam und verständnisvoll'
        }
    
    def _generate_fallback_content(
        self, 
        description: str, 
        email_type: str, 
        tone: str, 
        include_variables: bool
    ) -> Dict[str, Any]:
        """Generate email content using predefined templates as fallback."""
        
        # Template-based content generation - Extended for all trigger categories
        templates = {
            # Authentication Templates
            'welcome': {
                'subject': 'Willkommen bei {{ site_name }}!',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: linear-gradient(135deg, #007bff 0%, #0056b3 100%); padding: 30px 20px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 28px;">Willkommen {{ user_name }}!</h1>
                        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Bei {{ site_name }}</p>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>herzlich willkommen bei {{ site_name }}! Wir freuen uns sehr, Sie als neues Mitglied begrüßen zu dürfen.</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0;">
                            <h3 style="margin: 0 0 15px 0; color: #007bff;">🚀 Ihre nächsten Schritte:</h3>
                            <ul style="margin: 0; padding-left: 20px;">
                                <li>Erkunden Sie Ihr <a href="{{ dashboard_url }}" style="color: #007bff;">Dashboard</a></li>
                                <li>Entdecken Sie unsere {{ features }}</li>
                                <li>Kontaktieren Sie unser Support-Team bei Fragen</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ dashboard_url }}" style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                Dashboard öffnen
                            </a>
                        </div>
                        
                        <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                        © 2025 {{ site_name }}. Alle Rechte vorbehalten.
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'site_name': 'Website-Name',
                    'dashboard_url': 'Dashboard-Link',
                    'features': 'Verfügbare Features'
                }
            },
            
            'account_activation': {
                'subject': 'Bitte bestätigen Sie Ihr Konto bei {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #28a745; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">🔐 Konto bestätigen</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>vielen Dank für Ihre Registrierung bei {{ site_name }}! Um Ihr Konto zu aktivieren, bestätigen Sie bitte Ihre E-Mail-Adresse.</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ verification_url }}" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                E-Mail bestätigen
                            </a>
                        </div>
                        
                        <p><strong>Alternativ</strong> können Sie diesen Link in Ihren Browser kopieren:</p>
                        <p style="background: #f8f9fa; padding: 10px; border-radius: 4px; word-break: break-all; font-family: monospace; font-size: 12px;">
                            {{ verification_url }}
                        </p>
                        
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>⚠️ Wichtig:</strong> Dieser Link ist nur begrenzt gültig. Falls Sie sich nicht registriert haben, können Sie diese E-Mail ignorieren.
                        </div>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'site_name': 'Website-Name',
                    'verification_url': 'Bestätigungslink'
                }
            },
            
            'password_reset': {
                'subject': 'Passwort zurücksetzen für {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #ffc107; padding: 20px; text-align: center;">
                        <h1 style="color: #333; margin: 0;">🔑 Passwort zurücksetzen</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>Sie haben eine Anfrage zum Zurücksetzen Ihres Passworts für {{ site_name }} gestellt.</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ reset_url }}" style="background: #ffc107; color: #333; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                Neues Passwort festlegen
                            </a>
                        </div>
                        
                        <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>⏰ Gültigkeitsdauer:</strong> Dieser Link ist {{ expiry_hours }} Stunden gültig.
                        </div>
                        
                        <p>Falls Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren. Ihr Passwort wird nicht geändert.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'site_name': 'Website-Name',
                    'reset_url': 'Passwort-Reset-Link',
                    'expiry_hours': 'Gültigkeitsdauer in Stunden'
                }
            },
            
            # Storage Management Templates
            'storage_warning': {
                'subject': '⚠️ Speicherplatz-Warnung - {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #ffc107; padding: 20px; text-align: center;">
                        <h1 style="color: #333; margin: 0;">⚠️ Speicherplatz-Warnung</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>Ihr Speicherplatz ist bald vollständig aufgebraucht:</p>
                        
                        <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 25px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <strong>Verwendeter Speicher:</strong>
                                <span>{{ used_storage }}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                                <strong>Verfügbarer Speicher:</strong>
                                <span>{{ max_storage }}</span>
                            </div>
                            {% if grace_period_days %}
                            <div style="background: #f8d7da; padding: 10px; border-radius: 4px;">
                                <strong>🕒 Kulanzzeit:</strong> {{ grace_period_days }} Tage verbleibend
                            </div>
                            {% endif %}
                        </div>
                        
                        <p><strong>Was passiert als nächstes?</strong></p>
                        <ul>
                            <li>Löschen Sie nicht benötigte Dateien</li>
                            <li>Oder upgraden Sie auf einen größeren Plan</li>
                            <li>Bei Überschreitung können Dateien archiviert werden</li>
                        </ul>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ upgrade_url }}" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                Jetzt upgraden
                            </a>
                        </div>
                        
                        <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'used_storage': 'Verwendeter Speicher',
                    'max_storage': 'Maximaler Speicher',
                    'grace_period_days': 'Kulanzzeit in Tagen',
                    'upgrade_url': 'Upgrade-Link'
                }
            },
            
            # Payment Templates
            'subscription_created': {
                'subject': '🎉 Willkommen bei {{ plan_name }} - {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); padding: 30px 20px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 28px;">🎉 Abonnement aktiviert!</h1>
                        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 18px;">{{ plan_name }}</p>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>vielen Dank für Ihr Vertrauen! Ihr <strong>{{ plan_name }}</strong> Abonnement wurde erfolgreich aktiviert.</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0;">
                            <h3 style="margin: 0 0 15px 0; color: #28a745;">📋 Abonnement-Details:</h3>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <strong>Plan:</strong>
                                <span>{{ plan_name }}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <strong>Preis:</strong>
                                <span>{{ price }}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                                <strong>Abrechnung:</strong>
                                <span>{{ billing_cycle }}</span>
                            </div>
                            <div style="border-top: 1px solid #dee2e6; padding-top: 15px;">
                                <strong>Enthaltene Features:</strong>
                                <div style="margin-top: 10px;">{{ features }}</div>
                            </div>
                        </div>
                        
                        <p>Sie können alle Vorteile Ihres neuen Plans sofort nutzen!</p>
                        
                        <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'plan_name': 'Abonnement-Name',
                    'price': 'Preis',
                    'billing_cycle': 'Abrechnungszyklus',
                    'features': 'Enthaltene Features'
                }
            },
            
            'payment_failed': {
                'subject': '❌ Zahlung fehlgeschlagen - {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #dc3545; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">❌ Zahlung fehlgeschlagen</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>leider konnten wir Ihre Zahlung in Höhe von <strong>{{ amount }}</strong> nicht verarbeiten.</p>
                        
                        <div style="background: #f8d7da; padding: 20px; border-radius: 8px; margin: 25px 0;">
                            <h3 style="margin: 0 0 15px 0; color: #dc3545;">🔍 Fehlergrund:</h3>
                            <p style="margin: 0;">{{ reason }}</p>
                        </div>
                        
                        <p><strong>Was können Sie tun?</strong></p>
                        <ul>
                            <li>Überprüfen Sie Ihre Zahlungsinformationen</li>
                            <li>Kontaktieren Sie Ihre Bank</li>
                            <li>Aktualisieren Sie Ihre Zahlungsmethode</li>
                        </ul>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ retry_url }}" style="background: #28a745; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; margin-right: 10px;">
                                Zahlung wiederholen
                            </a>
                            <a href="{{ update_payment_url }}" style="background: #6c757d; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                Zahlungsmethode ändern
                            </a>
                        </div>
                        
                        <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'amount': 'Betrag',
                    'reason': 'Fehlergrund',
                    'retry_url': 'Wiederholen-Link',
                    'update_payment_url': 'Zahlungsmethode aktualisieren'
                }
            },
            
            # E-Commerce Templates
            'order_confirmation': {
                'subject': '✅ Bestellbestätigung #{{ order_number }} - {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #28a745; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">✅ Bestellung bestätigt</h1>
                        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Bestellnummer: #{{ order_number }}</p>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ customer_name }},</p>
                        
                        <p>vielen Dank für Ihre Bestellung! Wir haben Ihre Bestellung erhalten und bearbeiten sie bereits.</p>
                        
                        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0;">
                            <h3 style="margin: 0 0 15px 0; color: #28a745;">📦 Bestelldetails:</h3>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <strong>Bestellnummer:</strong>
                                <span>#{{ order_number }}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                                <strong>Gesamtbetrag:</strong>
                                <span><strong>{{ total_amount }}</strong></span>
                            </div>
                            
                            <div style="border-top: 1px solid #dee2e6; padding-top: 15px;">
                                <strong>Bestellpositionen:</strong>
                                <div style="margin-top: 10px;">{{ order_items }}</div>
                            </div>
                            
                            {% if shipping_address %}
                            <div style="border-top: 1px solid #dee2e6; padding-top: 15px; margin-top: 15px;">
                                <strong>Lieferadresse:</strong>
                                <div style="margin-top: 5px;">{{ shipping_address }}</div>
                            </div>
                            {% endif %}
                        </div>
                        
                        <p>Sie erhalten eine separate E-Mail, sobald Ihre Bestellung versendet wurde.</p>
                        
                        <p>Bei Fragen zu Ihrer Bestellung stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'customer_name': 'Kundenname',
                    'order_number': 'Bestellnummer',
                    'order_items': 'Bestellpositionen',
                    'total_amount': 'Gesamtbetrag',
                    'shipping_address': 'Lieferadresse'
                }
            },
            
            # System & Organization Templates
            'maintenance_notification': {
                'subject': '🔧 Wartungsankündigung - {{ site_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #ffc107; padding: 20px; text-align: center;">
                        <h1 style="color: #333; margin: 0;">🔧 Geplante Wartung</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>wir informieren Sie über geplante Wartungsarbeiten, die sich auf unsere Services auswirken können:</p>
                        
                        <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #ffc107;">
                            <h3 style="margin: 0 0 15px 0; color: #856404;">📅 Wartungsdetails</h3>
                            <div style="margin-bottom: 10px;">
                                <strong>Beginn:</strong> {{ maintenance_start }}
                            </div>
                            <div style="margin-bottom: 10px;">
                                <strong>Ende:</strong> {{ maintenance_end }}
                            </div>
                            <div style="margin-bottom: 15px;">
                                <strong>Betroffene Services:</strong> {{ affected_services }}
                            </div>
                            <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                                <strong>Auswirkungen:</strong><br>
                                {{ impact_description }}
                            </div>
                        </div>
                        
                        <p><strong>Was bedeutet das für Sie?</strong></p>
                        <ul>
                            <li>Während der Wartung können Services eingeschränkt verfügbar sein</li>
                            <li>Geplante Aktivitäten sollten vor oder nach der Wartung durchgeführt werden</li>
                            <li>Wir entschuldigen uns für eventuelle Unannehmlichkeiten</li>
                        </ul>
                        
                        <p>Wir werden die Wartung so schnell wie möglich abschließen und Sie über den Abschluss informieren.</p>
                        
                        <p>Vielen Dank für Ihr Verständnis,<br>
                        Ihr {{ site_name }}-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'site_name': 'Website-Name',
                    'maintenance_start': 'Wartungsbeginn',
                    'maintenance_end': 'Wartungsende',
                    'affected_services': 'Betroffene Services',
                    'impact_description': 'Auswirkungen'
                }
            },
            
            'event_reminder': {
                'subject': '📅 Erinnerung: {{ event_title }} - {{ event_date }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: linear-gradient(135deg, #6f42c1 0%, #e83e8c 100%); padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">📅 Terminerinnerung</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ user_name }},</p>
                        
                        <p>dies ist eine freundliche Erinnerung an Ihren anstehenden Termin:</p>
                        
                        <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #6f42c1;">
                            <h3 style="margin: 0 0 20px 0; color: #6f42c1;">{{ event_title }}</h3>
                            
                            <div style="display: grid; grid-template-columns: auto 1fr; gap: 10px 20px; margin-bottom: 15px;">
                                <div style="font-weight: bold;">📅 Datum:</div>
                                <div>{{ event_date }}</div>
                                
                                <div style="font-weight: bold;">🕒 Zeit:</div>
                                <div>{{ event_time }}</div>
                                
                                {% if event_location %}
                                <div style="font-weight: bold;">📍 Ort:</div>
                                <div>{{ event_location }}</div>
                                {% endif %}
                            </div>
                            
                            {% if event_description %}
                            <div style="border-top: 1px solid #dee2e6; padding-top: 15px;">
                                <strong>Beschreibung:</strong><br>
                                <div style="margin-top: 5px;">{{ event_description }}</div>
                            </div>
                            {% endif %}
                        </div>
                        
                        <div style="background: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>💡 Tipp:</strong> Fügen Sie diesen Termin zu Ihrem Kalender hinzu, damit Sie ihn nicht vergessen!
                        </div>
                        
                        <p>Wir freuen uns auf Ihre Teilnahme!</p>
                        
                        <p>Beste Grüße,<br>
                        Ihr Organisationsteam</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'event_title': 'Termin-Titel',
                    'event_date': 'Termin-Datum',
                    'event_time': 'Termin-Zeit',
                    'event_location': 'Termin-Ort',
                    'event_description': 'Termin-Beschreibung'
                }
            },
            
            'task_assigned': {
                'subject': '📋 Neue Aufgabe zugewiesen: {{ task_title }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #17a2b8; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">📋 Neue Aufgabe</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ assignee_name }},</p>
                        
                        <p>{{ assigner_name }} hat Ihnen eine neue Aufgabe zugewiesen:</p>
                        
                        <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #17a2b8;">
                            <h3 style="margin: 0 0 15px 0; color: #17a2b8;">{{ task_title }}</h3>
                            
                            <div style="margin-bottom: 20px;">
                                <strong>Beschreibung:</strong><br>
                                <div style="margin-top: 8px; line-height: 1.5;">{{ task_description }}</div>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: auto 1fr; gap: 10px 20px;">
                                <div style="font-weight: bold;">📅 Fälligkeitsdatum:</div>
                                <div>{{ due_date }}</div>
                                
                                <div style="font-weight: bold;">⚡ Priorität:</div>
                                <div>
                                    {% if priority == 'high' %}
                                        <span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">HOCH</span>
                                    {% elif priority == 'medium' %}
                                        <span style="background: #ffc107; color: #333; padding: 2px 8px; border-radius: 3px; font-size: 12px;">MITTEL</span>
                                    {% else %}
                                        <span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">NIEDRIG</span>
                                    {% endif %}
                                </div>
                                
                                <div style="font-weight: bold;">👤 Zugewiesen von:</div>
                                <div>{{ assigner_name }}</div>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="#" style="background: #17a2b8; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                                Aufgabe anzeigen
                            </a>
                        </div>
                        
                        <p>Bitte bestätigen Sie den Erhalt dieser Aufgabe und planen Sie deren Bearbeitung entsprechend.</p>
                        
                        <p>Bei Fragen wenden Sie sich gerne an {{ assigner_name }}.</p>
                        
                        <p>Viel Erfolg bei der Bearbeitung!</p>
                        
                        <p>Beste Grüße,<br>
                        Ihr Projektmanagement-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'assignee_name': 'Name des Beauftragten',
                    'task_title': 'Aufgaben-Titel',
                    'task_description': 'Aufgaben-Beschreibung',
                    'due_date': 'Fälligkeitsdatum',
                    'priority': 'Priorität',
                    'assigner_name': 'Name des Zuweisenden'
                }
            },
            
            # Generic Templates
            'notification': {
                'subject': 'Wichtige Benachrichtigung - {{ betreff_detail }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #17a2b8; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">📢 Benachrichtigung</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ empfaenger_name }},</p>
                        
                        <p>wir möchten Sie über eine wichtige Änderung informieren:</p>
                        
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>{{ benachrichtigung_titel }}</strong><br>
                            {{ benachrichtigung_text }}
                        </div>
                        
                        {% if aktion_erforderlich %}
                        <p><strong>Aktion erforderlich:</strong></p>
                        <p>{{ aktion_beschreibung }}</p>
                        
                        <div style="text-align: center; margin: 25px 0;">
                            <a href="{{ aktion_link }}" style="background: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block;">
                                {{ aktion_button_text }}
                            </a>
                        </div>
                        {% endif %}
                        
                        <p>Bei Fragen kontaktieren Sie uns unter {{ kontakt_email }}.</p>
                        
                        <p>Mit freundlichen Grüßen,<br>
                        Ihr Support-Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'empfaenger_name': 'Name des Empfängers',
                    'betreff_detail': 'Details zum Betreff',
                    'benachrichtigung_titel': 'Titel der Benachrichtigung',
                    'benachrichtigung_text': 'Text der Benachrichtigung',
                    'aktion_erforderlich': 'Ob eine Aktion erforderlich ist (true/false)',
                    'aktion_beschreibung': 'Beschreibung der erforderlichen Aktion',
                    'aktion_link': 'Link für die Aktion',
                    'aktion_button_text': 'Text für den Aktions-Button',
                    'kontakt_email': 'Kontakt-E-Mail-Adresse'
                }
            },
            'marketing': {
                'subject': '🎉 Exklusives Angebot nur für Sie - {{ angebot_name }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 20px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 28px;">🎉 Exklusives Angebot</h1>
                        <p style="color: white; margin: 10px 0 0 0; font-size: 16px;">Nur für unsere geschätzten Kunden</p>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Liebe/r {{ kunde_name }},</p>
                        
                        <p>wir haben etwas Besonderes für Sie vorbereitet! Entdecken Sie unser exklusives Angebot:</p>
                        
                        <div style="background: #f8f9fa; border-left: 4px solid #28a745; padding: 20px; margin: 25px 0;">
                            <h3 style="margin: 0 0 10px 0; color: #28a745;">{{ angebot_titel }}</h3>
                            <p style="margin: 0; font-size: 16px;">{{ angebot_beschreibung }}</p>
                            
                            {% if rabatt_prozent %}
                            <div style="background: #28a745; color: white; padding: 10px; text-align: center; margin: 15px 0; border-radius: 5px;">
                                <strong style="font-size: 24px;">{{ rabatt_prozent }}% RABATT</strong>
                            </div>
                            {% endif %}
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{{ angebot_link }}" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-size: 18px; font-weight: bold;">
                                {{ button_text }}
                            </a>
                        </div>
                        
                        {% if gutschein_code %}
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; text-align: center; margin: 20px 0; border-radius: 5px;">
                            <strong>Gutscheincode:</strong> <code style="background: #f8f9fa; padding: 5px 10px; border-radius: 3px; font-size: 16px;">{{ gutschein_code }}</code>
                        </div>
                        {% endif %}
                        
                        {% if angebot_gueltig_bis %}
                        <p style="text-align: center; color: #dc3545; font-weight: bold;">
                            ⏰ Angebot gültig bis: {{ angebot_gueltig_bis }}
                        </p>
                        {% endif %}
                        
                        <p>Verpassen Sie nicht diese einmalige Gelegenheit!</p>
                        
                        <p>Herzliche Grüße,<br>
                        Ihr {{ firma }}-Team</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                        Sie erhalten diese E-Mail, weil Sie sich für unseren Newsletter angemeldet haben.<br>
                        <a href="{{ abmelde_link }}" style="color: #666;">Abmelden</a>
                    </div>
                </div>
                ''',
                'variables': {
                    'kunde_name': 'Name des Kunden',
                    'angebot_name': 'Name des Angebots',
                    'angebot_titel': 'Titel des Angebots',
                    'angebot_beschreibung': 'Beschreibung des Angebots',
                    'angebot_link': 'Link zum Angebot',
                    'rabatt_prozent': 'Rabatt in Prozent',
                    'gutschein_code': 'Gutscheincode',
                    'angebot_gueltig_bis': 'Gültigkeitsdatum',
                    'button_text': 'Text für den Call-to-Action Button',
                    'firma': 'Name des Unternehmens',
                    'abmelde_link': 'Link zum Abmelden'
                }
            },
            'confirmation': {
                'subject': 'Bestätigung: {{ aktion_titel }}',
                'html_content': '''
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
                    <div style="background: #28a745; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">✅ Bestätigung</h1>
                    </div>
                    
                    <div style="padding: 30px 20px;">
                        <p>Hallo {{ empfaenger_name }},</p>
                        
                        <p>vielen Dank! Wir haben Ihre Aktion erfolgreich verarbeitet:</p>
                        
                        <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; border-radius: 5px; margin: 25px 0;">
                            <h3 style="margin: 0 0 15px 0; color: #155724;">{{ bestaetigung_titel }}</h3>
                            
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold; width: 30%;">Datum:</td>
                                    <td style="padding: 8px 0;">{{ datum }}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Referenz:</td>
                                    <td style="padding: 8px 0;">{{ referenz_nummer }}</td>
                                </tr>
                                {% if betrag %}
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Betrag:</td>
                                    <td style="padding: 8px 0;">{{ betrag }}</td>
                                </tr>
                                {% endif %}
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Status:</td>
                                    <td style="padding: 8px 0;"><span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-size: 12px;">BESTÄTIGT</span></td>
                                </tr>
                            </table>
                        </div>
                        
                        {% if naechste_schritte %}
                        <h4>Nächste Schritte:</h4>
                        <p>{{ naechste_schritte }}</p>
                        {% endif %}
                        
                        {% if wichtige_informationen %}
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            <strong>💡 Wichtige Informationen:</strong><br>
                            {{ wichtige_informationen }}
                        </div>
                        {% endif %}
                        
                        <p>Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
                        
                        <p>Mit freundlichen Grüßen,<br>
                        Ihr Team</p>
                    </div>
                </div>
                ''',
                'variables': {
                    'empfaenger_name': 'Name des Empfängers',
                    'aktion_titel': 'Titel der bestätigten Aktion',
                    'bestaetigung_titel': 'Titel der Bestätigung',
                    'datum': 'Datum der Aktion',
                    'referenz_nummer': 'Referenz-/Bestellnummer',
                    'betrag': 'Betrag (optional)',
                    'naechste_schritte': 'Beschreibung der nächsten Schritte',
                    'wichtige_informationen': 'Wichtige zusätzliche Informationen'
                }
            }
        }
        
        # Map email_type to template - use direct match or fallback to closest match
        type_mapping = {
            # Direct mappings
            'welcome': 'welcome',
            'account_activation': 'account_activation',
            'password_reset': 'password_reset',
            'storage_warning': 'storage_warning',
            'storage_grace_period_start': 'storage_warning',
            'storage_grace_period_warning': 'storage_warning',
            'storage_grace_period_end': 'storage_warning',
            'subscription_created': 'subscription_created',
            'subscription_cancelled': 'payment_failed',
            'payment_failed': 'payment_failed',
            'payment_successful': 'subscription_created',
            'order_confirmation': 'order_confirmation',
            'order_shipped': 'order_confirmation',
            'maintenance_notification': 'maintenance_notification',
            'event_reminder': 'event_reminder',
            'task_assigned': 'task_assigned',
            'notification': 'notification',
            'marketing': 'marketing',
            'confirmation': 'confirmation',
            
            # Fallback mappings for new types
            'user_registration': 'welcome',
            'password_changed': 'notification',
            'login_notification': 'notification',
            'videos_archived': 'storage_warning',
            'files_archived': 'storage_warning',
            'backup_notification': 'notification',
            'subscription_renewed': 'subscription_created',
            'subscription_expired': 'payment_failed',
            'invoice': 'order_confirmation',
            'payment_reminder': 'payment_failed',
            'trial_ending': 'subscription_created',
            'trial_expired': 'payment_failed',
            'order_delivered': 'order_confirmation',
            'order_cancelled': 'notification',
            'cart_abandoned': 'marketing',
            'product_review_request': 'marketing',
            'return_request': 'notification',
            'refund_processed': 'confirmation',
            'support_ticket_created': 'notification',
            'support_ticket_updated': 'notification',
            'support_ticket_resolved': 'confirmation',
            'feedback_request': 'marketing',
            'survey_invitation': 'marketing',
            'bug_report_submitted': 'notification',
            'bug_report_response': 'notification',
            'system_update': 'maintenance_notification',
            'security_alert': 'notification',
            'feature_announcement': 'marketing',
            'service_disruption': 'maintenance_notification',
            'data_breach_notification': 'notification',
            'event_invitation': 'event_reminder',
            'event_cancelled': 'notification',
            'event_rescheduled': 'event_reminder',
            'task_reminder': 'task_assigned',
            'task_completed': 'confirmation',
            'task_overdue': 'task_assigned',
            'deadline_reminder': 'task_assigned',
            'newsletter': 'marketing',
            'marketing_campaign': 'marketing',
            'promotional_offer': 'marketing',
            'announcement': 'notification',
            'seasonal_greeting': 'marketing',
            'birthday_wish': 'marketing',
            'anniversary': 'marketing',
            'loyalty_reward': 'marketing',
            'referral_invitation': 'marketing',
            'activity_summary': 'notification',
            'achievement_unlocked': 'confirmation',
            'milestone_reached': 'confirmation',
            'inactivity_reminder': 'notification',
            're_engagement': 'marketing',
            'transactional': 'confirmation',
            'reminder': 'notification',
            'alert': 'notification',
            'info': 'notification',
            'custom': 'notification'
        }
        
        # Get template key, with fallback
        template_key = type_mapping.get(email_type, 'notification')
        
        # Get template based on mapped key
        template = templates.get(template_key, templates['notification'])
        
        # Customize based on description and tone
        subject = template['subject']
        html_content = template['html_content']
        variables = template['variables']
        
        # Tone adjustments
        if tone == 'friendly':
            subject = subject.replace('{{ firma }}', '{{ firma }} 😊')
        elif tone == 'formal':
            html_content = html_content.replace('Liebe/r', 'Sehr geehrte/r')
            html_content = html_content.replace('Herzliche Grüße', 'Mit freundlichen Grüßen')
        elif tone == 'enthusiastic':
            subject = '🎉 ' + subject + ' 🎉'
        
        return {
            'success': True,
            'content': {
                'subject': subject,
                'html_content': html_content,
                'text_content': self._html_to_text(html_content),
                'suggested_variables': variables if include_variables else {}
            },
            'is_fallback': True
        }
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text


# Global instance
ai_service = EmailAIService()