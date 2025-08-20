import json
import requests
import openai
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from .models import Campaign, Creative, AIService, GenerationJob
from .api_client import CentralAPIClient
from .image_utils import download_and_store_dalle_image
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class AICreativeGenerator:
    """
    Service für die KI-gestützte Creative-Generierung
    """
    
    def __init__(self, user: User):
        self.user = user
        # Verwende den zentralen API-Client
        self.api_client = CentralAPIClient(user)
        
        # Hole API-Keys über den zentralen Client
        api_keys = self.api_client.get_api_keys()
        self.openai_api_key = api_keys.get('openai')
        self.anthropic_api_key = api_keys.get('anthropic')
        self.google_api_key = api_keys.get('google')
        
        # Billing-Status Tracking
        self._billing_limit_reached = False
        self._quota_exceeded = False
        
        # Debug-Ausgabe für API-Key Status
        logger.info(f"AICreativeGenerator für User {user.username} initialisiert:")
        logger.info(f"  - OpenAI: {'✓ verfügbar' if self.openai_api_key else '✗ nicht konfiguriert'}")
        logger.info(f"  - Anthropic: {'✓ verfügbar' if self.anthropic_api_key else '✗ nicht konfiguriert'}")
        logger.info(f"  - Google: {'✓ verfügbar' if self.google_api_key else '✗ nicht konfiguriert'}")
    
    def get_billing_status(self):
        """
        Gibt den aktuellen Billing-Status zurück
        """
        if self._billing_limit_reached:
            return {
                'status': 'error',
                'message': 'OpenAI Billing-Limit erreicht',
                'detail': 'Das monatliche Ausgabenlimit für OpenAI wurde überschritten. Bitte überprüfen Sie Ihr OpenAI-Konto.'
            }
        elif self._quota_exceeded:
            return {
                'status': 'warning', 
                'message': 'OpenAI Guthaben erschöpft',
                'detail': 'Ihr OpenAI-Guthaben ist aufgebraucht. Bitte laden Sie Ihr Konto auf.'
            }
        else:
            return {
                'status': 'ok',
                'message': 'Billing-Status normal',
                'detail': 'Keine Billing-Probleme erkannt.'
            }
    
    def generate_creatives(
        self, 
        campaign: Campaign, 
        count: int = 10,
        ai_service: str = 'openai',
        style_preference: str = 'modern',
        color_scheme: str = 'vibrant',
        target_audience: str = '',
        custom_instructions: str = '',
        existing_examples: List[Dict] = None
    ) -> List[Creative]:
        """
        Generiert Creatives für eine Kampagne
        """
        try:
            # Generation Job erstellen
            job = GenerationJob.objects.create(
                campaign=campaign,
                job_type='initial',
                target_count=count,
                status='processing',
                started_at=timezone.now()
            )
            
            # Prompt für Text-Generierung erstellen
            text_prompt = self._build_text_prompt(
                campaign, style_preference, target_audience, custom_instructions, existing_examples
            )
            
            # Image-Prompt erstellen
            image_prompt = self._build_image_prompt(
                campaign, style_preference, color_scheme
            )
            
            creatives = []
            batch_number = self._get_next_batch_number(campaign)
            
            for i in range(count):
                try:
                    # Text generieren
                    creative_text = self._generate_text(text_prompt, ai_service)
                    
                    # Bild generieren
                    image_url = self._generate_image(image_prompt, ai_service)
                    
                    # Creative erstellen
                    creative = Creative.objects.create(
                        campaign=campaign,
                        title=f"Creative {i+1}",
                        description=creative_text.get('description', ''),
                        text_content=creative_text.get('content', ''),
                        image_url=image_url,
                        ai_prompt_used=json.dumps({
                            'text_prompt': text_prompt,
                            'image_prompt': image_prompt
                        }),
                        generation_status='completed',
                        generation_batch=batch_number
                    )
                    
                    # DALL-E Bild sofort lokal speichern um 403-Fehler zu vermeiden
                    if image_url and ('openai' in image_url or 'dalle' in image_url.lower()):
                        logger.info(f"Downloading DALL-E image for Creative {creative.id}")
                        local_path = download_and_store_dalle_image(image_url, str(creative.id))
                        if local_path:
                            creative.image_file.name = local_path
                            creative.save(update_fields=['image_file'])
                            logger.info(f"✅ DALL-E image stored locally for Creative {creative.id}")
                        else:
                            logger.warning(f"⚠️ Failed to download DALL-E image for Creative {creative.id}")
                    
                    creatives.append(creative)
                    
                    # Job-Fortschritt aktualisieren
                    job.generated_count = i + 1
                    job.save()
                    
                except Exception as e:
                    logger.error(f"Fehler bei Creative-Generierung {i+1}: {str(e)}")
                    continue
            
            # Job als abgeschlossen markieren
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'completed_at'])
            
            return creatives
            
        except Exception as e:
            logger.error(f"Fehler bei Creative-Generierung: {str(e)}")
            if 'job' in locals():
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = timezone.now()
                job.save(update_fields=['status', 'error_message', 'completed_at'])
            return []
    
    def generate_more_creatives(
        self, 
        campaign: Campaign, 
        count: int = 5,
        **kwargs
    ) -> List[Creative]:
        """
        Generiert weitere Creatives für eine bestehende Kampagne
        """
        # Batch-Nummer für neue Creatives
        batch_number = self._get_next_batch_number(campaign)
        
        # Bestehende Creatives analysieren für bessere Prompts
        existing_creatives = campaign.creatives.filter(
            generation_status='completed'
        ).order_by('-created_at')[:5]
        
        # Prompt basierend auf bestehenden Creatives anpassen
        kwargs['existing_examples'] = [
            {
                'title': c.title,
                'text': c.text_content,
                'description': c.description
            }
            for c in existing_creatives
        ]
        
        # Übergebe alle Parameter explizit an generate_creatives
        return self.generate_creatives(
            campaign=campaign, 
            count=count, 
            ai_service=kwargs.get('ai_service', 'openai'),
            style_preference=kwargs.get('style_preference', 'modern'),
            color_scheme=kwargs.get('color_scheme', 'vibrant'),
            target_audience=kwargs.get('target_audience', ''),
            custom_instructions=kwargs.get('custom_instructions', ''),
            existing_examples=kwargs.get('existing_examples')
        )
    
    def revise_creative(
        self, 
        original_creative: Creative,
        revision_instructions: str,
        revision_type: str = 'both'
    ) -> Optional[Creative]:
        """
        Überarbeitet ein bestehendes Creative
        """
        try:
            logger.info(f"Starting creative revision for {original_creative.id}")
            logger.info(f"Revision type: {revision_type}")
            logger.info(f"Instructions: {revision_instructions}")
            
            # API-Key-Validierung
            if revision_type in ['text_only', 'both', 'image_only'] and not self.openai_api_key:
                raise ValueError("OpenAI API-Key ist erforderlich für Creative-Überarbeitung")
            
            campaign = original_creative.campaign
            
            # Text-Revision
            if revision_type in ['text_only', 'both']:
                logger.info("Generating revised text...")
                text_prompt = self._build_revision_text_prompt(
                    original_creative, revision_instructions
                )
                new_text = self._generate_text(text_prompt, 'openai')
                logger.info(f"Text revision completed: {new_text}")
            else:
                new_text = {
                    'content': original_creative.text_content,
                    'description': original_creative.description
                }
            
            # Bild-Revision
            if revision_type in ['image_only', 'both']:
                logger.info("Generating revised image...")
                image_prompt = self._build_revision_image_prompt(
                    original_creative, revision_instructions
                )
                new_image_url = self._generate_image(image_prompt, 'openai')
                logger.info(f"Image revision completed: {new_image_url}")
            else:
                new_image_url = original_creative.image_url
                logger.info("Using original image URL")
            
            # Validierung der generierten Inhalte
            if not new_text or not new_text.get('content'):
                raise ValueError("Text-Generierung fehlgeschlagen")
            
            if revision_type in ['image_only', 'both'] and not new_image_url:
                # Prüfe Billing-Status für bessere Fehlermeldung
                billing_status = self.get_billing_status()
                if billing_status['status'] in ['error', 'warning']:
                    raise ValueError(f"Bild-Generierung fehlgeschlagen: {billing_status['detail']}")
                else:
                    raise ValueError("Bild-Generierung fehlgeschlagen")
            
            # Überarbeitetes Creative erstellen
            logger.info("Creating revised creative...")
            revised_creative = Creative.objects.create(
                campaign=campaign,
                title=f"{original_creative.title} (Überarbeitet)",
                description=new_text.get('description', original_creative.description),
                text_content=new_text.get('content', original_creative.text_content),
                image_url=new_image_url,
                ai_prompt_used=json.dumps({
                    'revision_instructions': revision_instructions,
                    'original_creative_id': str(original_creative.id),
                    'revision_type': revision_type
                }),
                generation_status='completed',
                generation_batch=original_creative.generation_batch
            )
            
            # DALL-E Bild sofort lokal speichern um 403-Fehler zu vermeiden
            if new_image_url and ('openai' in new_image_url or 'dalle' in new_image_url.lower()):
                logger.info(f"Downloading DALL-E image for revised Creative {revised_creative.id}")
                local_path = download_and_store_dalle_image(new_image_url, str(revised_creative.id))
                if local_path:
                    revised_creative.image_file.name = local_path
                    revised_creative.save(update_fields=['image_file'])
                    logger.info(f"✅ DALL-E image stored locally for revised Creative {revised_creative.id}")
                else:
                    logger.warning(f"⚠️ Failed to download DALL-E image for revised Creative {revised_creative.id}")
            
            logger.info(f"Creative revision successful: {revised_creative.id}")
            return revised_creative
            
        except Exception as e:
            logger.error(f"Fehler bei Creative-Überarbeitung: {str(e)}", exc_info=True)
            raise e  # Re-raise für bessere Fehlerbehandlung in der View
    
    def _build_text_prompt(
        self, 
        campaign: Campaign,
        style_preference: str,
        target_audience: str,
        custom_instructions: str,
        existing_examples: List[Dict] = None
    ) -> str:
        """
        Erstellt den Prompt für Text-Generierung mit Referenzbild-Kontext
        """
        prompt = f"""
        Erstelle einen ansprechenden Werbetext für folgende Kampagne:
        
        Kampagne: {campaign.name}
        Grundidee: {campaign.basic_idea}
        Detailbeschreibung: {campaign.detailed_description or 'Nicht angegeben'}
        
        Stil: {style_preference}
        Zielgruppe: {target_audience or 'Allgemein'}
        
        Zusätzliche Informationen: {campaign.additional_info or 'Keine'}
        Web-Links: {campaign.web_links or 'Keine'}
        Spezielle Anweisungen: {custom_instructions or 'Keine'}
        """
        
        # Referenzbild-Analysen hinzufügen
        reference_context = self._get_reference_image_context(campaign)
        if reference_context:
            prompt += f"\n\nREFERENZBILD-KONTEXT:\n{reference_context}\n"
        
        prompt += """
        Erstelle einen kreativen Werbetext, der:
        1. Aufmerksamkeit erregt
        2. Die Hauptbotschaft klar vermittelt
        3. Zur Aktion motiviert
        4. Zum gewählten Stil passt
        5. Die Zielgruppe anspricht
        6. Die Stil-Elemente der Referenzbilder berücksichtigt (falls vorhanden)
        
        Antworte im JSON-Format:
        {{
            "content": "Der Haupttext für das Creative",
            "description": "Eine kurze Beschreibung des Creative-Konzepts"
        }}
        """
        
        if existing_examples:
            prompt += "\n\nBerücksichtige diese bestehenden Beispiele für Konsistenz:\n"
            for example in existing_examples:
                prompt += f"- {example['title']}: {example['text'][:100]}...\n"
        
        return prompt.strip()
    
    def _build_image_prompt(
        self, 
        campaign: Campaign,
        style_preference: str,
        color_scheme: str
    ) -> str:
        """
        Erstellt den Prompt für Bild-Generierung mit Referenzbild-Kontext
        """
        prompt = f"""
        Create an advertising image for: {campaign.basic_idea}
        
        Style: {style_preference}
        Color scheme: {color_scheme}
        
        Requirements:
        - High quality, professional advertising image
        - Clear visual hierarchy
        - Suitable for digital advertising
        - Engaging and eye-catching
        - {style_preference} design aesthetic
        - {color_scheme} color palette
        
        Additional context: {campaign.detailed_description or ''}
        Additional info: {campaign.additional_info or ''}
        """
        
        # Referenzbild-Kontext für Bildgenerierung hinzufügen
        reference_context = self._get_reference_image_context(campaign, for_image_generation=True)
        if reference_context:
            prompt += f"\n\nREFERENCE STYLE GUIDANCE:\n{reference_context}"
        
        return prompt.strip()
    
    def _get_reference_image_context(self, campaign: Campaign, for_image_generation: bool = False) -> str:
        """
        Extrahiert Referenzbild-Kontext für Prompt-Erstellung
        
        Args:
            campaign: Campaign object
            for_image_generation: If True, formats context for image prompts
            
        Returns:
            Formatted reference context string
        """
        try:
            reference_images = campaign.reference_images.all()
            if not reference_images.exists():
                return ""
            
            context_parts = []
            
            for i, ref_image in enumerate(reference_images[:5], 1):  # Limit to 5 images
                # Try to extract analysis from description
                description = ref_image.description or ""
                
                # Look for AI-analysis markers in description
                if "KI-analysiert:" in description:
                    # Extract the AI analysis part
                    ai_part = description.split("KI-analysiert:")[-1].strip()
                    if for_image_generation:
                        context_parts.append(f"Reference {i}: {ai_part}")
                    else:
                        context_parts.append(f"Referenzbild {i}: {ai_part}")
                        
                elif "von https://" in description or "Auto-downloaded" in description:
                    # This is a URL-downloaded image
                    clean_desc = description.replace("Auto-downloaded from:", "").strip()
                    clean_desc = clean_desc.split("(von https://")[0].strip()
                    if clean_desc:
                        if for_image_generation:
                            context_parts.append(f"Reference {i}: {clean_desc}")
                        else:
                            context_parts.append(f"Referenzbild {i}: {clean_desc}")
                            
                else:
                    # Regular description
                    if description.strip():
                        if for_image_generation:
                            context_parts.append(f"Reference {i}: {description.strip()}")
                        else:
                            context_parts.append(f"Referenzbild {i}: {description.strip()}")
            
            if not context_parts:
                return ""
            
            if for_image_generation:
                # Format for image generation (more concise)
                header = f"Based on {len(context_parts)} reference image(s), incorporate these visual elements:"
                return header + "\n- " + "\n- ".join(context_parts)
            else:
                # Format for text generation (more detailed)
                header = f"Die Kampagne hat {len(context_parts)} Referenzbild(er) mit folgenden Stil-Elementen:"
                return header + "\n- " + "\n- ".join(context_parts)
                
        except Exception as e:
            logger.warning(f"Error extracting reference image context: {str(e)}")
            return ""
    
    def _build_revision_text_prompt(
        self, 
        original_creative: Creative,
        revision_instructions: str
    ) -> str:
        """
        Erstellt Prompt für Text-Überarbeitung
        """
        return f"""
        Überarbeite folgenden Werbetext basierend auf den Anweisungen:
        
        Original Text: {original_creative.text_content}
        Original Beschreibung: {original_creative.description}
        
        Überarbeitungsanweisungen: {revision_instructions}
        
        Antworte im JSON-Format:
        {{
            "content": "Der überarbeitete Haupttext",
            "description": "Überarbeitete Beschreibung"
        }}
        """
    
    def _build_revision_image_prompt(
        self, 
        original_creative: Creative,
        revision_instructions: str
    ) -> str:
        """
        Erstellt Prompt für Bild-Überarbeitung
        """
        return f"""
        Revise this advertising image concept based on instructions:
        
        Original concept: {original_creative.description}
        Revision instructions: {revision_instructions}
        
        Create a new advertising image that incorporates these changes while maintaining professional quality.
        """
    
    def _generate_text(self, prompt: str, ai_service: str) -> Dict[str, str]:
        """
        Generiert Text mit der gewählten KI
        """
        logger.info(f"Text-Generierung angefordert - Service: {ai_service}")
        
        if ai_service == 'openai':
            if self.openai_api_key:
                logger.info("Verwende OpenAI für Text-Generierung")
                return self._generate_text_openai(prompt)
            else:
                logger.warning("OpenAI angefordert, aber kein API-Key verfügbar - verwende Mock")
        elif ai_service == 'claude':
            if self.anthropic_api_key:
                logger.info("Verwende Claude für Text-Generierung")
                return self._generate_text_claude(prompt)
            else:
                logger.warning("Claude angefordert, aber kein API-Key verfügbar - verwende Mock")
        elif ai_service == 'google':
            if self.google_api_key:
                logger.info("Verwende Google AI für Text-Generierung")
                return self._generate_text_google(prompt)
            else:
                logger.warning("Google AI angefordert, aber kein API-Key verfügbar - verwende Mock")
        
        # Fallback für Demo-Zwecke
        logger.info("Verwende Mock-Text-Generierung")
        return self._generate_mock_text(prompt)
    
    def _generate_image(self, prompt: str, ai_service: str) -> str:
        """
        Generiert Bild mit der gewählten KI
        """
        logger.info(f"Bildgenerierung angefordert - Service: {ai_service}")
        
        if ai_service == 'openai':
            if self.openai_api_key:
                logger.info("Verwende DALL-E für Bildgenerierung")
                return self._generate_image_dalle(prompt)
            else:
                logger.warning("OpenAI angefordert, aber kein API-Key verfügbar - verwende Mock-Bild")
        else:
            logger.info(f"Service {ai_service} noch nicht für Bildgenerierung implementiert - verwende Mock")
        
        # Fallback für Demo-Zwecke
        logger.info("Verwende Mock-Bildgenerierung")
        return self._generate_mock_image(prompt)
    
    def _generate_text_openai(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit OpenAI (aktualisierte API)
        """
        try:
            from openai import OpenAI
            
            # OpenAI Client mit API-Key initialisieren
            client = OpenAI(api_key=self.openai_api_key)
            
            logger.info(f"Starte OpenAI Text-Generierung für User {self.user.username}")
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Du bist ein kreativer Werbetexter. Antworte immer im JSON-Format mit 'content' und 'description' Feldern."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            logger.info(f"OpenAI Text erfolgreich generiert: {content[:100]}...")
            
            # JSON-Antwort parsen
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                # Fallback wenn nicht JSON
                return {
                    "content": content,
                    "description": "KI-generierter Werbetext"
                }
                
        except Exception as e:
            logger.error(f"OpenAI Text-Generierung Fehler: {str(e)}")
            logger.error(f"API-Key verfügbar: {bool(self.openai_api_key)}")
            return self._generate_mock_text(prompt)
    
    def _generate_image_dalle(self, prompt: str) -> str:
        """
        Bild-Generierung mit DALL-E (aktualisierte API)
        """
        try:
            from openai import OpenAI
            
            # OpenAI Client mit API-Key initialisieren
            client = OpenAI(api_key=self.openai_api_key)
            
            logger.info(f"Starte DALL-E Bildgenerierung für User {self.user.username}")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            response = client.images.generate(
                model="dall-e-3",  # Neuestes DALL-E Modell
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            logger.info(f"DALL-E Bild erfolgreich generiert: {image_url}")
            
            return image_url
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"DALL-E Bild-Generierung Fehler: {error_message}")
            logger.error(f"API-Key verfügbar: {bool(self.openai_api_key)}")
            logger.error(f"Prompt: {prompt}")
            
            # Spezifische Fehlermeldung für Billing-Probleme
            if 'billing_hard_limit_reached' in error_message:
                logger.warning("⚠️ OpenAI Billing-Limit erreicht - Platzhalter wird verwendet")
                self._billing_limit_reached = True  # Merke für spätere Checks
            elif 'insufficient_quota' in error_message:
                logger.warning("⚠️ OpenAI Guthaben erschöpft - Platzhalter wird verwendet")
                self._quota_exceeded = True
            
            # Fallback zu DALL-E 2 versuchen (nur wenn nicht Billing-Problem)
            if 'billing_hard_limit_reached' not in error_message and 'insufficient_quota' not in error_message:
                try:
                    logger.info("Versuche DALL-E 2 Fallback...")
                    client = OpenAI(api_key=self.openai_api_key)
                    response = client.images.generate(
                        model="dall-e-2",
                        prompt=prompt[:1000],  # DALL-E 2 hat kürzere Prompt-Limits
                        size="1024x1024",
                        n=1,
                    )
                    image_url = response.data[0].url
                    logger.info(f"DALL-E 2 Fallback erfolgreich: {image_url}")
                    return image_url
                except Exception as e2:
                    logger.error(f"DALL-E 2 Fallback auch fehlgeschlagen: {str(e2)}")
            
            return self._generate_mock_image(prompt)
    
    def _generate_text_claude(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit Claude (Placeholder)
        """
        # TODO: Implementierung der Claude API
        return self._generate_mock_text(prompt)
    
    def _generate_text_google(self, prompt: str) -> Dict[str, str]:
        """
        Text-Generierung mit Google AI (Placeholder)
        """
        # TODO: Implementierung der Google AI API
        return self._generate_mock_text(prompt)
    
    def _generate_mock_text(self, prompt: str) -> Dict[str, str]:
        """
        Mock Text-Generierung für Demo-Zwecke
        """
        import random
        
        mock_contents = [
            "🚀 Revolutioniere dein Business! Entdecke unsere innovative Lösung und steigere deinen Erfolg um 300%!",
            "✨ Das Geheimnis erfolgreicher Unternehmen! Jetzt verfügbar und nur für kurze Zeit zum Sonderpreis!",
            "🎯 Erreiche deine Ziele schneller als je zuvor! Mit unserer bewährten Methode zum garantierten Erfolg!",
            "💡 Innovation trifft auf Effizienz! Transformiere deine Arbeitsweise mit unserem bahnbrechenden Tool!",
            "🌟 Werde zum Marktführer! Nutze die Chance und sichere dir deinen Wettbewerbsvorteil!"
        ]
        
        mock_descriptions = [
            "Dynamisches Creative mit kraftvoller Call-to-Action",
            "Emotionales Marketing-Creative für maximale Conversion",
            "Professionelles Business-Creative mit modernem Design",
            "Innovatives Product-Creative für Tech-Zielgruppe",
            "Motivierendes Service-Creative mit persönlicher Note"
        ]
        
        return {
            "content": random.choice(mock_contents),
            "description": random.choice(mock_descriptions)
        }
    
    def _generate_mock_image(self, prompt: str) -> str:
        """
        Mock Bild-URL für Demo-Zwecke - erstellt vielfältige Fallback-Bilder
        """
        import random
        from django.conf import settings
        
        logger.warning(f"Mock-Bild als SVG generiert für User {self.user.username}")
        logger.warning("Konfigurieren Sie einen OpenAI API-Key für echte DALL-E Bilder!")
        
        # Erstelle verschiedene SVG-Designs basierend auf dem Prompt
        return self._create_diverse_svg_fallback(prompt)
    
    def _create_diverse_svg_fallback(self, prompt: str = "") -> str:
        """
        Erstellt vielfältige SVG Fallback-Bilder basierend auf dem Prompt
        """
        import random
        import hashlib
        
        # Erstelle deterministische Zufälligkeit basierend auf Prompt
        if prompt:
            seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
            random.seed(seed)
        
        # Verschiedene Design-Variationen
        designs = [
            {
                'bg': '#f8f9fa', 'accent': '#007bff', 'text': '#495057',
                'icon': '🎨', 'title': 'Creative Design', 'pattern': 'gradient'
            },
            {
                'bg': '#fff3cd', 'accent': '#ffc107', 'text': '#856404',
                'icon': '✨', 'title': 'Premium Content', 'pattern': 'circles'
            },
            {
                'bg': '#d1ecf1', 'accent': '#17a2b8', 'text': '#0c5460',
                'icon': '🚀', 'title': 'Innovation Hub', 'pattern': 'lines'
            },
            {
                'bg': '#d4edda', 'accent': '#28a745', 'text': '#155724',
                'icon': '💡', 'title': 'Bright Ideas', 'pattern': 'dots'
            },
            {
                'bg': '#f8d7da', 'accent': '#dc3545', 'text': '#721c24',
                'icon': '🎯', 'title': 'Target Focus', 'pattern': 'waves'
            },
            {
                'bg': '#e2e3e5', 'accent': '#6c757d', 'text': '#383d41',
                'icon': '⚡', 'title': 'Power Mode', 'pattern': 'grid'
            }
        ]
        
        design = random.choice(designs)
        
        # Erstelle Pattern basierend auf Design
        pattern_svg = self._create_pattern_svg(design['pattern'], design['accent'])
        
        svg_content = f'''
        <svg width="1024" height="1024" xmlns="http://www.w3.org/2000/svg">
            <defs>
                {pattern_svg}
                <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{design['accent']};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:{design['text']};stop-opacity:1" />
                </linearGradient>
            </defs>
            
            <!-- Background -->
            <rect width="100%" height="100%" fill="{design['bg']}"/>
            
            <!-- Pattern overlay -->
            <rect width="100%" height="100%" fill="url(#pattern)" opacity="0.1"/>
            
            <!-- Main content area -->
            <rect x="80" y="300" width="864" height="424" fill="white" rx="20" opacity="0.9"/>
            <rect x="80" y="300" width="864" height="424" fill="{design['accent']}" rx="20" opacity="0.05"/>
            
            <!-- Icon -->
            <text x="512" y="400" text-anchor="middle" font-family="Arial, sans-serif" font-size="80">
                {design['icon']}
            </text>
            
            <!-- Title -->
            <text x="512" y="480" text-anchor="middle" font-family="Arial, sans-serif" font-size="48" font-weight="bold" fill="url(#textGrad)">
                {design['title']}
            </text>
            
            <!-- Subtitle -->
            <text x="512" y="530" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="{design['text']}">
                Demo Modus
            </text>
            
            <!-- Description -->
            <text x="512" y="570" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="{design['accent']}">
                OpenAI API-Key für echte Bilder konfigurieren
            </text>
            
            <!-- Footer -->
            <text x="512" y="650" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#6c757d">
                Placeholder • Nicht KI-generiert
            </text>
            
            <!-- Decorative border -->
            <rect x="80" y="300" width="864" height="424" fill="none" stroke="{design['accent']}" stroke-width="2" rx="20" opacity="0.3"/>
        </svg>
        '''
        
        import base64
        svg_b64 = base64.b64encode(svg_content.encode()).decode()
        return f"data:image/svg+xml;base64,{svg_b64}"
    
    def _create_pattern_svg(self, pattern_type: str, color: str) -> str:
        """
        Erstellt SVG-Pattern für Hintergründe
        """
        patterns = {
            'gradient': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="100" height="100">
                    <rect width="100" height="100" fill="url(#grad)"/>
                    <defs>
                        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:{color};stop-opacity:0.1" />
                            <stop offset="100%" style="stop-color:{color};stop-opacity:0.3" />
                        </linearGradient>
                    </defs>
                </pattern>
            ''',
            'circles': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="60" height="60">
                    <circle cx="30" cy="30" r="8" fill="{color}" opacity="0.2"/>
                    <circle cx="0" cy="0" r="4" fill="{color}" opacity="0.1"/>
                    <circle cx="60" cy="60" r="4" fill="{color}" opacity="0.1"/>
                </pattern>
            ''',
            'lines': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="40" height="40">
                    <path d="M0,20 L40,20" stroke="{color}" stroke-width="1" opacity="0.2"/>
                    <path d="M20,0 L20,40" stroke="{color}" stroke-width="1" opacity="0.2"/>
                </pattern>
            ''',
            'dots': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="50" height="50">
                    <circle cx="25" cy="25" r="2" fill="{color}" opacity="0.3"/>
                    <circle cx="0" cy="0" r="1" fill="{color}" opacity="0.2"/>
                    <circle cx="50" cy="50" r="1" fill="{color}" opacity="0.2"/>
                </pattern>
            ''',
            'waves': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="80" height="40">
                    <path d="M0,20 Q20,0 40,20 Q60,40 80,20" stroke="{color}" stroke-width="2" fill="none" opacity="0.2"/>
                </pattern>
            ''',
            'grid': f'''
                <pattern id="pattern" patternUnits="userSpaceOnUse" width="30" height="30">
                    <rect width="30" height="30" fill="none" stroke="{color}" stroke-width="0.5" opacity="0.2"/>
                </pattern>
            '''
        }
        
        return patterns.get(pattern_type, patterns['gradient'])
    
    def _create_svg_fallback(self) -> str:
        """
        Fallback für Legacy-Aufrufe
        """
        return self._create_diverse_svg_fallback()
    
    def _get_next_batch_number(self, campaign: Campaign) -> int:
        """
        Ermittelt die nächste Batch-Nummer für Creatives
        """
        last_batch = campaign.creatives.aggregate(
            max_batch=models.Max('generation_batch')
        )['max_batch']
        
        return (last_batch or 0) + 1
