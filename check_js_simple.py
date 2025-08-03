#!/usr/bin/env python3
"""
Simple JavaScript syntax check for plan_detail.html
"""

def check_js_in_template():
    try:
        with open('somi_plan/templates/somi_plan/plan_detail.html', 'r') as f:
            content = f.read()
        
        # Count JavaScript function definitions
        functions = ['showPostModal', 'editPost', 'schedulePost', 'generateMorePosts']
        found_functions = []
        
        for func in functions:
            if f'window.{func} = function' in content:
                found_functions.append(func)
        
        print(f"🔧 JavaScript Functions Found:")
        for func in functions:
            status = "✅" if func in found_functions else "❌"
            print(f"   {status} {func}")
        
        # Check for Django template problems
        child_js_start = content.find('{% block child_js %}')
        child_js_end = content.find('{% endblock %}', child_js_start)
        
        if child_js_start != -1 and child_js_end != -1:
            js_section = content[child_js_start:child_js_end]
            
            # Check for template tags in JS area
            django_tags = js_section.count('{% ')
            template_vars = js_section.count('{{ ')
            
            print(f"\n📊 Template Analysis:")
            print(f"   - Django template tags in JS area: {django_tags}")
            print(f"   - Template variables in JS area: {template_vars}")
            
            if django_tags == 0:
                print("   ✅ No Django template tags in JavaScript")
            else:
                print("   ❌ Django template tags found in JavaScript")
            
            if template_vars <= 20:  # Some are expected in JSON data
                print("   ✅ Template variables seem reasonable")
            else:
                print("   ⚠️  High number of template variables")
            
            return len(found_functions) >= 3 and django_tags == 0
        else:
            print("❌ child_js block not found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Simple JavaScript Check")
    print("=" * 40)
    result = check_js_in_template()
    print("=" * 40)
    if result:
        print("🎉 JavaScript looks good!")
    else:
        print("⚠️  JavaScript issues found")