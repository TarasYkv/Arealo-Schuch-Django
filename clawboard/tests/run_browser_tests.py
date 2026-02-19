#!/usr/bin/env python3
"""
Browser Test Runner für Clawboard
Führt Tests im sichtbaren Browser aus zur manuellen Überprüfung

Verwendung:
    python run_browser_tests.py              # Alle Tests (headed)
    python run_browser_tests.py --headless   # Alle Tests (headless für CI)
    python run_browser_tests.py -k dashboard # Nur Dashboard Tests
    python run_browser_tests.py --live       # Gegen Live-Server testen
"""
import os
import sys
import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description='Clawboard Browser Tests')
    parser.add_argument('--headless', action='store_true', 
                        help='Tests headless ausführen (für CI/CD)')
    parser.add_argument('--live', action='store_true',
                        help='Gegen Live-Server (workloom.de) testen')
    parser.add_argument('-k', '--filter', type=str, default='',
                        help='Test-Filter (z.B. "dashboard" oder "connection")')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose Output')
    parser.add_argument('--slowmo', type=int, default=500,
                        help='Slow-Motion in ms (Standard: 500)')
    
    args = parser.parse_args()
    
    # Zum Workloom-Projekt wechseln
    workloom_dir = os.path.expanduser('~/clawd/projects/workloom')
    os.chdir(workloom_dir)
    
    # Pytest Kommando aufbauen
    cmd = [
        'python', '-m', 'pytest',
        'clawboard/tests/',
        '--tb=short',
    ]
    
    if args.verbose:
        cmd.append('-v')
    
    if args.filter:
        cmd.extend(['-k', args.filter])
    
    # Headed/Headless Mode via Umgebungsvariable
    env = os.environ.copy()
    if args.headless:
        env['PLAYWRIGHT_HEADLESS'] = '1'
    else:
        env['PLAYWRIGHT_HEADLESS'] = '0'
        env['PLAYWRIGHT_SLOWMO'] = str(args.slowmo)
    
    if args.live:
        env['TEST_LIVE_SERVER'] = 'https://www.workloom.de'
    
    # Tests ausführen
    print(f"🧪 Starte Clawboard Browser Tests...")
    print(f"   Mode: {'Headless' if args.headless else 'Headed (sichtbar)'}")
    print(f"   Filter: {args.filter or 'alle Tests'}")
    print()
    
    result = subprocess.run(cmd, env=env)
    
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
