"""
Utility functions for email templates
"""
from html.parser import HTMLParser
import re


class HTMLToTextConverter(HTMLParser):
    """
    Converts HTML to plain text while preserving structure
    """
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {'script', 'style', 'head'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        # Add line breaks for block elements
        if tag in {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'}:
            self.text_parts.append('\n')
        if tag == 'li':
            self.text_parts.append('- ')

    def handle_endtag(self, tag):
        self.current_tag = None
        # Add extra line break after headings and paragraphs
        if tag in {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self.text_parts.append('\n')

    def handle_data(self, data):
        # Skip content in script/style/head tags
        if self.current_tag not in self.skip_tags:
            # Clean up whitespace but preserve template variables
            text = data.strip()
            if text:
                self.text_parts.append(text)
                self.text_parts.append(' ')

    def get_text(self):
        text = ''.join(self.text_parts)
        # Clean up multiple spaces and line breaks
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        return text.strip()


def html_to_text(html_content):
    """
    Convert HTML content to plain text

    Args:
        html_content (str): HTML content to convert

    Returns:
        str: Plain text version
    """
    if not html_content:
        return ''

    # Parse HTML and convert to text
    converter = HTMLToTextConverter()
    try:
        converter.feed(html_content)
        text = converter.get_text()
        return text
    except Exception as e:
        # Fallback: just strip all HTML tags
        import html
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def sync_text_from_html(html_content):
    """
    Generate text content from HTML content
    Preserves Django template variables like {{ variable }}

    Args:
        html_content (str): HTML content

    Returns:
        str: Plain text version suitable for email text content
    """
    text = html_to_text(html_content)

    # Ensure template variables are preserved
    # They should already be preserved by the HTMLParser

    return text