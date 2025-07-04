"""
API Pricing und Kostenberechnung für verschiedene KI-Provider
"""

from decimal import Decimal

# Aktuelle Preise pro 1M Tokens (Stand: 2025)
API_PRICING = {
    'openai': {
        'gpt-4.1': {'input': Decimal('5.00'), 'output': Decimal('15.00')},
        'gpt-4.1-mini': {'input': Decimal('0.15'), 'output': Decimal('0.60')},
        'gpt-4.1-nano': {'input': Decimal('0.05'), 'output': Decimal('0.20')},
        'gpt-4o': {'input': Decimal('2.50'), 'output': Decimal('10.00')},
        'gpt-4o-mini': {'input': Decimal('0.15'), 'output': Decimal('0.60')},
        'gpt-4-turbo': {'input': Decimal('10.00'), 'output': Decimal('30.00')},
        'gpt-4': {'input': Decimal('30.00'), 'output': Decimal('60.00')},
        'gpt-3.5-turbo': {'input': Decimal('0.50'), 'output': Decimal('1.50')},
        'o3': {'input': Decimal('60.00'), 'output': Decimal('240.00')},  # Reasoning-Modelle sind teurer
        'o4-mini': {'input': Decimal('10.00'), 'output': Decimal('40.00')},
    },
    'anthropic': {
        'claude-opus-4': {'input': Decimal('15.00'), 'output': Decimal('75.00')},
        'claude-sonnet-4': {'input': Decimal('3.00'), 'output': Decimal('15.00')},
        'claude-sonnet-3.7': {'input': Decimal('3.00'), 'output': Decimal('15.00')},
        'claude-sonnet-3.5-new': {'input': Decimal('3.00'), 'output': Decimal('15.00')},
        'claude-sonnet-3.5': {'input': Decimal('3.00'), 'output': Decimal('15.00')},
        'claude-haiku-3.5-new': {'input': Decimal('1.00'), 'output': Decimal('5.00')},
        'claude-haiku-3.5': {'input': Decimal('1.00'), 'output': Decimal('5.00')},
    },
    'google': {
        'gemini-2.5-pro': {'input': Decimal('1.25'), 'output': Decimal('10.00')},  # Premium-Preise
        'gemini-2.5-flash': {'input': Decimal('0.075'), 'output': Decimal('0.30')},  # Beste Preis-Leistung
        'gemini-2.0-flash': {'input': Decimal('0.075'), 'output': Decimal('0.30')},
        'gemini-2.0-pro': {'input': Decimal('1.25'), 'output': Decimal('5.00')},
        'gemini-1.5-flash': {'input': Decimal('0.075'), 'output': Decimal('0.30')},
        'gemini-1.5-pro': {'input': Decimal('1.25'), 'output': Decimal('5.00')},
        'gemini': {'input': Decimal('0.00'), 'output': Decimal('0.00')},  # Kostenlos
    }
}

def get_provider_from_model(model_name):
    """Ermittelt den Provider basierend auf dem Modellnamen"""
    if model_name.startswith(('gpt-', 'o')):
        return 'openai'
    elif model_name.startswith('claude-'):
        return 'anthropic'
    elif model_name.startswith('gemini') or model_name == 'gemini':
        return 'google'
    return None

def calculate_cost(model_name, prompt_tokens, completion_tokens):
    """Berechnet die geschätzten Kosten für eine API-Anfrage"""
    provider = get_provider_from_model(model_name)
    
    if not provider or provider not in API_PRICING:
        return Decimal('0.00')
    
    model_pricing = API_PRICING[provider].get(model_name)
    if not model_pricing:
        # Fallback zu einem Standard-Preis des Providers
        if provider == 'openai':
            model_pricing = API_PRICING[provider]['gpt-4o-mini']
        elif provider == 'anthropic':
            model_pricing = API_PRICING[provider]['claude-haiku-3.5']
        elif provider == 'google':
            model_pricing = API_PRICING[provider]['gemini-1.5-flash']
        else:
            return Decimal('0.00')
    
    # Kosten berechnen (Preise sind pro 1M Tokens)
    input_cost = (Decimal(prompt_tokens) / Decimal('1000000')) * model_pricing['input']
    output_cost = (Decimal(completion_tokens) / Decimal('1000000')) * model_pricing['output']
    
    total_cost = input_cost + output_cost
    return total_cost.quantize(Decimal('0.0001'))  # 4 Dezimalstellen

def estimate_tokens(text):
    """Grobe Schätzung der Token-Anzahl basierend auf Textlänge"""
    # Grobe Regel: ~4 Zeichen = 1 Token für die meisten Modelle
    return max(1, len(text) // 4)

def get_model_info(model_name):
    """Gibt Informationen über ein Modell zurück"""
    provider = get_provider_from_model(model_name)
    
    if not provider or provider not in API_PRICING:
        return None
    
    pricing = API_PRICING[provider].get(model_name)
    if not pricing:
        return None
    
    return {
        'provider': provider,
        'input_price': pricing['input'],
        'output_price': pricing['output'],
        'currency': 'USD'
    }

def get_cheapest_models():
    """Gibt die günstigsten Modelle pro Provider zurück"""
    cheapest = {}
    
    for provider, models in API_PRICING.items():
        cheapest_model = None
        cheapest_cost = None
        
        for model_name, pricing in models.items():
            # Durchschnittliche Kosten (Input + Output) / 2
            avg_cost = (pricing['input'] + pricing['output']) / 2
            
            if cheapest_cost is None or avg_cost < cheapest_cost:
                cheapest_cost = avg_cost
                cheapest_model = model_name
        
        if cheapest_model:
            cheapest[provider] = {
                'model': cheapest_model,
                'avg_cost': cheapest_cost
            }
    
    return cheapest

def get_most_expensive_models():
    """Gibt die teuersten Modelle pro Provider zurück"""
    most_expensive = {}
    
    for provider, models in API_PRICING.items():
        expensive_model = None
        expensive_cost = None
        
        for model_name, pricing in models.items():
            # Durchschnittliche Kosten (Input + Output) / 2
            avg_cost = (pricing['input'] + pricing['output']) / 2
            
            if expensive_cost is None or avg_cost > expensive_cost:
                expensive_cost = avg_cost
                expensive_model = model_name
        
        if expensive_model:
            most_expensive[provider] = {
                'model': expensive_model,
                'avg_cost': expensive_cost
            }
    
    return most_expensive