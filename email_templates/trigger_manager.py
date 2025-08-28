"""
Email Trigger Management System
Centralized management for all email triggers and template sending
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import EmailTrigger, EmailTemplate, ZohoMailServerConnection, EmailSendLog
from .services import EmailTemplateService

User = get_user_model()
logger = logging.getLogger(__name__)


class TriggerRegistry:
    """Registry for managing email triggers"""
    
    def __init__(self):
        self._triggers: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable] = {}
    
    def register_trigger(self, trigger_key: str, name: str, description: str, 
                        category: str = 'custom', variables: Dict[str, str] = None,
                        handler: Callable = None):
        """Register a new email trigger"""
        self._triggers[trigger_key] = {
            'name': name,
            'description': description,
            'category': category,
            'variables': variables or {},
            'registered_at': timezone.now()
        }
        
        if handler:
            self._handlers[trigger_key] = handler
        
        logger.info(f"Registered trigger: {trigger_key}")
    
    def get_trigger(self, trigger_key: str) -> Optional[Dict[str, Any]]:
        """Get trigger information by key"""
        return self._triggers.get(trigger_key)
    
    def get_all_triggers(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered triggers"""
        return self._triggers.copy()
    
    def get_handler(self, trigger_key: str) -> Optional[Callable]:
        """Get handler function for trigger"""
        return self._handlers.get(trigger_key)


class TriggerManager:
    """Main trigger management service"""
    
    def __init__(self):
        self.registry = TriggerRegistry()
        self._setup_default_triggers()
    
    def _setup_default_triggers(self):
        """Register all default system triggers"""
        default_triggers = [
            # Authentication triggers
            {
                'key': 'user_registration',
                'name': 'Benutzer-Registrierung',
                'description': 'Wird ausgelöst wenn sich ein neuer Benutzer registriert',
                'category': 'authentication',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'username': 'Benutzername',
                    'email': 'E-Mail-Adresse',
                    'registration_date': 'Registrierungsdatum',
                    'domain': 'Website-Domain'
                }
            },
            {
                'key': 'account_activation',
                'name': 'Account-Aktivierung',
                'description': 'E-Mail-Bestätigung für neue Benutzer',
                'category': 'authentication',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'username': 'Benutzername',
                    'verification_url': 'Bestätigungslink',
                    'domain': 'Website-Domain',
                    'site_name': 'Website-Name'
                }
            },
            {
                'key': 'password_reset',
                'name': 'Passwort zurücksetzen',
                'description': 'Passwort-Reset-Link für Benutzer',
                'category': 'authentication',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'reset_url': 'Passwort-Reset-Link',
                    'domain': 'Website-Domain',
                    'expiry_hours': 'Gültigkeitsdauer in Stunden'
                }
            },
            {
                'key': 'welcome_email',
                'name': 'Willkommens-E-Mail',
                'description': 'Begrüßung für neue verifizierte Benutzer',
                'category': 'authentication',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'dashboard_url': 'Dashboard-Link',
                    'features': 'Verfügbare Features',
                    'domain': 'Website-Domain'
                }
            },
            
            # Storage Management triggers
            {
                'key': 'storage_grace_period_start',
                'name': 'Speicher-Kulanzzeit gestartet',
                'description': 'Speicher überschritten, Kulanzzeit beginnt',
                'category': 'storage',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'used_storage': 'Verwendeter Speicher',
                    'max_storage': 'Maximaler Speicher',
                    'grace_period_days': 'Kulanzzeit in Tagen',
                    'overage_amount': 'Überschreitung'
                }
            },
            {
                'key': 'storage_grace_period_warning',
                'name': 'Speicher-Kulanzzeit Warnung',
                'description': 'Warnung vor Ende der Kulanzzeit',
                'category': 'storage',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'days_remaining': 'Verbleibende Tage',
                    'upgrade_url': 'Upgrade-Link',
                    'used_storage': 'Verwendeter Speicher'
                }
            },
            {
                'key': 'storage_grace_period_end',
                'name': 'Speicher-Kulanzzeit beendet',
                'description': 'Kulanzzeit beendet, Restriktionen starten',
                'category': 'storage',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'restriction_level': 'Restriktionsstufe',
                    'upgrade_url': 'Upgrade-Link',
                    'used_storage': 'Verwendeter Speicher'
                }
            },
            {
                'key': 'videos_archived',
                'name': 'Videos archiviert',
                'description': 'Videos wurden wegen Speichermangel archiviert',
                'category': 'storage',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'archived_count': 'Anzahl archivierter Videos',
                    'archived_size': 'Archivierte Datenmenge',
                    'restore_url': 'Wiederherstellungs-Link'
                }
            },
            
            # Payment triggers
            {
                'key': 'subscription_created',
                'name': 'Abonnement erstellt',
                'description': 'Neues Abonnement wurde erstellt',
                'category': 'payments',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'plan_name': 'Abonnement-Name',
                    'price': 'Preis',
                    'billing_cycle': 'Abrechnungszyklus',
                    'features': 'Enthaltene Features'
                }
            },
            {
                'key': 'subscription_cancelled',
                'name': 'Abonnement gekündigt',
                'description': 'Abonnement wurde gekündigt',
                'category': 'payments',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'plan_name': 'Abonnement-Name',
                    'end_date': 'Enddatum',
                    'refund_info': 'Erstattungsinformationen'
                }
            },
            {
                'key': 'payment_failed',
                'name': 'Zahlung fehlgeschlagen',
                'description': 'Zahlung konnte nicht verarbeitet werden',
                'category': 'payments',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'amount': 'Betrag',
                    'reason': 'Fehlergrund',
                    'retry_url': 'Wiederholen-Link',
                    'update_payment_url': 'Zahlungsmethode aktualisieren'
                }
            },
            
            # E-Commerce triggers
            {
                'key': 'order_confirmation',
                'name': 'Bestellbestätigung',
                'description': 'Bestätigung einer neuen Bestellung',
                'category': 'ecommerce',
                'variables': {
                    'customer_name': 'Kundenname',
                    'order_number': 'Bestellnummer',
                    'order_items': 'Bestellpositionen',
                    'total_amount': 'Gesamtbetrag',
                    'shipping_address': 'Lieferadresse'
                }
            },
            {
                'key': 'order_shipped',
                'name': 'Versandbestätigung',
                'description': 'Bestellung wurde versendet',
                'category': 'ecommerce',
                'variables': {
                    'customer_name': 'Kundenname',
                    'order_number': 'Bestellnummer',
                    'tracking_number': 'Sendungsverfolgung',
                    'carrier': 'Versanddienstleister',
                    'estimated_delivery': 'Voraussichtliche Lieferung'
                }
            },
            
            # System triggers
            {
                'key': 'bug_report_submitted',
                'name': 'Bug-Report eingereicht',
                'description': 'Neuer Bug-Report wurde eingereicht',
                'category': 'system',
                'variables': {
                    'reporter_name': 'Name des Meldenden',
                    'bug_title': 'Bug-Titel',
                    'bug_description': 'Bug-Beschreibung',
                    'priority': 'Priorität',
                    'submission_date': 'Einreichungsdatum'
                }
            },
            {
                'key': 'maintenance_notification',
                'name': 'Wartungsankündigung',
                'description': 'Ankündigung von Wartungsarbeiten',
                'category': 'system',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'maintenance_start': 'Wartungsbeginn',
                    'maintenance_end': 'Wartungsende',
                    'affected_services': 'Betroffene Services',
                    'impact_description': 'Auswirkungen'
                }
            },
            
            # Organization triggers
            {
                'key': 'event_reminder',
                'name': 'Terminerinnerung',
                'description': 'Erinnerung an anstehende Termine',
                'category': 'organization',
                'variables': {
                    'user_name': 'Name des Benutzers',
                    'event_title': 'Termin-Titel',
                    'event_date': 'Termin-Datum',
                    'event_time': 'Termin-Zeit',
                    'event_location': 'Termin-Ort',
                    'event_description': 'Termin-Beschreibung'
                }
            },
            {
                'key': 'task_assigned',
                'name': 'Aufgabe zugewiesen',
                'description': 'Neue Aufgabe wurde zugewiesen',
                'category': 'organization',
                'variables': {
                    'assignee_name': 'Name des Beauftragten',
                    'task_title': 'Aufgaben-Titel',
                    'task_description': 'Aufgaben-Beschreibung',
                    'due_date': 'Fälligkeitsdatum',
                    'priority': 'Priorität',
                    'assigner_name': 'Name des Zuweisenden'
                }
            }
        ]
        
        for trigger_data in default_triggers:
            self.registry.register_trigger(
                trigger_key=trigger_data['key'],
                name=trigger_data['name'],
                description=trigger_data['description'],
                category=trigger_data['category'],
                variables=trigger_data['variables']
            )
    
    def sync_triggers_to_database(self):
        """Sync registered triggers to database"""
        synced_count = 0
        
        for trigger_key, trigger_data in self.registry.get_all_triggers().items():
            trigger, created = EmailTrigger.objects.get_or_create(
                trigger_key=trigger_key,
                defaults={
                    'name': trigger_data['name'],
                    'description': trigger_data['description'],
                    'category': trigger_data['category'],
                    'available_variables': trigger_data['variables'],
                    'is_system_trigger': True
                }
            )
            
            if not created:
                # Update existing trigger
                trigger.name = trigger_data['name']
                trigger.description = trigger_data['description']
                trigger.category = trigger_data['category']
                trigger.available_variables = trigger_data['variables']
                trigger.save()
            
            synced_count += 1
            
        logger.info(f"Synced {synced_count} triggers to database")
        return synced_count
    
    def fire_trigger(self, trigger_key: str, context_data: Dict[str, Any], 
                    recipient_email: str, recipient_name: str = None,
                    sent_by: User = None, delay_minutes: int = 0) -> List[Dict[str, Any]]:
        """
        Fire a trigger and send associated email templates
        
        Args:
            trigger_key: The trigger to fire
            context_data: Template variables
            recipient_email: Email recipient
            recipient_name: Recipient name (optional)
            sent_by: User who triggered the email (optional)
            delay_minutes: Additional delay in minutes (optional)
        
        Returns:
            List of send results
        """
        try:
            # Get trigger from database
            trigger = EmailTrigger.objects.filter(
                trigger_key=trigger_key,
                is_active=True
            ).first()
            
            if not trigger:
                logger.warning(f"Trigger '{trigger_key}' not found or inactive")
                return []
            
            # Get active templates for this trigger
            templates = EmailTemplate.objects.filter(
                trigger=trigger,
                is_active=True,
                is_auto_send=True
            )
            
            if not templates.exists():
                logger.info(f"No active templates found for trigger '{trigger_key}'")
                return []
            
            # WICHTIG: Email-Templates verwendet jetzt SuperConfig!
            # Check SuperConfig email status instead of Zoho connections
            from superconfig.models import EmailConfiguration
            superconfig_active = EmailConfiguration.objects.filter(is_active=True).exists()
            
            if not superconfig_active:
                logger.error("No active SuperConfig email configuration found")
                return []
            
            results = []
            
            for template in templates:
                try:
                    # Calculate delay
                    total_delay = delay_minutes + (template.send_delay_minutes or 0)
                    
                    # Check conditions (if any)
                    if template.conditions and not self._check_conditions(template.conditions, context_data):
                        logger.info(f"Template '{template.name}' conditions not met, skipping")
                        continue
                    
                    # TODO: Implement delay mechanism for future enhancement
                    # For now, send immediately
                    
                    # WICHTIG: Verwende SuperConfig anstatt Zoho connection
                    result = EmailTemplateService.send_template_email(
                        template=template,
                        connection=None,  # SuperConfig verwendet keine Connection
                        recipient_email=recipient_email,
                        recipient_name=recipient_name,
                        context_data=context_data,
                        sent_by=sent_by
                    )
                    
                    results.append({
                        'template': template.name,
                        'trigger': trigger_key,
                        'success': result['success'],
                        'message': result.get('message', ''),
                        'send_log_id': result.get('send_log_id')
                    })
                    
                    if result['success']:
                        logger.info(f"Template '{template.name}' sent successfully for trigger '{trigger_key}'")
                    else:
                        logger.error(f"Template '{template.name}' failed for trigger '{trigger_key}': {result.get('message')}")
                
                except Exception as template_error:
                    error_msg = f"Error sending template '{template.name}': {str(template_error)}"
                    logger.error(error_msg)
                    results.append({
                        'template': template.name,
                        'trigger': trigger_key,
                        'success': False,
                        'message': error_msg
                    })
            
            return results
            
        except Exception as e:
            error_msg = f"Error firing trigger '{trigger_key}': {str(e)}"
            logger.error(error_msg)
            return [{
                'trigger': trigger_key,
                'success': False,
                'message': error_msg
            }]
    
    def _check_conditions(self, conditions: Dict[str, Any], context_data: Dict[str, Any]) -> bool:
        """
        Check if template conditions are met
        
        This is a basic implementation that can be extended for complex conditions
        """
        try:
            # Example condition checking logic
            for condition_key, condition_value in conditions.items():
                if condition_key in context_data:
                    if isinstance(condition_value, dict):
                        # Handle complex conditions like {'min': 100, 'max': 1000}
                        if 'equals' in condition_value:
                            if context_data[condition_key] != condition_value['equals']:
                                return False
                        if 'min' in condition_value:
                            if context_data[condition_key] < condition_value['min']:
                                return False
                        if 'max' in condition_value:
                            if context_data[condition_key] > condition_value['max']:
                                return False
                        if 'contains' in condition_value:
                            if condition_value['contains'] not in str(context_data[condition_key]):
                                return False
                    else:
                        # Simple equality check
                        if context_data[condition_key] != condition_value:
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking conditions: {str(e)}")
            return False
    
    def get_trigger_templates(self, trigger_key: str) -> List[EmailTemplate]:
        """Get all templates associated with a trigger"""
        try:
            trigger = EmailTrigger.objects.get(trigger_key=trigger_key)
            return list(trigger.templates.filter(is_active=True))
        except EmailTrigger.DoesNotExist:
            return []
    
    def validate_template_variables(self, template: EmailTemplate, context_data: Dict[str, Any]) -> List[str]:
        """Validate that all required template variables are present"""
        if not template.trigger:
            return []
        
        available_vars = template.trigger.available_variables.keys()
        missing_vars = []
        
        for var in available_vars:
            if var not in context_data:
                missing_vars.append(var)
        
        return missing_vars


# Global trigger manager instance
trigger_manager = TriggerManager()


def email_trigger(trigger_key: str, name: str = None, description: str = None, 
                 category: str = 'custom', variables: Dict[str, str] = None):
    """
    Decorator for registering email triggers with handlers
    
    Usage:
    @email_trigger('my_trigger', name='My Trigger', variables={'user': 'User name'})
    def handle_my_trigger(user, **kwargs):
        trigger_manager.fire_trigger('my_trigger', {'user': user.name}, user.email)
    """
    def decorator(func: Callable):
        trigger_manager.registry.register_trigger(
            trigger_key=trigger_key,
            name=name or trigger_key.replace('_', ' ').title(),
            description=description or f"Handler for {trigger_key}",
            category=category,
            variables=variables or {},
            handler=func
        )
        return func
    return decorator