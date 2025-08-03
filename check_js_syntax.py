#!/usr/bin/env python3
"""
Check JavaScript syntax in plan_detail.html template
"""

import re

def check_template_js():
    print('🔍 Checking JavaScript syntax in plan_detail.html...')
    
    try:
        # Read the template file
        with open('somi_plan/templates/somi_plan/plan_detail.html', 'r') as f:
            content = f.read()

        # Extract JavaScript from child_js block
        js_start = content.find('{% block child_js %}')
        js_end = content.find('{% endblock %}', js_start)

        if js_start != -1 and js_end != -1:
            js_block = content[js_start:js_end]
            
            # Find all JavaScript content (multiple script tags)
            import re
            script_matches = re.findall(r'<script[^>]*>(.*?)</script>', js_block, re.DOTALL)
            
            # Combine all JavaScript code except JSON data
            js_code = ""
            for match in script_matches:
                # Skip JSON data scripts
                if not match.strip().startswith('[') and not match.strip().startswith('{'):
                    js_code += match + "\n"
                
            print(f'✅ JavaScript block found: {len(js_code)} characters')
                
            # Look for template variables that might cause issues
            template_vars = re.findall(r'\{\{.*?\}\}', js_code)
            if template_vars:
                print(f'⚠️  Found {len(template_vars)} Django template variables in JavaScript:')
                for var in template_vars[:5]:  # Show first 5
                    print(f'   - {var}')
            
            # Look for key functions
            functions = ['showPostModal', 'editPost', 'schedulePost', 'generateMorePosts']
            print(f'\n🔧 Checking for key functions:')
            for func in functions:
                pattern = f'window.{func} = function'
                if pattern in js_code:
                    print(f'   ✅ {func}: Found')
                else:
                    print(f'   ❌ {func}: Missing')
            
            # Check for potential syntax issues
            lines = js_code.split('\n')
            syntax_issues = 0
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if line_stripped:
                    # Check for common issues
                    if '{% ' in line and ' %}' in line:
                        print(f'❌ Line {i}: Django template tag in JavaScript')
                        syntax_issues += 1
                    elif line_stripped.count('"') % 2 != 0 and not line_stripped.startswith('//'):
                        print(f'⚠️  Line {i}: Unmatched quotes: {line_stripped[:50]}...')
                        syntax_issues += 1
                    elif line_stripped.count("'") % 2 != 0 and not line_stripped.startswith('//'):
                        print(f'⚠️  Line {i}: Unmatched single quotes: {line_stripped[:50]}...')
                        syntax_issues += 1
            
            if syntax_issues == 0:
                print(f'✅ No obvious syntax issues found')
            else:
                print(f'❌ Found {syntax_issues} potential syntax issues')
            
            return syntax_issues == 0
        else:
            print('❌ No child_js block found in template')
            return False
        else:
            print('❌ No child_js block found in template')
            return False
            
    except Exception as e:
        print(f'❌ Error checking template: {e}')
        return False

if __name__ == '__main__':
    check_template_js()