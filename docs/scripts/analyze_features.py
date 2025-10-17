import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.apps import apps

# Get all models from all apps
print("=== DJANGO APPS AND THEIR MODELS ===")
print()

for app_config in apps.get_app_configs():
    # Skip Django's built-in apps
    if app_config.name.startswith('django.'):
        continue
    
    print(f"App: {app_config.name}")
    print(f"Verbose Name: {app_config.verbose_name}")
    
    # Get all models for this app
    models = app_config.get_models()
    if models:
        print("Models:")
        for model in models:
            print(f"  - {model.__name__}")
            # Show fields
            fields = [f.name for f in model._meta.get_fields()]
            if fields:
                print(f"    Fields: {', '.join(fields[:10])}{'...' if len(fields) > 10 else ''}")
    else:
        print("  No models")
    print()