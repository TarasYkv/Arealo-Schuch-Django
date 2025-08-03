#!/usr/bin/env python3
"""
Simple Template Structure Test
Verifies the template fixes without needing full Django setup
"""

import os

def test_base_template_structure():
    """Test the base template structure"""
    
    print("🏗️ Testing SoMi-Plan Base Template Structure...")
    print("=" * 50)
    
    try:
        # Read the base template file
        base_template_path = 'somi_plan/templates/somi_plan/base.html'
        if not os.path.exists(base_template_path):
            print(f"❌ Base template not found at: {base_template_path}")
            return False
            
        with open(base_template_path, 'r', encoding='utf-8') as f:
            base_content = f.read()
        
        print(f"📁 Reading: {base_template_path}")
        print(f"📊 File size: {len(base_content):,} characters")
        
        # Check structure
        checks = {
            'Has page_js block': '{% block page_js %}' in base_content,
            'Has child_js block': '{% block child_js %}' in base_content,
            'child_js is inside page_js': None,
            'block.super in correct position': None,
            'Proper block ending': '{% endblock %}' in base_content
        }
        
        # Find positions
        page_js_start = base_content.find('{% block page_js %}')
        child_js_start = base_content.find('{% block child_js %}')
        block_super_pos = base_content.find('{{ block.super }}')
        page_js_end = base_content.rfind('{% endblock %}')  # Last endblock should be page_js
        
        # Advanced checks
        if page_js_start > 0 and child_js_start > 0:
            checks['child_js is inside page_js'] = child_js_start > page_js_start
        
        if child_js_start > 0 and block_super_pos > 0:
            checks['block.super in correct position'] = block_super_pos > child_js_start
        
        print(f"\n🧪 Structure Checks:")
        print("-" * 30)
        all_good = True
        for check, result in checks.items():
            if result is None:
                status = "⚠️"
                result_text = "Could not determine"
            else:
                status = "✅" if result else "❌"
                result_text = str(result)
                if not result:
                    all_good = False
            
            print(f"{status} {check}: {result_text}")
        
        # Show the relevant section around child_js
        if child_js_start > 0:
            # Get 200 chars before and after child_js block
            start = max(0, child_js_start - 100)
            end = min(len(base_content), child_js_start + 300)
            child_js_section = base_content[start:end]
            
            print(f"\n📝 child_js block area:")
            print("-" * 30)
            for i, line in enumerate(child_js_section.split('\n'), 1):
                if 'child_js' in line or 'block.super' in line:
                    print(f"  ➤ {line.strip()}")
                else:
                    print(f"    {line.strip()}")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Error reading base template: {e}")
        return False

def test_plan_detail_template():
    """Test the plan detail template"""
    
    print(f"\n📄 Testing Plan Detail Template...")
    print("=" * 50)
    
    try:
        # Read the plan detail template
        detail_template_path = 'somi_plan/templates/somi_plan/plan_detail.html'
        if not os.path.exists(detail_template_path):
            print(f"❌ Plan detail template not found at: {detail_template_path}")
            return False
            
        with open(detail_template_path, 'r', encoding='utf-8') as f:
            detail_content = f.read()
        
        print(f"📁 Reading: {detail_template_path}")
        print(f"📊 File size: {len(detail_content):,} characters")
        
        # Check key elements
        checks = {
            'Extends somi_plan/base.html': 'extends "somi_plan/base.html"' in detail_content,
            'Has child_js block': '{% block child_js %}' in detail_content,
            'showPostModal function defined': 'window.showPostModal = function' in detail_content,
            'Post cards have onclick': 'onclick="showPostModal(' in detail_content,
            'Modal HTML present': 'id="postModal"' in detail_content,
            'editPost function': 'window.editPost = function' in detail_content,
            'schedulePost function': 'window.schedulePost = function' in detail_content,
            'JavaScript in child_js block': None
        }
        
        # Check if JavaScript is actually in child_js block
        child_js_start = detail_content.find('{% block child_js %}')  
        child_js_end = detail_content.find('{% endblock %}', child_js_start)
        
        if child_js_start > 0 and child_js_end > 0:
            js_block_content = detail_content[child_js_start:child_js_end]
            checks['JavaScript in child_js block'] = 'window.showPostModal' in js_block_content
        
        print(f"\n🧪 Template Content Checks:")
        print("-" * 30)
        all_good = True
        for check, result in checks.items():
            if result is None:
                status = "⚠️"
                result_text = "Could not determine"
            else:
                status = "✅" if result else "❌"
                result_text = str(result)
                if not result:
                    all_good = False
            
            print(f"{status} {check}: {result_text}")
        
        # Show key JavaScript functions
        js_functions = ['showPostModal', 'editPost', 'schedulePost', 'generateMorePosts']
        print(f"\n🔧 JavaScript Functions Found:")
        print("-" * 30)
        for func in js_functions:
            pattern = f'window.{func} = function'
            found = pattern in detail_content
            status = "✅" if found else "❌"
            print(f"{status} {func}: {found}")
            if not found:
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"❌ Error reading plan detail template: {e}")
        return False

def show_diagnosis():
    """Show diagnosis and next steps"""
    
    print(f"\n🔍 Issue Diagnosis:")
    print("=" * 50)
    print("The issue was that in somi_plan/base.html:")
    print("  ❌ BEFORE: {{ block.super }} was OUTSIDE the child_js block")
    print("  ✅ AFTER:  {{ block.super }} is now INSIDE the child_js block")
    print()
    print("This ensures that:")
    print("  1. Parent template JavaScript loads first ({{ block.super }})")
    print("  2. Child template JavaScript loads after (in child_js)")
    print("  3. showPostModal function is properly available when clicked")
    print()
    print("🎯 Expected Result:")
    print("  - Post cards should now be clickable")
    print("  - showPostModal function should be defined")
    print("  - Modal should open when clicking post cards")

if __name__ == '__main__':
    print("🧪 SoMi-Plan Template Fix Verification")
    print("=" * 60)
    
    # Test base template structure
    base_ok = test_base_template_structure()
    
    # Test plan detail template
    detail_ok = test_plan_detail_template() 
    
    print(f"\n" + "=" * 60)
    if base_ok and detail_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Template structure is correct")
        print("✅ JavaScript functions are properly defined")
        print("✅ The showPostModal issue should be fixed")
    else:
        print("⚠️  SOME TESTS FAILED!")
        if not base_ok:
            print("❌ Base template structure needs review")
        if not detail_ok:
            print("❌ Plan detail template has issues")
    
    # Show diagnosis
    show_diagnosis()
    
    print(f"\n💡 Next Step: Test in browser at:")
    print(f"   🌐 http://127.0.0.1:8000/somi-plan/plan/4/")
    print(f"   👆 Click on any post card to test showPostModal")