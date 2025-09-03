from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

def get_current_page_name(request):
    """Extract page name from URL"""
    path = request.path.strip('/')
    if not path or path == '':
        return 'startseite'
    return path

@register.simple_tag(takes_context=True)
def apply_visual_edits_simple(context):
    """Apply visual editor changes - SIMPLE VERSION"""
    try:
        request = context['request']
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return ''
        
        # Get current page name
        current_page = get_current_page_name(request)
        
        # Import models here to avoid circular imports
        from accounts.models import EditableContent
        
        # Get only SIMPLE published editable content (no complex selectors)
        edits = EditableContent.objects.filter(
            user=request.user,
            page=current_page,
            is_active=True,
            is_published=True
        ).exclude(
            content_key__contains='nth-child'
        ).exclude(
            content_key__contains='.'
        ).exclude(
            content_key__contains='main.container'
        ).order_by('sort_order')
        
        if not edits.exists():
            return ''
        
        # Build simple JavaScript
        scripts = []
        
        for edit in edits:
            content_key = edit.content_key
            
            if edit.content_type == 'text' and edit.text_content:
                script = f'''
                try {{
                    var element = document.getElementById({json.dumps(content_key)});
                    if (element) {{
                        element.textContent = {json.dumps(edit.text_content)};
                        console.log('✅ [Simple] Applied text edit:', {json.dumps(content_key)});
                    }} else {{
                        console.log('❌ [Simple] Element not found:', {json.dumps(content_key)});
                    }}
                }} catch(e) {{
                    console.error('Error applying text edit:', e);
                }}
                '''
                scripts.append(script)
                
            elif edit.content_type in ['html_block', 'ai_generated'] and edit.html_content:
                script = f'''
                try {{
                    var element = document.getElementById({json.dumps(content_key)});
                    if (element) {{
                        element.innerHTML = {json.dumps(edit.html_content)};
                        console.log('✅ [Simple] Applied HTML edit:', {json.dumps(content_key)});
                    }} else {{
                        console.log('❌ [Simple] Element not found:', {json.dumps(content_key)});
                    }}
                }} catch(e) {{
                    console.error('Error applying HTML edit:', e);
                }}
                '''
                scripts.append(script)
        
        if not scripts:
            return ''
            
        script_content = '\n'.join(scripts)
        
        return mark_safe(f'''
            <script type="text/javascript">
                // Visual Editor Simple Edits
                (function() {{
                    if (window.visualEditorSimpleApplied) return;
                    window.visualEditorSimpleApplied = true;
                    
                    console.log('[Visual Editor Simple] Starting application of {len(scripts)} edits');
                    
                    function applySimpleEdits() {{
                        {script_content}
                    }}
                    
                    // Apply immediately if DOM is ready
                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', applySimpleEdits);
                    }} else {{
                        applySimpleEdits();
                    }}
                    
                    // Apply again after dynamic content loads
                    setTimeout(applySimpleEdits, 1000);
                }})();
            </script>
        ''')
        
    except Exception as e:
        return f'<!-- Visual Editor Simple Error: {e} -->'