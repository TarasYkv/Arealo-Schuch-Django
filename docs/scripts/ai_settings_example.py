# KI-API Konfiguration für Naturmacher Schulungserstellung
# 
# Fügen Sie diese Einstellungen zu Ihrer Django settings.py hinzu
# Mindestens eine API muss konfiguriert werden

# Option 1: Claude API (Anthropic) - Empfohlen
# Registrierung: https://console.anthropic.com/
# ANTHROPIC_API_KEY = 'your-anthropic-api-key-here'

# Option 2: OpenAI API 
# Registrierung: https://platform.openai.com/
# OPENAI_API_KEY = 'your-openai-api-key-here'

# Option 3: Google Gemini API
# Registrierung: https://ai.google.dev/
# GOOGLE_AI_API_KEY = 'your-google-ai-api-key-here'

# Beispiel-Konfiguration:
"""
# In Ihrer settings.py Datei:

# Claude API (beste Qualität für lange Texte)
ANTHROPIC_API_KEY = 'sk-ant-api03-...'

# Oder OpenAI API 
OPENAI_API_KEY = 'sk-...'

# Oder Google Gemini API (kostenlos mit Limits)
GOOGLE_AI_API_KEY = 'AIza...'
"""

# Das System versucht die APIs in folgender Reihenfolge:
# 1. Claude (Anthropic) - beste Qualität für Bildungsinhalte
# 2. OpenAI GPT-4 - sehr gute Qualität
# 3. Google Gemini - kostenlose Option mit Limits
# 4. Fallback: Demo-HTML wird generiert

# Sicherheitshinweis:
# - API-Keys NIEMALS in den Code committen
# - Verwenden Sie Umgebungsvariablen oder separate Konfigurationsdateien
# - Beispiel mit Umgebungsvariablen:
#   ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')FIELD_ENCRYPTION_KEY = '79aa1b704e2b5114658443300270c4d5'
