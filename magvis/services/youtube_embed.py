"""YouTube-URL-Parser und Shorts-Embed-Helper."""
import re

YT_PATTERNS = [
    r'(?:youtu\.be/|youtube\.com/(?:embed/|v/|shorts/|watch\?v=|watch\?.+&v=))([A-Za-z0-9_-]{11})',
]


def extract_video_id(url: str) -> str | None:
    """Extrahiert YouTube-Video-ID aus URL (Standard, Shorts, embed, youtu.be)."""
    if not url:
        return None
    for pattern in YT_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def embed_html(video_id: str, *, height: int = 720, width: str = '100%', is_short: bool = True) -> str:
    """Liefert iframe-HTML für Blog-Embed.

    Shorts werden hochkant (9:16) ausgegeben — wie auf Naturmacher-Blog.
    """
    if not video_id:
        return ''
    if is_short:
        # Hochkant für Shorts (wie auf Naturmacher-Blog)
        return (
            f'<div class="magvis-youtube-short" style="display:flex;justify-content:center;margin:2rem 0;">'
            f'<iframe src="https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1" '
            f'width="405" height="{height}" '
            f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
            f'gyroscope; picture-in-picture" allowfullscreen '
            f'style="max-width:100%;border-radius:12px;"></iframe>'
            f'</div>'
        )
    return (
        f'<div class="magvis-youtube" style="position:relative;padding-bottom:56.25%;height:0;margin:2rem 0;">'
        f'<iframe src="https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1" '
        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
        f'gyroscope; picture-in-picture" allowfullscreen '
        f'style="position:absolute;top:0;left:0;width:100%;height:100%;border-radius:12px;"></iframe>'
        f'</div>'
    )
