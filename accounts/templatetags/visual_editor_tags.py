from django import template
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
import json
import re

register = template.Library()

@register.simple_tag(takes_context=True)
def apply_visual_edits(context):
    """Apply visual editor changes to the current page"""
    try:
        request = context['request']
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return ''
        
        # Get current page name
        current_page = get_current_page_name(request)
        
        # Import models here to avoid circular imports
        from accounts.models import EditableContent
        
        # Get all published editable content for this page
        edits = EditableContent.objects.filter(
            user=request.user,
            page=current_page,
            is_active=True,
            is_published=True  # Only show published changes
        ).order_by('sort_order')
        
        # Get published deleted elements to hide them
        deleted_elements = EditableContent.objects.filter(
            user=request.user,
            page=current_page,
            is_active=False,
            is_published=True,
            content_type='delete_action'
        )
        
        if not edits.exists() and not deleted_elements.exists():
            return ''
        
        # Build JavaScript and CSS to apply the edits and hide deleted elements
        script_content = build_edit_script(edits, current_page)
        delete_script = build_delete_script(deleted_elements) if deleted_elements.exists() else ''
        
        return mark_safe(f'''
            <script type="text/javascript">
                // Visual Editor Edits Applied
                (function() {{
                    if (window.visualEditorApplied) return;
                    window.visualEditorApplied = true;
                    
                    function applyVisualEdits() {{
                        // First clean up any contamination from previous runs
                        cleanupNavigationContamination();
                        
                        {script_content}
                        {delete_script}
                    }}
                    
                    // Apply edits when DOM is ready
                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', applyVisualEdits);
                    }} else {{
                        applyVisualEdits();
                    }}
                }})();
            </script>
        ''')
        
    except Exception as e:
        # In production, fail silently
        return f'<!-- Visual Editor Error: {str(e)} -->'


def get_current_page_name(request):
    """Determine current page name from request"""
    path = request.path.strip('/')
    
    if not path:
        return 'startseite'
    
    # Map common paths
    path_mapping = {
        'accounts/dashboard': 'dashboard',
        'impressum': 'impressum',
        'datenschutz': 'datenschutz',
        'agb': 'agb',
        'streamrec': 'streamrec',
        'videos': 'videos',
        'naturmacher': 'naturmacher',
        'chat': 'chat',
        'organization': 'organization',
        'todos': 'todos',
        'loomads': 'loomads',
    }
    
    return path_mapping.get(path, path.split('/')[0] if '/' in path else path)


def build_edit_script(edits, page_name):
    """Build JavaScript to apply the edits"""
    scripts = []
    
    for edit in edits:
        content_key = edit.content_key
        
        # Different approaches based on content type and key
        if edit.content_type == 'text' and edit.text_content:
            # Text content replacement using smart content matching
            script = f'''
                try {{
                    var applied = false;
                    
                    // Method 1: Try as ID first (even with underscores)
                    var element = document.getElementById({json.dumps(content_key)});
                    if (element) {{
                        element.textContent = {json.dumps(edit.text_content)};
                        console.log('✅ Applied text edit via ID:', {json.dumps(content_key)});
                        applied = true;
                    }}
                    
                    // Method 2: Smart content replacement for complex selectors
                    if (!applied) {{
                        applied = applyTextBySmartMatch({json.dumps(edit.text_content)}, {json.dumps(content_key)});
                    }}
                    
                    // Method 3: Aggressive fallback for very specific complex selectors
                    if (!applied && {json.dumps(content_key)}.includes('nth-child')) {{
                        applied = applyContentByComplexSelector({json.dumps(edit.text_content)}, {json.dumps(content_key)});
                    }}
                    
                    if (!applied) {{
                        console.log('⚠️ Could not apply text edit for:', {json.dumps(content_key)});
                    }}
                }} catch(e) {{
                    console.warn('Failed to apply text edit {content_key}:', e);
                }}
            '''
            
        elif edit.content_type in ['html_block', 'ai_generated'] and edit.html_content:
            # HTML content replacement using smart content matching
            script = f'''
                try {{
                    var applied = false;
                    
                    // Method 1: Try as ID first (even with underscores)
                    var element = document.getElementById({json.dumps(content_key)});
                    if (element) {{
                        element.innerHTML = {json.dumps(edit.html_content)};
                        console.log('✅ Applied HTML edit via ID:', {json.dumps(content_key)});
                        applied = true;
                    }}
                    
                    // Method 2: Smart content replacement for complex selectors
                    if (!applied) {{
                        applied = applyHtmlBySmartMatch({json.dumps(edit.html_content)}, {json.dumps(content_key)});
                    }}
                    
                    // Method 3: Aggressive fallback for very specific complex selectors
                    if (!applied && {json.dumps(content_key)}.includes('nth-child')) {{
                        applied = applyHtmlByComplexSelector({json.dumps(edit.html_content)}, {json.dumps(content_key)});
                    }}
                    
                    if (!applied) {{
                        console.log('⚠️ Could not apply HTML edit for:', {json.dumps(content_key)});
                    }}
                }} catch(e) {{
                    console.warn('Failed to apply HTML edit {content_key}:', e);
                }}
            '''
            
        else:
            continue
        
        scripts.append(script)
    
    # Add helper functions
    helper_script = '''
        function applyTextBySmartMatch(newText, contentKey) {
            console.log('🔍 Trying smart text match for:', contentKey);
            
            // Helper function to check if element is in excluded areas
            function isInExcludedArea(element) {
                var current = element;
                while (current && current !== document.body) {
                    var classList = current.classList;
                    var id = current.id;
                    var tagName = current.tagName.toLowerCase();
                    
                    // Exclude navigation, menu, header, footer areas
                    if (tagName === 'nav' || tagName === 'header' || tagName === 'footer' ||
                        classList.contains('navbar') || classList.contains('menu') || 
                        classList.contains('navigation') || classList.contains('dropdown') ||
                        id.includes('nav') || id.includes('menu') || id.includes('header')) {
                        return true;
                    }
                    current = current.parentElement;
                }
                return false;
            }
            
            // Strategy 1: Try to match by existing text content (broader search but protected)  
            var textElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, a, button, li, div');
            for (var element of textElements) {
                if (isInExcludedArea(element)) continue;
                
                if (element.children.length === 0 && element.textContent.trim()) {
                    var currentText = element.textContent.trim();
                    
                    // Strategy 1a: Exact text match (most reliable)
                    if (currentText === newText) {
                        element.textContent = newText;
                        console.log('✅ Smart text match successful via exact match');
                        return true;
                    }
                    
                    // Strategy 1b: Element type and context matching
                    if (currentText.length > 3 && currentText.length < 500) {
                        var isGoodMatch = false;
                        
                        // Type-based matching
                        if ((contentKey.includes('button') || contentKey.includes('btn')) && 
                            (element.tagName.toLowerCase() === 'button' || element.classList.contains('btn'))) {
                            isGoodMatch = true;
                        } else if (contentKey.includes('link') && element.tagName.toLowerCase() === 'a') {
                            isGoodMatch = true;
                        } else if (contentKey.includes('title') && ['h1','h2','h3','h4','h5','h6'].includes(element.tagName.toLowerCase())) {
                            isGoodMatch = true;
                        } else if (element.tagName.toLowerCase() === 'li' && newText.length < 100) {
                            isGoodMatch = true; // List items are often targets
                        } else if (element.tagName.toLowerCase() === 'span' && newText.length < 50) {
                            isGoodMatch = true; // Spans often contain short text
                        }
                        
                        if (isGoodMatch) {
                            element.textContent = newText;
                            console.log('✅ Smart text match successful via element type matching');
                            return true;
                        }
                    }
                }
            }
            
            // Strategy 2: Find by similar text length and context (only in main content areas)
            var mainTextElements = document.querySelectorAll('main *, .content *, .main-content *, #content *');
            for (var element of mainTextElements) {
                if (isInExcludedArea(element)) continue;
                
                if (element.children.length === 0) {
                    var currentText = element.textContent.trim();
                    if (currentText && Math.abs(currentText.length - newText.length) < 20) {
                        // Additional safety check: avoid very common text
                        if (!currentText.toLowerCase().includes('menu') && 
                            !currentText.toLowerCase().includes('navigation') &&
                            currentText.length > 10) {
                            element.textContent = newText;
                            console.log('✅ Smart text match successful via length similarity');
                            return true;
                        }
                    }
                }
            }
            
            console.log('❌ Smart text match failed');
            return false;
        }
        
        function applyHtmlBySmartMatch(newHtml, contentKey) {
            console.log('🔍 Trying smart HTML match for:', contentKey);
            
            // Helper function to check if element is in excluded areas (reuse from text function)
            function isInExcludedArea(element) {
                var current = element;
                while (current && current !== document.body) {
                    var classList = current.classList;
                    var id = current.id;
                    var tagName = current.tagName.toLowerCase();
                    
                    // Exclude navigation, menu, header, footer areas
                    if (tagName === 'nav' || tagName === 'header' || tagName === 'footer' ||
                        classList.contains('navbar') || classList.contains('menu') || 
                        classList.contains('navigation') || classList.contains('dropdown') ||
                        id.includes('nav') || id.includes('menu') || id.includes('header')) {
                        return true;
                    }
                    current = current.parentElement;
                }
                return false;
            }
            
            // Strategy 1: Find elements that contain similar content (broader search but protected)
            var htmlElements = document.querySelectorAll('div, section, article, li, td, span, p, a, button');
            for (var element of htmlElements) {
                if (isInExcludedArea(element)) continue;
                
                if (element.innerHTML && element.innerHTML.trim()) {
                    var currentHtml = element.innerHTML.trim();
                    
                    // Strategy 1a: Exact content match (most reliable)
                    if (currentHtml === newHtml) {
                        console.log('✅ Smart HTML match successful via exact content match');
                        return true;
                    }
                    
                    // Strategy 1b: Content similarity with better heuristics
                    if (currentHtml.length > 20 && Math.abs(currentHtml.length - newHtml.length) < 300) {
                        // More flexible content matching
                        if (element.classList.contains('card-body') || 
                            element.classList.contains('tool-features') ||
                            element.classList.contains('feature-card') ||
                            element.tagName.toLowerCase() === 'li' ||
                            element.tagName.toLowerCase() === 'span' ||
                            element.tagName.toLowerCase() === 'button' ||
                            element.tagName.toLowerCase() === 'a') {
                            element.innerHTML = newHtml;
                            console.log('✅ Smart HTML match successful via flexible content similarity');
                            return true;
                        }
                    }
                }
            }
            
            // Strategy 2: Look for empty or placeholder elements (only in main content)
            var mainEmptyElements = document.querySelectorAll('main div, .content div, .main-content div, #content div');
            for (var element of mainEmptyElements) {
                if (isInExcludedArea(element)) continue;
                
                if (!element.innerHTML.trim() || element.innerHTML.trim() === '&nbsp;') {
                    element.innerHTML = newHtml;
                    console.log('✅ Smart HTML match successful via empty element');
                    return true;
                }
            }
            
            console.log('❌ Smart HTML match failed - being conservative to avoid menu contamination');
            return false;
        }
        
        // Legacy function kept for compatibility
        function applyContentByTextMatch(newText) {
            return applyTextBySmartMatch(newText, 'legacy');
        }
        
        // Aggressive fallback functions for complex nth-child selectors
        function applyContentByComplexSelector(newContent, contentKey) {
            console.log('🚀 Trying aggressive complex selector match for:', contentKey);
            
            // Parse the complex selector to extract useful parts
            var parts = contentKey.split('_');
            var hints = [];
            
            for (var part of parts) {
                if (part.includes('btn') || part.includes('button')) hints.push('button');
                if (part.includes('card')) hints.push('.card');
                if (part.includes('hero')) hints.push('.hero');
                if (part.includes('tool')) hints.push('.tool');
                if (part.includes('feature')) hints.push('.feature');
                if (part.includes('li') && part.includes('nth-child')) hints.push('li');
                if (part.includes('span') && part.includes('nth-child')) hints.push('span');
            }
            
            // Try to find elements using the extracted hints
            for (var hint of hints) {
                var elements = document.querySelectorAll(hint);
                for (var element of elements) {
                    if (isInExcludedArea(element)) continue;
                    
                    if (element.children.length === 0 && element.textContent.trim()) {
                        var currentText = element.textContent.trim();
                        // If length is similar or element is very specific, try replacing
                        if (Math.abs(currentText.length - newContent.length) < 50) {
                            element.textContent = newContent;
                            console.log('🚀 Aggressive match successful via hint:', hint);
                            return true;
                        }
                    }
                }
            }
            
            console.log('❌ Aggressive complex selector match failed');
            return false;
        }
        
        function applyHtmlByComplexSelector(newHtml, contentKey) {
            console.log('🚀 Trying aggressive HTML complex selector match for:', contentKey);
            
            // Same hint extraction logic
            var parts = contentKey.split('_');
            var hints = [];
            
            for (var part of parts) {
                if (part.includes('card')) hints.push('.card-body');
                if (part.includes('tool')) hints.push('.tool-features');
                if (part.includes('feature')) hints.push('.feature-card');
                if (part.includes('hero')) hints.push('.hero-section');
                if (part.includes('li') && part.includes('nth-child')) hints.push('li');
                if (part.includes('div') && part.includes('nth-child')) hints.push('div');
            }
            
            // Try to find elements using the extracted hints  
            for (var hint of hints) {
                var elements = document.querySelectorAll(hint);
                for (var element of elements) {
                    if (isInExcludedArea(element)) continue;
                    
                    if (element.innerHTML && element.innerHTML.trim()) {
                        var currentHtml = element.innerHTML.trim();
                        if (Math.abs(currentHtml.length - newHtml.length) < 200) {
                            element.innerHTML = newHtml;
                            console.log('🚀 Aggressive HTML match successful via hint:', hint);
                            return true;
                        }
                    }
                }
            }
            
            console.log('❌ Aggressive HTML complex selector match failed');
            return false;
        }
        
        // Cleanup function to remove accidentally inserted content from navigation areas
        function cleanupNavigationContamination() {
            var navElements = document.querySelectorAll('nav, header, .navbar, .menu, .navigation, .dropdown, [id*="nav"], [id*="menu"], [id*="header"]');
            var cleaned = 0;
            
            for (var navElement of navElements) {
                var textNodes = navElement.querySelectorAll('*');
                for (var node of textNodes) {
                    var text = node.textContent;
                    // Check for accidentally inserted content (look for common patterns)
                    if (text && (text.includes('KI-Bildgenerierung') || 
                               text.includes('Browser-basierter') ||
                               text.includes('Canva-Import') ||
                               text.includes('Projekt-basierte') ||
                               text.includes('Direkte Shopify') ||
                               text.length > 100)) {
                        // This looks like content that doesn't belong in navigation
                        if (node.children.length === 0) {
                            node.textContent = '';
                            cleaned++;
                            console.log('🧹 Cleaned contaminated navigation text');
                        }
                    }
                }
            }
            
            if (cleaned > 0) {
                console.log(`🧹 Cleaned ${cleaned} contaminated navigation elements`);
            }
        }
    '''
    
    return helper_script + '\n'.join(scripts)


def build_delete_script(deleted_elements):
    """Build JavaScript to hide deleted elements"""
    scripts = []
    
    for element in deleted_elements:
        content_key = element.content_key
        
        script = f'''
            try {{
                var element = document.getElementById({json.dumps(content_key)});
                if (element) {{
                    element.style.display = 'none';
                    element.setAttribute('data-deleted', 'true');
                    console.log('🗑️ Hidden deleted element:', {json.dumps(content_key)});
                }} else {{
                    console.log('❌ Deleted element not found:', {json.dumps(content_key)});
                }}
            }} catch(e) {{
                console.error('Error hiding deleted element:', e);
            }}
        '''
        scripts.append(script)
    
    return '\n'.join(scripts)


@register.simple_tag(takes_context=True)
def visual_editor_element(context, tag='div', content_key='', default_content='', **kwargs):
    """Create an element that can be edited with the visual editor"""
    try:
        request = context['request']
        
        # Build attributes
        attrs = []
        for key, value in kwargs.items():
            attrs.append(f'{key}="{value}"')
        
        attrs.append(f'data-edit-key="{content_key}"')
        attrs.append(f'data-content-key="{content_key}"')
        attrs.append('data-visual-editor="true"')
        
        # Get saved content if user is authenticated
        saved_content = default_content
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from accounts.models import EditableContent
                current_page = get_current_page_name(request)
                
                edit = EditableContent.objects.filter(
                    user=request.user,
                    page=current_page,
                    content_key=content_key,
                    is_active=True,
                    is_published=True  # Only show published changes
                ).first()
                
                if edit:
                    if edit.html_content:
                        saved_content = edit.html_content
                    elif edit.text_content:
                        saved_content = edit.text_content
            except:
                pass
        
        attrs_str = ' '.join(attrs)
        return mark_safe(f'<{tag} {attrs_str}>{saved_content}</{tag}>')
        
    except Exception as e:
        return mark_safe(f'<{tag}>{default_content}</{tag}>')


@register.inclusion_tag('visual_editor/editable_text.html', takes_context=True)
def editable_text(context, content_key, default_text='', tag='p', css_class=''):
    """Render editable text element"""
    return {
        'content_key': content_key,
        'default_text': default_text,
        'tag': tag,
        'css_class': css_class,
        'request': context['request']
    }


@register.inclusion_tag('visual_editor/editable_html.html', takes_context=True)
def editable_html(context, content_key, default_html='', tag='div', css_class=''):
    """Render editable HTML element"""
    return {
        'content_key': content_key,
        'default_html': default_html,
        'tag': tag,
        'css_class': css_class,
        'request': context['request']
    }


@register.simple_tag(takes_context=True)
def visual_content(context, page, content_key, default_text=''):
    """
    Simple template tag to show visual editor content or default text
    Usage: {% visual_content 'startseite' 'h2_tools_overview' 'Default text' %}
    """
    try:
        request = context['request']
        
        # For authenticated users, try to get saved content
        if hasattr(request, 'user') and request.user.is_authenticated:
            from accounts.models import EditableContent
            
            try:
                content = EditableContent.objects.get(
                    user=request.user,
                    page=page,
                    content_key=content_key,
                    is_active=True,
                    is_published=True
                )
                
                # Return saved content (text or html)
                if content.text_content:
                    return mark_safe(content.text_content)
                elif content.html_content:
                    return mark_safe(content.html_content)
                    
            except EditableContent.DoesNotExist:
                pass
        
        # Return default text if no saved content found
        return mark_safe(default_text)
        
    except Exception as e:
        # If anything goes wrong, return default text
        return mark_safe(default_text)