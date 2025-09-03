from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
from django.apps import apps
import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import os

@login_required
def discover_site_structure(request):
    """Automatically discover all available pages on the site"""
    try:
        base_url = request.build_absolute_uri('/')
        discovered_pages = []
        
        # 1. Get pages from URL patterns
        url_pages = get_pages_from_urls()
        discovered_pages.extend(url_pages)
        
        # 2. Crawl sitemap if exists
        sitemap_pages = get_pages_from_sitemap(base_url)
        discovered_pages.extend(sitemap_pages)
        
        # 3. Crawl main navigation
        nav_pages = crawl_navigation(base_url)
        discovered_pages.extend(nav_pages)
        
        # 4. Get pages from custom models
        custom_pages = get_custom_pages(request.user)
        discovered_pages.extend(custom_pages)
        
        # Remove duplicates and clean up
        unique_pages = {}
        for page in discovered_pages:
            url = page['url']
            if url not in unique_pages:
                unique_pages[url] = page
        
        # Sort pages by category
        categorized_pages = categorize_pages(list(unique_pages.values()))
        
        return JsonResponse({
            'success': True,
            'pages': categorized_pages,
            'total_count': len(unique_pages)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_pages_from_urls():
    """Extract pages from Django URL patterns"""
    pages = []
    
    # Static pages that we know exist
    static_pages = [
        {'url': '/', 'title': 'Startseite', 'category': 'main', 'type': 'static'},
        {'url': '/impressum/', 'title': 'Impressum', 'category': 'legal', 'type': 'static'},
        {'url': '/datenschutz/', 'title': 'Datenschutz', 'category': 'legal', 'type': 'static'},
        {'url': '/agb/', 'title': 'AGB', 'category': 'legal', 'type': 'static'},
    ]
    
    # App-based pages
    app_pages = [
        {'url': '/streamrec/', 'title': 'StreamRec', 'category': 'apps', 'type': 'app'},
        {'url': '/videos/', 'title': 'Videos', 'category': 'apps', 'type': 'app'},
        {'url': '/naturmacher/', 'title': 'Naturmacher', 'category': 'apps', 'type': 'app'},
        {'url': '/chat/', 'title': 'Chat', 'category': 'apps', 'type': 'app'},
        {'url': '/organization/', 'title': 'Organisation', 'category': 'apps', 'type': 'app'},
        {'url': '/todos/', 'title': 'Todos', 'category': 'apps', 'type': 'app'},
        {'url': '/loomads/', 'title': 'LoomAds', 'category': 'apps', 'type': 'app'},
    ]
    
    # Account pages
    account_pages = [
        {'url': '/accounts/dashboard/', 'title': 'Dashboard', 'category': 'account', 'type': 'account'},
        {'url': '/accounts/profil/', 'title': 'Profil', 'category': 'account', 'type': 'account'},
    ]
    
    pages.extend(static_pages)
    pages.extend(app_pages)
    pages.extend(account_pages)
    
    return pages


def get_pages_from_sitemap(base_url):
    """Try to get pages from sitemap.xml"""
    pages = []
    
    try:
        sitemap_url = urljoin(base_url, '/sitemap.xml')
        response = requests.get(sitemap_url, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'xml')
            urls = soup.find_all('url')
            
            for url in urls:
                loc = url.find('loc')
                if loc:
                    page_url = loc.text
                    relative_url = page_url.replace(base_url.rstrip('/'), '')
                    if not relative_url.startswith('/'):
                        relative_url = '/' + relative_url
                        
                    pages.append({
                        'url': relative_url,
                        'title': extract_title_from_url(relative_url),
                        'category': 'sitemap',
                        'type': 'discovered'
                    })
                    
    except Exception:
        pass  # Sitemap doesn't exist or is not accessible
    
    return pages


def crawl_navigation(base_url):
    """Crawl main page to find navigation links"""
    pages = []
    
    try:
        response = requests.get(base_url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find navigation elements
            nav_selectors = [
                'nav a',
                '.navbar a',
                '.navigation a', 
                '.menu a',
                'header a',
                '.nav-link',
                '.navbar-nav a'
            ]
            
            found_urls = set()
            
            for selector in nav_selectors:
                links = soup.select(selector)
                
                for link in links:
                    href = link.get('href', '')
                    if href and href.startswith('/') and href not in found_urls:
                        # Skip admin, API and non-page URLs
                        if any(skip in href for skip in ['/admin/', '/api/', '/media/', '/static/', '.json', '.xml']):
                            continue
                            
                        found_urls.add(href)
                        
                        title = link.get_text(strip=True)
                        if not title:
                            title = extract_title_from_url(href)
                            
                        pages.append({
                            'url': href,
                            'title': title,
                            'category': 'navigation',
                            'type': 'crawled'
                        })
                        
    except Exception:
        pass
    
    return pages


def get_custom_pages(user):
    """Get user-specific custom pages"""
    pages = []
    
    try:
        from accounts.models import CustomPage
        custom_pages = CustomPage.objects.filter(user=user)
        
        for page in custom_pages:
            pages.append({
                'url': f'/custom/{page.page_name}/',
                'title': page.display_name,
                'category': 'custom',
                'type': 'custom'
            })
            
    except Exception:
        pass
    
    return pages


def extract_title_from_url(url):
    """Extract a readable title from URL"""
    # Remove leading/trailing slashes and split
    parts = url.strip('/').split('/')
    if not parts or parts == ['']:
        return 'Startseite'
    
    # Take the last meaningful part
    title_part = parts[-1]
    
    # Convert to readable format
    title = title_part.replace('-', ' ').replace('_', ' ').title()
    
    # Special cases
    title_map = {
        'streamrec': 'StreamRec',
        'naturmacher': 'Naturmacher',
        'loomads': 'LoomAds',
        'dashboard': 'Dashboard',
        'impressum': 'Impressum',
        'datenschutz': 'Datenschutz',
        'agb': 'AGB'
    }
    
    return title_map.get(title_part.lower(), title)


def categorize_pages(pages):
    """Organize pages by category"""
    categories = {
        'main': {'name': 'Hauptseiten', 'pages': []},
        'apps': {'name': 'Anwendungen', 'pages': []},
        'account': {'name': 'Account', 'pages': []},
        'legal': {'name': 'Rechtliches', 'pages': []},
        'custom': {'name': 'Benutzerdefiniert', 'pages': []},
        'navigation': {'name': 'Navigation', 'pages': []},
        'other': {'name': 'Weitere', 'pages': []}
    }
    
    for page in pages:
        category = page.get('category', 'other')
        if category not in categories:
            category = 'other'
        categories[category]['pages'].append(page)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v['pages']}


@login_required
def get_page_info(request):
    """Get detailed information about a specific page"""
    try:
        page_url = request.GET.get('url', '/')
        base_url = request.build_absolute_uri('/')
        full_url = urljoin(base_url, page_url)
        
        # Fetch page content
        response = requests.get(full_url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract page information
            page_info = {
                'url': page_url,
                'title': soup.find('title').get_text(strip=True) if soup.find('title') else 'Ohne Titel',
                'meta_description': '',
                'headings': [],
                'links': [],
                'images': [],
                'editable_elements': []
            }
            
            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                page_info['meta_description'] = meta_desc.get('content', '')
            
            # Headings
            for i in range(1, 7):
                headings = soup.find_all(f'h{i}')
                for heading in headings:
                    page_info['headings'].append({
                        'level': i,
                        'text': heading.get_text(strip=True),
                        'id': heading.get('id', ''),
                        'class': heading.get('class', [])
                    })
            
            # Links
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if href.startswith('/'):
                    page_info['links'].append({
                        'url': href,
                        'text': link.get_text(strip=True),
                        'title': link.get('title', '')
                    })
            
            # Images
            images = soup.find_all('img', src=True)
            for img in images:
                page_info['images'].append({
                    'src': img['src'],
                    'alt': img.get('alt', ''),
                    'title': img.get('title', '')
                })
            
            # Count editable elements
            editable_selectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'button', 'li']
            for selector in editable_selectors:
                elements = soup.find_all(selector)
                page_info['editable_elements'].append({
                    'tag': selector,
                    'count': len(elements)
                })
            
            return JsonResponse({'success': True, 'page_info': page_info})
            
        else:
            return JsonResponse({'success': False, 'error': f'Page not accessible (HTTP {response.status_code})'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required 
def create_custom_page(request):
    """Create a new custom page"""
    try:
        if request.method == 'POST':
            import json
            data = json.loads(request.body)
            
            page_name = data.get('page_name', '').strip()
            display_name = data.get('display_name', '').strip()
            template_type = data.get('template_type', 'blank')
            
            if not page_name or not display_name:
                return JsonResponse({'success': False, 'error': 'Name und Titel sind erforderlich'})
            
            # Validate page name (URL-safe)
            if not re.match(r'^[a-zA-Z0-9_-]+$', page_name):
                return JsonResponse({'success': False, 'error': 'Seitenname darf nur Buchstaben, Zahlen, _ und - enthalten'})
            
            # Import model
            from accounts.models import CustomPage, EditableContent
            
            # Check if page already exists
            if CustomPage.objects.filter(user=request.user, page_name=page_name).exists():
                return JsonResponse({'success': False, 'error': 'Eine Seite mit diesem Namen existiert bereits'})
            
            # Create custom page
            custom_page = CustomPage.objects.create(
                user=request.user,
                page_name=page_name,
                display_name=display_name,
                page_type='custom',
                description=data.get('description', '')
            )
            
            # Create default content based on template
            create_default_content_for_page(request.user, page_name, template_type)
            
            return JsonResponse({
                'success': True,
                'page': {
                    'url': f'/custom/{page_name}/',
                    'title': display_name,
                    'category': 'custom',
                    'type': 'custom'
                }
            })
        
        return JsonResponse({'success': False, 'error': 'POST-Request erforderlich'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def create_default_content_for_page(user, page_name, template_type):
    """Create default content for new pages based on template type"""
    from accounts.models import EditableContent
    
    if template_type == 'landing':
        # Landing page template
        contents = [
            {
                'key': 'hero_title',
                'type': 'text',
                'content': 'Willkommen auf unserer neuen Seite',
                'order': 1,
                'section': 'hero'
            },
            {
                'key': 'hero_subtitle', 
                'type': 'text',
                'content': 'Hier steht eine beeindruckende Beschreibung',
                'order': 2,
                'section': 'hero'
            },
            {
                'key': 'cta_button',
                'type': 'html_block',
                'content': '<button class="btn btn-primary">Jetzt starten</button>',
                'order': 3,
                'section': 'hero'
            }
        ]
    elif template_type == 'blog':
        # Blog template
        contents = [
            {
                'key': 'blog_title',
                'type': 'text',
                'content': 'Blog-Titel',
                'order': 1,
                'section': 'header'
            },
            {
                'key': 'blog_content',
                'type': 'html_block',
                'content': '<p>Hier steht der Blog-Inhalt...</p>',
                'order': 2,
                'section': 'content'
            }
        ]
    else:
        # Blank template
        contents = [
            {
                'key': 'main_title',
                'type': 'text',
                'content': 'Neue Seite',
                'order': 1,
                'section': 'main'
            },
            {
                'key': 'main_content',
                'type': 'text', 
                'content': 'Hier können Sie Ihren Inhalt einfügen.',
                'order': 2,
                'section': 'main'
            }
        ]
    
    # Create content objects
    for content in contents:
        EditableContent.objects.create(
            user=user,
            page=page_name,
            content_key=content['key'],
            content_type=content['type'],
            text_content=content['content'],
            sort_order=content['order'],
            section=content.get('section', 'main'),
            is_active=True
        )