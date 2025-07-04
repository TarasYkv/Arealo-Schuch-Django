#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
django.setup()

from naturmacher.models import Thema, Training

print(f'Themen: {Thema.objects.count()}')
print(f'Trainings: {Training.objects.count()}')

for thema in Thema.objects.all():
    print(f'{thema.name}: {thema.trainings.count()} Trainings')