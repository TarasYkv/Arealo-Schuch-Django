#!/usr/bin/env python
"""
ASGI server startup script for WebSocket support
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')

# Setup Django
django.setup()

if __name__ == '__main__':
    from daphne.cli import CommandLineInterface
    
    # Run Daphne with the ASGI application
    cli = CommandLineInterface()
    cli.run([
        '-b', '127.0.0.1',
        '-p', '8001',  # Different port for ASGI
        'Schuch.asgi:application'
    ])