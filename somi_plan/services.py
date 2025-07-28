import json
import requests
from django.conf import settings
from django.utils import timezone
from .models import PostContent, PostTemplate, Platform


class SomiPlanAIService:
    """
    KI-Service für SoMi-Plan unter Verwendung der bestehenden KI-Integration
    """
    
    def __init__(self, user):
        self.user = user
        # API-Keys aus User-Modell laden (verschlüsselte Felder)
        self.openai_api_key = user.openai_api_key if hasattr(user, 'openai_api_key') and user.openai_api_key else None
        self.anthropic_api_key = user.anthropic_api_key if hasattr(user, 'anthropic_api_key') and user.anthropic_api_key else None
        self.google_api_key = user.google_api_key if hasattr(user, 'google_api_key') and user.google_api_key else None
        
        # Debug: API-Keys überprüfen
        print(f"DEBUG - User: {user.username}")
        print(f"DEBUG - OpenAI Key: {'Ja (' + str(len(self.openai_api_key)) + ' Zeichen)' if self.openai_api_key else 'Nein'}")
        print(f"DEBUG - Anthropic Key: {'Ja (' + str(len(self.anthropic_api_key)) + ' Zeichen)' if self.anthropic_api_key else 'Nein'}")
        print(f"DEBUG - Google Key: {'Ja (' + str(len(self.google_api_key)) + ' Zeichen)' if self.google_api_key else 'Nein'}")
        
        # Test: Prüfe ob Keys valide aussehen
        if self.openai_api_key:
            print(f"DEBUG - OpenAI Key start: {self.openai_api_key[:8]}...")
        if self.anthropic_api_key:
            print(f"DEBUG - Anthropic Key start: {self.anthropic_api_key[:8]}...")
        if self.google_api_key:
            print(f"DEBUG - Google Key start: {self.google_api_key[:8]}...")
    
    def generate_strategy(self, posting_plan):
        """
        Generiert eine Posting-Strategie basierend auf User-Input
        """
        try:
            # Erstelle System-Prompt für Strategie-Generierung
            system_prompt = f"""Du bist ein Experte für Social Media Marketing und Content-Strategie speziell für {posting_plan.platform.name}.

AUFGABE: Erstelle eine optimale Posting-Strategie basierend auf den User-Angaben.

PLATFORM-SPEZIFISCHE INFOS ({posting_plan.platform.name}):
- Zeichen-Limit: {posting_plan.platform.character_limit}
- Beste Zeiten: Variiert je nach Zielgruppe
- Content-Formate: Je nach Plattform optimiert

WICHTIGE REGELN:
1. Analysiere die Zielgruppe und erstelle passende Empfehlungen
2. Berücksichtige die verfügbaren Ressourcen
3. Fokussiere auf realistische, umsetzbare Strategien
4. Berücksichtige Plattform-spezifische Best Practices
5. Erstelle einen ausgewogenen Content-Mix

ANTWORT FORMAT (JSON):
{{
  "posting_frequency": "3_times_week",
  "best_times": ["evening", "midday"],
  "content_types": ["tips", "behind_scenes", "motivational"],
  "content_mix_percentages": {{"tips": 40, "behind_scenes": 30, "motivational": 20, "product": 10}},
  "strategic_recommendations": [
    "Fokussiere auf Storytelling - deine persönliche Geschichte resoniert stark",
    "Nutze Fragen und Umfragen für mehr Engagement",
    "Teile Behind-the-Scenes Content für Authentizität"
  ],
  "hashtag_strategy": "Mix aus 5-7 relevanten und nischigen Hashtags",
  "posting_times_explanation": "Deine Zielgruppe ist abends zwischen 18-20 Uhr am aktivsten",
  "frequency_explanation": "3x pro Woche ist optimal für konstante Präsenz ohne Überforderung"
}}"""

            user_prompt = f"""BENUTZER-PROFIL:
{posting_plan.user_profile}

ZIELGRUPPE:
{posting_plan.target_audience}

ZIELE:
{posting_plan.goals}

VISION:
{posting_plan.vision}

PLATTFORM: {posting_plan.platform.name}

Erstelle eine optimale Posting-Strategie für diesen Benutzer. Berücksichtige die Plattform-spezifischen Eigenarten von {posting_plan.platform.name} und die verfügbaren Ressourcen."""

            # Versuche KI-API Aufruf
            result = self._call_ai_api(system_prompt, user_prompt)
            
            if result['success']:
                try:
                    # Clean and prepare JSON response
                    clean_content = self._clean_json_response(result['content'])
                    strategy_data = json.loads(clean_content)
                    strategy_data['ai_generated_at'] = timezone.now().isoformat()
                    strategy_data['ai_model_used'] = result.get('model_used', 'Unknown')
                    return {
                        'success': True,
                        'strategy_data': strategy_data
                    }
                except json.JSONDecodeError:
                    # Fallback: Parse text response
                    return self._parse_strategy_from_text(result['content'])
            else:
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Strategie-Generierung fehlgeschlagen: {str(e)}'
            }
    
    def generate_posts(self, posting_plan, count=5):
        """
        Generiert Content-Posts basierend auf Strategie
        """
        try:
            strategy = posting_plan.strategy_data or {}
            content_types = strategy.get('content_types', ['tips', 'motivational', 'behind_scenes'])
            
            generated_posts = []
            
            for i in range(count):
                # Wähle Content-Typ basierend auf Strategie
                content_type = content_types[i % len(content_types)]
                
                # Hole passende Templates
                template = self._get_template_for_content_type(posting_plan.platform, content_type)
                
                # Generiere Post
                post_result = self._generate_single_post(posting_plan, content_type, template)
                
                if post_result['success']:
                    # Erstelle PostContent Objekt
                    post = PostContent.objects.create(
                        posting_plan=posting_plan,
                        title=post_result['title'],
                        content=post_result['content'],
                        script=post_result['script'],
                        hashtags=post_result['hashtags'],
                        call_to_action=post_result.get('call_to_action', ''),
                        post_type=content_type,
                        priority=post_result.get('priority', 2),
                        ai_generated=True,
                        ai_model_used=post_result.get('model_used', 'Unknown'),
                        ai_prompt_used=post_result.get('prompt_used', '')
                    )
                    generated_posts.append(post)
            
            return {
                'success': True,
                'posts': generated_posts,
                'count': len(generated_posts)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Post-Generierung fehlgeschlagen: {str(e)}'
            }
    
    def generate_more_ideas(self, posting_plan, existing_posts_count=0):
        """
        Generiert weitere kreative Post-Ideen (ohne Wiederholungen)
        """
        try:
            # Analysiere existierende Posts um Wiederholungen zu vermeiden
            existing_titles = list(posting_plan.posts.values_list('title', flat=True))
            existing_topics = [title.lower() for title in existing_titles]
            
            system_prompt = f"""Du bist ein kreativer Social Media Content-Experte für {posting_plan.platform.name}.

AUFGABE: Erstelle NEUE, EINZIGARTIGE Content-Ideen die sich von den existierenden unterscheiden.

EXISTIERENDE THEMEN (VERMEIDE WIEDERHOLUNGEN):
{', '.join(existing_topics) if existing_topics else 'Keine existierenden Posts'}

PLATTFORM: {posting_plan.platform.name} ({posting_plan.platform.character_limit} Zeichen)

WICHTIGE REGELN:
1. Erstelle völlig neue Themen und Ansätze
2. Vermeide Wiederholungen der existierenden Posts
3. Sei kreativ und denke outside the box
4. Halte dich an die Strategie aber bringe frische Perspektiven
5. Erstelle actionable, wertvolle Inhalte

ANTWORT FORMAT (JSON):
{{
  "posts": [
    {{
      "title": "Titel des Posts",
      "content": "Vollständiger Post-Content für {posting_plan.platform.name}",
      "script": "Detaillierte Anweisungen zur Umsetzung",
      "hashtags": "#relevante #hashtags #hier",
      "call_to_action": "Spezifische Handlungsaufforderung",
      "post_type": "tips|behind_scenes|motivational|product|educational",
      "priority": 1-3,
      "creative_angle": "Was macht diesen Post einzigartig?"
    }}
  ]
}}"""

            user_prompt = f"""USER-KONTEXT:
Profil: {posting_plan.user_profile}
Zielgruppe: {posting_plan.target_audience}
Ziele: {posting_plan.goals}

STRATEGIE:
{json.dumps(posting_plan.strategy_data, indent=2) if posting_plan.strategy_data else 'Keine spezifische Strategie'}

Erstelle 3 völlig neue, kreative Content-Ideen die sich von den {existing_posts_count} existierenden Posts unterscheiden. Denke innovativ und bringe frische Perspektiven ein!"""

            result = self._call_ai_api(system_prompt, user_prompt)
            
            if result['success']:
                try:
                    # Clean and prepare JSON response
                    clean_content = self._clean_json_response(result['content'])
                    response_data = json.loads(clean_content)
                    new_posts = []
                    
                    for post_data in response_data.get('posts', []):
                        post = PostContent.objects.create(
                            posting_plan=posting_plan,
                            title=post_data['title'],
                            content=post_data['content'],
                            script=post_data['script'],
                            hashtags=post_data.get('hashtags', ''),
                            call_to_action=post_data.get('call_to_action', ''),
                            post_type=post_data.get('post_type', 'tips'),
                            priority=post_data.get('priority', 2),
                            ai_generated=True,
                            ai_model_used=result.get('model_used', 'Unknown'),
                            ai_prompt_used=user_prompt
                        )
                        new_posts.append(post)
                    
                    return {
                        'success': True,
                        'posts': new_posts,
                        'count': len(new_posts)
                    }
                    
                except json.JSONDecodeError as e:
                    # Fallback: Parse text response and create posts
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"JSON parsing failed for generate_more_ideas: {e}")
                    logger.error(f"AI Response: {result['content'][:1000]}...")
                    logger.error(f"Cleaned content: {clean_content[:500]}...")
                    
                    try:
                        fallback_posts = self._parse_ideas_from_text(result['content'], posting_plan)
                        if fallback_posts:
                            return {
                                'success': True,
                                'posts': fallback_posts,
                                'count': len(fallback_posts),
                                'fallback_used': True
                            }
                    except Exception as fallback_error:
                        print(f"Fallback parsing also failed: {fallback_error}")
                    
                    return {
                        'success': False,
                        'error': f'KI-Antwort konnte nicht geparst werden. Details: {str(e)}'
                    }
            else:
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Idea-Generierung fehlgeschlagen: {str(e)}'
            }
    
    def _generate_single_post(self, posting_plan, content_type, template=None):
        """
        Generiert einen einzelnen Post
        """
        try:
            # Template-basierte oder freie Generierung
            if template:
                system_prompt = template.ai_system_prompt or self._get_default_system_prompt(posting_plan.platform, content_type)
                user_prompt_template = template.ai_user_prompt_template or self._get_default_user_prompt_template(content_type)
                
                # Template usage tracking
                template.increment_usage()
            else:
                system_prompt = self._get_default_system_prompt(posting_plan.platform, content_type)
                user_prompt_template = self._get_default_user_prompt_template(content_type)
            
            # Variablen im Template ersetzen
            user_prompt = user_prompt_template.format(
                zielgruppe=posting_plan.target_audience,
                thema=posting_plan.goals,
                business_kontext=posting_plan.user_profile,
                plattform=posting_plan.platform.name,
                zeichen_limit=posting_plan.platform.character_limit,
                content_type=content_type
            )
            
            result = self._call_ai_api(system_prompt, user_prompt)
            
            if result['success']:
                return self._parse_post_from_response(result['content'], content_type, result.get('model_used'))
            else:
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Post-Generierung fehlgeschlagen: {str(e)}'
            }
    
    def _call_ai_api(self, system_prompt, user_prompt):
        """
        Nutzt die bestehende KI-Integration (OpenAI oder Anthropic)
        """
        try:
            # Versuche OpenAI zuerst
            if self.openai_api_key:
                print("DEBUG - Versuche OpenAI API...")
                result = self._call_openai_api(system_prompt, user_prompt)
                print(f"DEBUG - OpenAI Result: {result.get('success', False)}")
                if result.get('success'):
                    return result
                else:
                    print(f"DEBUG - OpenAI Error: {result.get('error', 'Unknown')}")
            
            # Fallback zu Anthropic
            if self.anthropic_api_key:
                print("DEBUG - Versuche Anthropic API...")
                result = self._call_anthropic_api(system_prompt, user_prompt)
                if result['success']:
                    return result
            
            # Fallback zu Google Gemini
            if self.google_api_key:
                print("DEBUG - Versuche Google API...")
                result = self._call_gemini_api(system_prompt, user_prompt)
                if result['success']:
                    return result
            
            # Detaillierte Fehlermeldung
            available_keys = []
            if self.openai_api_key: available_keys.append("OpenAI")
            if self.anthropic_api_key: available_keys.append("Anthropic")  
            if self.google_api_key: available_keys.append("Google")
            
            if available_keys:
                error_msg = f'API-Keys verfügbar ({", ".join(available_keys)}), aber alle Aufrufe fehlgeschlagen.'
            else:
                error_msg = 'Kein API-Key verfügbar. Bitte konfiguriere OpenAI, Anthropic oder Google API-Key in den Einstellungen: http://127.0.0.1:8000/accounts/api-einstellungen/'
            
            return {
                'success': False,
                'error': error_msg
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'KI-API Aufruf fehlgeschlagen: {str(e)}'
            }
    
    def _call_openai_api(self, system_prompt, user_prompt, model=None):
        """
        OpenAI API Aufruf mit System- und User-Prompt
        """
        try:
            print(f"DEBUG - OpenAI API Aufruf gestartet mit Key: {self.openai_api_key[:10]}..." if self.openai_api_key else "Kein Key")
            
            headers = {
                'Authorization': f'Bearer {self.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Verwende das spezifizierte Modell oder User-Präferenz als Fallback
            user_preference = getattr(self.user, 'preferred_openai_model', 'gpt-4o-mini')
            selected_model = model or user_preference
            print(f"DEBUG - Model Parameter: {model}")
            print(f"DEBUG - User Preference: {user_preference}")
            print(f"DEBUG - Verwende OpenAI Modell: {selected_model}")
            
            data = {
                'model': selected_model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                'temperature': 0.8,  # Mehr Kreativität für Social Media Content
                'max_tokens': 2000
            }
            
            print("DEBUG - Sende Request an OpenAI...")
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            print(f"DEBUG - OpenAI Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print("DEBUG - OpenAI Aufruf erfolgreich")
                
                return {
                    'success': True,
                    'content': content,
                    'model_used': data['model'],
                    'usage': result.get('usage', {})
                }
            else:
                error_msg = f'OpenAI API Fehler: {response.status_code} - {response.text}'
                print(f"DEBUG - {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f'OpenAI API Aufruf fehlgeschlagen: {str(e)}'
            print(f"DEBUG - {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def _call_anthropic_api(self, system_prompt, user_prompt, model=None):
        """
        Anthropic API Aufruf mit System- und User-Prompt
        """
        try:
            print(f"DEBUG - Anthropic API Aufruf gestartet mit Key: {self.anthropic_api_key[:10]}..." if self.anthropic_api_key else "Kein Key")
            
            headers = {
                'x-api-key': self.anthropic_api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            # Verwende das spezifizierte Modell oder User-Präferenz als Fallback
            user_preference = getattr(self.user, 'preferred_anthropic_model', 'claude-3-5-sonnet-20241022')
            selected_model = model or user_preference
            print(f"DEBUG - Model Parameter: {model}")
            print(f"DEBUG - User Preference: {user_preference}")
            print(f"DEBUG - Verwende Anthropic Modell: {selected_model}")
            
            data = {
                'model': selected_model,
                'system': system_prompt,
                'messages': [
                    {'role': 'user', 'content': user_prompt}
                ],
                'max_tokens': 2000
            }
            
            print("DEBUG - Sende Request an Anthropic...")
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=30
            )
            
            print(f"DEBUG - Anthropic Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                print("DEBUG - Anthropic Aufruf erfolgreich")
                
                return {
                    'success': True,
                    'content': content,
                    'model_used': data['model'],
                    'usage': result.get('usage', {})
                }
            else:
                error_msg = f'Anthropic API Fehler: {response.status_code} - {response.text}'
                print(f"DEBUG - {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f'Anthropic API Aufruf fehlgeschlagen: {str(e)}'
            print(f"DEBUG - {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def _call_gemini_api(self, system_prompt, user_prompt):
        """
        Google Gemini API Aufruf
        """
        try:
            print(f"DEBUG - Gemini API Aufruf gestartet mit Key: {self.google_api_key[:10]}..." if self.google_api_key else "Kein Key")
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            # Verwende das spezifizierte Modell oder User-Präferenz als Fallback
            user_preference = getattr(self.user, 'preferred_gemini_model', 'gemini-pro')
            selected_model = getattr(self.user, 'preferred_gemini_model', 'gemini-pro')
            print(f"DEBUG - User Preference: {user_preference}")
            print(f"DEBUG - Verwende Gemini Modell: {selected_model}")
            
            # Kombiniere System- und User-Prompt für Gemini
            combined_prompt = f"{system_prompt}\n\nUser-Anfrage: {user_prompt}"
            
            data = {
                'contents': [{
                    'parts': [{
                        'text': combined_prompt
                    }]
                }],
                'generationConfig': {
                    'temperature': 0.8,
                    'maxOutputTokens': 2000,
                }
            }
            
            # Google AI API Endpoint
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent?key={self.google_api_key}'
            
            print("DEBUG - Sende Request an Gemini...")
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            print(f"DEBUG - Gemini Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    print("DEBUG - Gemini Aufruf erfolgreich")
                    
                    return {
                        'success': True,
                        'content': content,
                        'model_used': selected_model
                    }
                else:
                    error_msg = 'Gemini API: Keine Antwort erhalten'
                    print(f"DEBUG - {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg
                    }
            else:
                error_msg = f'Gemini API Fehler {response.status_code}: {response.text}'
                print(f"DEBUG - {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f'Gemini API Aufruf fehlgeschlagen: {str(e)}'
            print(f"DEBUG - {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def _get_template_for_content_type(self, platform, content_type):
        """
        Holt ein passendes Template für den Content-Typ
        """
        try:
            from .models import TemplateCategory
            
            categories = TemplateCategory.objects.filter(platform=platform)
            
            # Mapping von content_types zu Template-Kategorien
            category_mapping = {
                'tips': 'Tipps & Tricks',
                'behind_scenes': 'Behind the Scenes',
                'product': 'Produktvorstellung',
                'motivational': 'Motivation',
                'educational': 'Bildung'
            }
            
            category_name = category_mapping.get(content_type)
            if category_name:
                category = categories.filter(name=category_name).first()
                if category:
                    template = category.templates.filter(is_active=True).first()
                    return template
            
            return None
            
        except Exception:
            return None
    
    def _get_default_system_prompt(self, platform, content_type):
        """
        Standard System-Prompt je nach Plattform und Content-Typ
        """
        base_prompt = f"""Du bist ein Experte für {platform.name} Content-Erstellung mit Fokus auf {content_type}-Posts.

PLATTFORM-SPEZIFIKA ({platform.name}):
- Zeichen-Limit: {platform.character_limit}
- Zielgruppe: Plattform-spezifisch anpassen
- Stil: {self._get_platform_style(platform.name)}

WICHTIGE REGELN:
1. Erstelle authentischen, wertvollen Content
2. Verwende die richtige Ansprache für die Plattform
3. Halte dich an das Zeichen-Limit
4. Integriere relevante Hashtags natürlich
5. Erstelle klare Call-to-Actions
6. Achte auf Engagement-Optimierung

ANTWORT FORMAT (JSON):
{{
  "title": "Catchy Titel für den Post",
  "content": "Vollständiger Post-Text",
  "script": "Detaillierte Umsetzungsanweisungen",
  "hashtags": "#relevante #hashtags",
  "call_to_action": "Spezifische Handlungsaufforderung",
  "priority": 1-3
}}"""
        return base_prompt
    
    def _get_default_user_prompt_template(self, content_type):
        """
        Standard User-Prompt Template
        """
        templates = {
            'tips': """Erstelle einen wertvollen Tipp-Post für {zielgruppe} zum Thema {thema}.

KONTEXT:
- Business: {business_kontext}
- Plattform: {plattform}
- Zielgruppe: {zielgruppe}

Der Post soll praktisch umsetzbar sein und echten Mehrwert bieten.""",

            'behind_scenes': """Erstelle einen authentischen Behind-the-Scenes Post für {zielgruppe}.

KONTEXT:
- Business: {business_kontext}
- Plattform: {plattform}
- Zielgruppe: {zielgruppe}

Zeige Persönlichkeit und schaffe Verbindung zur Community.""",

            'motivational': """Erstelle einen inspirierenden, motivierenden Post für {zielgruppe}.

KONTEXT:
- Business: {business_kontext}
- Plattform: {plattform}
- Zielgruppe: {zielgruppe}
- Ziele: {thema}

Der Post soll ermutigen und zum Handeln inspirieren.""",

            'product': """Erstelle einen überzeugenden Post über ein Produkt/Service für {zielgruppe}.

KONTEXT:
- Business: {business_kontext}
- Plattform: {plattform}
- Zielgruppe: {zielgruppe}

Fokussiere auf Nutzen und Mehrwert, nicht auf Verkauf.""",

            'educational': """Erstelle einen lehrreichen, informativen Post für {zielgruppe}.

KONTEXT:
- Business: {business_kontext}
- Plattform: {plattform}
- Zielgruppe: {zielgruppe}
- Thema: {thema}

Erkläre komplexe Themen einfach und verständlich."""
        }
        
        return templates.get(content_type, templates['tips'])
    
    def _get_platform_style(self, platform_name):
        """
        Plattform-spezifische Stil-Richtlinien
        """
        styles = {
            'Instagram': 'Visual-first, Storytelling, Emojis, Hashtag-optimiert',
            'LinkedIn': 'Professional, Business-fokussiert, Networking, längere Texte',
            'Twitter/X': 'Kurz & prägnant, Trending Topics, Conversation-Starter',
            'Facebook': 'Community-orientiert, Diskussionen, längere Texte möglich',
            'TikTok': 'Trend-orientiert, jung & dynamisch, Video-Content',
            'YouTube': 'Educational, längere Formate, SEO-optimiert',
            'Pinterest': 'Visual & inspirational, DIY-orientiert, suchoptimiert'
        }
        return styles.get(platform_name, 'Authentisch und zielgruppengerecht')
    
    def _parse_post_from_response(self, response_text, content_type, model_used):
        """
        Parst KI-Antwort zu Post-Daten
        """
        try:
            # Clean and prepare JSON response
            clean_content = self._clean_json_response(response_text)
            # Versuche JSON zu parsen
            data = json.loads(clean_content)
            return {
                'success': True,
                'title': data.get('title', f'{content_type.title()} Post'),
                'content': data.get('content', ''),
                'script': data.get('script', ''),
                'hashtags': data.get('hashtags', ''),
                'call_to_action': data.get('call_to_action', ''),
                'priority': data.get('priority', 2),
                'model_used': model_used,
                'prompt_used': 'AI Generated'
            }
        except json.JSONDecodeError:
            # Fallback: Text-basierte Extraktion
            return self._extract_post_from_text(response_text, content_type, model_used)
    
    def _extract_post_from_text(self, text, content_type, model_used):
        """
        Extrahiert Post-Daten aus Freitext-Antwort
        """
        import re
        
        # Einfache Regex-Extraktion als Fallback
        title_match = re.search(r'titel?[:\s]*(.+)', text, re.IGNORECASE)
        content_match = re.search(r'content[:\s]*(.+?)(?=script|hashtag|$)', text, re.IGNORECASE | re.DOTALL)
        script_match = re.search(r'script[:\s]*(.+?)(?=hashtag|call.*action|$)', text, re.IGNORECASE | re.DOTALL)
        hashtag_match = re.search(r'hashtag[s]?[:\s]*(.+)', text, re.IGNORECASE)
        
        return {
            'success': True,
            'title': title_match.group(1).strip() if title_match else f'{content_type.title()} Post',
            'content': content_match.group(1).strip() if content_match else text[:500],
            'script': script_match.group(1).strip() if script_match else 'Standard Umsetzung',
            'hashtags': hashtag_match.group(1).strip() if hashtag_match else f'#{content_type}',
            'call_to_action': 'Folge für mehr Tipps!',
            'priority': 2,
            'model_used': model_used,
            'prompt_used': 'AI Generated (Text Fallback)'
        }
    
    def _parse_ideas_from_text(self, text, posting_plan):
        """
        Fallback für Post-Ideen-Parsing aus Freitext wenn JSON fehlschlägt
        """
        try:
            # Versuche Text in Abschnitte zu teilen und Posts zu extrahieren
            posts = []
            
            # Suche nach verschiedenen Strukturmustern
            import re
            
            # Muster 1: Titel in Anführungszeichen oder als Überschrift
            title_patterns = [
                r'"([^"]+)"',  # "Titel in Anführungszeichen"
                r'Titel:?\s*(.+?)(?:\n|$)',  # Titel: Text
                r'(\d+\.)\s*(.+?)(?:\n|$)',  # 1. Titel
                r'##?\s*(.+?)(?:\n|$)',  # ## Titel oder # Titel
            ]
            
            # Extrahiere potentielle Titel
            potential_titles = []
            for pattern in title_patterns:
                matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    title = match[1] if isinstance(match, tuple) else match
                    title = title.strip()
                    if len(title) > 10 and len(title) < 100:  # Sinnvolle Länge
                        potential_titles.append(title)
            
            # Fallback: Generiere Posts basierend auf gefundenen Titeln oder Standard-Posts
            if not potential_titles:
                # Standardisierte Fallback-Posts
                potential_titles = [
                    "5 Tipps für mehr Erfolg im Alltag",
                    "Behind the Scenes: Ein Tag in meinem Leben", 
                    "Was ich diese Woche gelernt habe"
                ]
            
            # Erstelle Posts aus den Titeln (max 3)
            for i, title in enumerate(potential_titles[:3]):
                # Generiere einfachen Content basierend auf Titel
                content = self._generate_fallback_content(title, posting_plan)
                script = self._generate_fallback_script(title, posting_plan)
                
                post = PostContent.objects.create(
                    posting_plan=posting_plan,
                    title=title,
                    content=content,
                    script=script,
                    hashtags="#inspiration #tipps #motivation",
                    call_to_action="Was denkst du darüber? Schreib es in die Kommentare!",
                    post_type="tips",
                    priority=2,
                    ai_generated=True,
                    ai_model_used="Fallback Parser",
                    ai_prompt_used="Fallback aufgrund JSON-Parsing-Fehler"
                )
                posts.append(post)
            
            return posts
            
        except Exception as e:
            print(f"Fallback parsing error: {e}")
            return None
    
    def _generate_fallback_content(self, title, posting_plan):
        """Generiert einfachen Fallback-Content"""
        platform_name = posting_plan.platform.name
        char_limit = posting_plan.platform.character_limit
        
        # Basis-Content Template
        content = f"""💡 {title}

Hey Community! 👋

Heute möchte ich mit euch ein wichtiges Thema teilen.

✨ Warum ist das relevant?
- Es hilft dir im Alltag
- Bringt dich deinen Zielen näher  
- Ist einfach umsetzbar

💪 Mein Tipp: Fang klein an und bleib dran!

Was sind eure Erfahrungen damit? 
Teilt gerne eure Gedanken! 👇

#tipps #motivation #erfolg"""
        
        # Kürze wenn nötig für Plattform
        if len(content) > char_limit:
            content = content[:char_limit-20] + "...\n\n#tipps #motivation"
        
        return content
    
    def _generate_fallback_script(self, title, posting_plan):
        """Generiert einfaches Fallback-Script"""
        return f"""POST-UMSETZUNG: {title}

🎯 ZIEL: Wertvolle Tipps teilen und Community-Engagement fördern

📱 ANWEISUNGEN:
1. Mit freundlicher Begrüßung starten
2. Relevanz des Themas erklären
3. Konkrete, umsetzbare Tipps geben
4. Community zur Interaktion einladen
5. Relevante Hashtags für Reichweite verwenden

⏰ BESTE POSTING-ZEIT: Abends zwischen 18-20 Uhr
📊 ZIEL: Hohe Interaktionsrate durch praktischen Wert
🎨 VISUAL: Passende Grafik oder Foto zum Thema
💬 FOLLOW-UP: Aktiv auf Kommentare antworten"""

    def _clean_json_response(self, content):
        """
        Bereinigt AI-Response für JSON-Parsing
        """
        import re
        import logging
        
        logger = logging.getLogger(__name__)
        original_content = content
        
        # Entferne Markdown Code-Blöcke
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE)
        
        # Entferne führende/nachfolgende Erklärungen
        content = content.strip()
        
        # Suche nach JSON-Start und -Ende
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            content = content[json_start:json_end]
        else:
            logger.warning(f"Could not find valid JSON boundaries in content: {content[:200]}...")
        
        # Entferne mögliche Kommentare im JSON
        content = re.sub(r'//.*?(?=\n|$)', '', content, flags=re.MULTILINE)
        
        # Ersetze häufige Formatierungsprobleme
        content = content.replace('\n', ' ')  # Entferne Zeilenumbrüche
        content = re.sub(r'\s+', ' ', content)  # Normalisiere Whitespace
        
        cleaned = content.strip()
        
        # Log the cleaning process for debugging
        if len(cleaned) < len(original_content) * 0.5:  # If we lost more than 50% of content
            logger.warning(f"Significant content loss during cleaning. Original: {len(original_content)}, Cleaned: {len(cleaned)}")
        
        return cleaned

    def _parse_strategy_from_text(self, text):
        """
        Fallback für Strategie-Parsing aus Freitext
        """
        # Einfache Fallback-Strategie
        return {
            'success': True,
            'strategy_data': {
                'posting_frequency': '3_times_week',
                'best_times': ['evening', 'midday'],
                'content_types': ['tips', 'behind_scenes', 'motivational'],
                'strategic_recommendations': [
                    'Fokussiere auf wertvollen Content',
                    'Nutze Storytelling für Authentizität',
                    'Interagiere aktiv mit der Community'
                ],
                'ai_generated_at': timezone.now().isoformat(),
                'fallback_used': True,
                'original_text': text
            }
        }