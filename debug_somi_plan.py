#!/usr/bin/env python3
"""
Comprehensive SoMi-Plan JavaScript Debugging Tool
"""

import os
import sys
import requests
from pathlib import Path

def check_server_status():
    """Check if Django server is running"""
    try:
        response = requests.get('http://127.0.0.1:8000/somi-plan/plan/4/', timeout=5)
        print(f"✅ Server status: {response.status_code}")
        return response.status_code == 200, response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ Server not accessible: {e}")
        return False, None

def analyze_html_output(html_content):
    """Analyze the actual HTML output"""
    if not html_content:
        return False
    
    print("\n🔍 HTML Content Analysis:")
    print("-" * 40)
    
    # Check for JavaScript includes
    js_includes = [
        'ux-improvements.js',
        'advanced-features.js',
        'showPostModal',
        'window.showPostModal',
        'onclick="showPostModal',
        'Bootstrap',
        'jquery'
    ]
    
    for item in js_includes:
        if item in html_content:
            print(f"✅ Found: {item}")
        else:
            print(f"❌ Missing: {item}")
    
    # Check for specific script blocks
    if 'id="posts-data"' in html_content:
        print("✅ Posts data JSON block found")
    else:
        print("❌ Posts data JSON block missing")
    
    if 'id="urls-data"' in html_content:
        print("✅ URLs data JSON block found") 
    else:
        print("❌ URLs data JSON block missing")
    
    # Count script tags
    script_count = html_content.count('<script')
    print(f"📊 Total script tags: {script_count}")
    
    # Check for syntax errors in script content
    if 'SyntaxError' in html_content:
        print("❌ SyntaxError found in HTML")
    else:
        print("✅ No SyntaxError in HTML")
    
    return True

def check_template_files():
    """Check template file structure"""
    print("\n📁 Template File Analysis:")
    print("-" * 40)
    
    files_to_check = [
        'somi_plan/templates/somi_plan/base.html',
        'somi_plan/templates/somi_plan/plan_detail.html',
        'somi_plan/static/somi_plan/js/ux-improvements.js',
        'somi_plan/static/somi_plan/js/advanced-features.js'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"✅ {file_path} ({size:,} bytes)")
        else:
            print(f"❌ {file_path} (missing)")
    
    # Check base template structure
    try:
        with open('somi_plan/templates/somi_plan/base.html', 'r') as f:
            base_content = f.read()
        
        checks = {
            'page_js block': '{% block page_js %}' in base_content,
            'child_js block': '{% block child_js %}' in base_content,
            'ux-improvements.js': 'ux-improvements.js' in base_content,
            'advanced-features.js': 'advanced-features.js' in base_content,
            'block.super removed': '{{ block.super }}' not in base_content
        }
        
        print(f"\n🏗️ Base Template Structure:")
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}")
            
    except Exception as e:
        print(f"❌ Error checking base template: {e}")

def create_test_html():
    """Create a simple test HTML to verify JavaScript loading"""
    test_html = """
<!DOCTYPE html>
<html>
<head>
    <title>JavaScript Test</title>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body>
    <h1>JavaScript Test</h1>
    <button onclick="testFunction()">Test Button</button>
    <div id="result"></div>
    
    <script>
    function testFunction() {
        document.getElementById('result').innerHTML = '✅ JavaScript is working!';
        console.log('✅ JavaScript executed successfully');
    }
    
    // Check if we can access showPostModal
    if (typeof window.showPostModal !== 'undefined') {
        console.log('✅ showPostModal is defined');
        document.getElementById('result').innerHTML += '<br>✅ showPostModal found';
    } else {
        console.log('❌ showPostModal is NOT defined');
        document.getElementById('result').innerHTML += '<br>❌ showPostModal missing';
    }
    </script>
</body>
</html>
    """
    
    with open('static/js_test.html', 'w') as f:
        f.write(test_html)
    
    print("\n🧪 Test HTML created at: static/js_test.html")
    print("   Access via: http://127.0.0.1:8000/static/js_test.html")

def check_django_settings():
    """Check Django settings that might affect JavaScript"""
    print("\n⚙️ Django Settings Check:")
    print("-" * 40)
    
    try:
        # Import Django settings
        sys.path.insert(0, os.getcwd())
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Schuch.settings')
        
        import django
        django.setup()
        
        from django.conf import settings
        
        # Check static files settings
        print(f"✅ STATIC_URL: {getattr(settings, 'STATIC_URL', 'Not set')}")
        print(f"✅ STATIC_ROOT: {getattr(settings, 'STATIC_ROOT', 'Not set')}")
        print(f"✅ STATICFILES_DIRS: {getattr(settings, 'STATICFILES_DIRS', 'Not set')}")
        
        # Check if debug is enabled
        debug = getattr(settings, 'DEBUG', False)
        print(f"✅ DEBUG: {debug}")
        
        if debug:
            print("   ℹ️  Debug mode - static files served by Django")
        else:
            print("   ⚠️  Production mode - check static file serving")
            
    except Exception as e:
        print(f"❌ Error checking Django settings: {e}")

def generate_fix_suggestions():
    """Generate specific fix suggestions based on findings"""
    print("\n💡 Fix Suggestions:")
    print("-" * 40)
    
    suggestions = [
        "1. Clear browser cache (Ctrl+F5 or Ctrl+Shift+R)",
        "2. Check browser console for specific error messages",
        "3. Verify Django server is serving static files correctly",
        "4. Test JavaScript loading with simple test page",
        "5. Check template inheritance chain",
        "6. Verify Django template rendering is working",
        "7. Test with different browser",
        "8. Check for conflicting JavaScript libraries"
    ]
    
    for suggestion in suggestions:
        print(f"   {suggestion}")

def main():
    print("🔍 Comprehensive SoMi-Plan JavaScript Debug")
    print("=" * 60)
    
    # Check server status and get HTML
    server_ok, html_content = check_server_status()
    
    if server_ok and html_content:
        analyze_html_output(html_content)
    
    # Check template files
    check_template_files()
    
    # Check Django settings
    check_django_settings()
    
    # Create test HTML
    create_test_html()
    
    # Generate suggestions
    generate_fix_suggestions()
    
    print("\n" + "=" * 60)
    print("🎯 Next Steps:")
    print("1. Check the browser console at: http://127.0.0.1:8000/somi-plan/plan/4/")
    print("2. Test basic JavaScript at: http://127.0.0.1:8000/static/js_test.html") 
    print("3. Look for specific error messages")
    print("4. Clear browser cache completely")

if __name__ == '__main__':
    main()