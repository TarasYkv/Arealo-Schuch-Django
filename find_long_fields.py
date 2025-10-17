#!/usr/bin/env python
"""
Script to find all CharField values that exceed their max_length in the fixture
"""
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from django.apps import apps

# Load fixture
with open('data_backup.json', 'r') as f:
    data = json.load(f)

print("Analyzing fixture for fields that exceed max_length...")
print("=" * 80)

problems = []

for item in data:
    model_name = item.get('model')
    if not model_name:
        continue

    try:
        app_label, model_class = model_name.split('.')
        model = apps.get_model(app_label, model_class)
    except:
        continue

    pk = item.get('pk')
    fields_data = item.get('fields', {})

    for field_name, value in fields_data.items():
        try:
            field = model._meta.get_field(field_name)

            # Check CharField max_length
            if hasattr(field, 'max_length') and field.max_length and isinstance(value, str):
                if len(value) > field.max_length:
                    problems.append({
                        'model': model_name,
                        'pk': pk,
                        'field': field_name,
                        'max_length': field.max_length,
                        'actual_length': len(value),
                        'value_preview': value[:100]
                    })
        except:
            pass

if problems:
    print(f"\n❌ Found {len(problems)} fields exceeding max_length:\n")
    for prob in problems:
        print(f"Model: {prob['model']} (pk={prob['pk']})")
        print(f"  Field: {prob['field']}")
        print(f"  Max length: {prob['max_length']}, Actual: {prob['actual_length']}")
        print(f"  Preview: {prob['value_preview']}")
        print()
else:
    print("\n✅ No problems found!")
