"""
Vordefinierte Suchbegriffe für BackLoom Backlink-Recherche
Kategorisiert nach Backlink-Typ
"""

DEFAULT_SEARCH_QUERIES = [
    # ===================
    # FOREN (forum)
    # ===================
    {
        'query': 'forum registrieren deutsch',
        'category': 'forum',
        'description': 'Deutsche Foren mit Registrierungsmöglichkeit',
        'priority': 8
    },
    {
        'query': 'community anmelden kostenlos',
        'category': 'forum',
        'description': 'Kostenlose Community-Plattformen',
        'priority': 7
    },
    {
        'query': 'diskussionsforum beitreten',
        'category': 'forum',
        'description': 'Diskussionsforen zum Beitreten',
        'priority': 6
    },
    {
        'query': 'fachforum deutsch',
        'category': 'forum',
        'description': 'Deutsche Fachforen',
        'priority': 7
    },
    {
        'query': '"jetzt registrieren" forum',
        'category': 'forum',
        'description': 'Foren mit Registrierungsaufruf',
        'priority': 8
    },
    {
        'query': 'phpbb forum deutsch',
        'category': 'forum',
        'description': 'phpBB-basierte deutsche Foren',
        'priority': 5
    },
    {
        'query': 'vbulletin forum deutsch',
        'category': 'forum',
        'description': 'vBulletin-basierte deutsche Foren',
        'priority': 5
    },

    # ===================
    # VERZEICHNISSE (directory)
    # ===================
    {
        'query': 'branchenbuch eintragen kostenlos',
        'category': 'directory',
        'description': 'Kostenlose Branchenbucheinträge',
        'priority': 9
    },
    {
        'query': 'firmenverzeichnis kostenlos eintragen',
        'category': 'directory',
        'description': 'Kostenlose Firmenverzeichnisse',
        'priority': 9
    },
    {
        'query': 'webkatalog anmelden',
        'category': 'directory',
        'description': 'Webkataloge für Anmeldung',
        'priority': 7
    },
    {
        'query': 'unternehmensverzeichnis deutschland',
        'category': 'directory',
        'description': 'Deutsche Unternehmensverzeichnisse',
        'priority': 8
    },
    {
        'query': 'lokale branchenverzeichnisse',
        'category': 'directory',
        'description': 'Lokale/regionale Branchenverzeichnisse',
        'priority': 8
    },
    {
        'query': '"firma eintragen" kostenlos',
        'category': 'directory',
        'description': 'Kostenloser Firmeneintrag',
        'priority': 9
    },
    {
        'query': 'business directory germany',
        'category': 'directory',
        'description': 'Internationale Business-Verzeichnisse für Deutschland',
        'priority': 6
    },
    {
        'query': 'startup verzeichnis deutschland',
        'category': 'directory',
        'description': 'Startup-Verzeichnisse',
        'priority': 7
    },

    # ===================
    # GASTBEITRÄGE (guest_post)
    # ===================
    {
        'query': 'gastbeitrag schreiben deutsch',
        'category': 'guest_post',
        'description': 'Deutsche Blogs mit Gastbeitragsmöglichkeit',
        'priority': 9
    },
    {
        'query': 'gastartikel veröffentlichen',
        'category': 'guest_post',
        'description': 'Gastartikel-Möglichkeiten',
        'priority': 9
    },
    {
        'query': '"gastautor werden"',
        'category': 'guest_post',
        'description': 'Seiten die Gastautoren suchen',
        'priority': 8
    },
    {
        'query': '"schreiben sie für uns"',
        'category': 'guest_post',
        'description': 'Blogs die Autoren suchen (deutsch)',
        'priority': 8
    },
    {
        'query': 'blog gastbeitrag einreichen',
        'category': 'guest_post',
        'description': 'Blogs mit Einreichungsmöglichkeit',
        'priority': 7
    },
    {
        'query': '"artikel einreichen" blog',
        'category': 'guest_post',
        'description': 'Artikel-Einreichung bei Blogs',
        'priority': 7
    },
    {
        'query': 'write for us germany',
        'category': 'guest_post',
        'description': 'Internationale "Write for us" Seiten',
        'priority': 6
    },
    {
        'query': 'guest post guidelines deutsch',
        'category': 'guest_post',
        'description': 'Gastbeitrag-Richtlinien',
        'priority': 6
    },

    # ===================
    # KOMMENTARE (comment)
    # ===================
    {
        'query': 'blog kommentare dofollow',
        'category': 'comment',
        'description': 'Blogs mit DoFollow-Kommentaren',
        'priority': 6
    },
    {
        'query': 'dofollow blogs deutsch',
        'category': 'comment',
        'description': 'Deutsche DoFollow-Blogs',
        'priority': 6
    },
    {
        'query': 'kommentarfunktion blog deutsch',
        'category': 'comment',
        'description': 'Blogs mit aktiver Kommentarfunktion',
        'priority': 5
    },

    # ===================
    # SOCIAL MEDIA (social)
    # ===================
    {
        'query': 'social bookmarking deutsch',
        'category': 'social',
        'description': 'Deutsche Social Bookmarking Seiten',
        'priority': 5
    },
    {
        'query': 'deutsche social media plattformen',
        'category': 'social',
        'description': 'Alternative deutsche Social-Media-Plattformen',
        'priority': 4
    },

    # ===================
    # FRAGE & ANTWORT (qa)
    # ===================
    {
        'query': 'frage antwort portal deutsch',
        'category': 'qa',
        'description': 'Deutsche Q&A-Portale',
        'priority': 7
    },
    {
        'query': 'wer weiss was alternative',
        'category': 'qa',
        'description': 'Alternativen zu Wer-weiss-was',
        'priority': 6
    },
    {
        'query': 'experten fragen portal',
        'category': 'qa',
        'description': 'Experten-Frage-Portale',
        'priority': 6
    },
    {
        'query': 'gutefrage alternative',
        'category': 'qa',
        'description': 'Alternativen zu Gutefrage',
        'priority': 6
    },

    # ===================
    # PROFILE (profile)
    # ===================
    {
        'query': 'profil erstellen kostenlos',
        'category': 'profile',
        'description': 'Kostenlose Profilseiten',
        'priority': 6
    },
    {
        'query': 'business profil anlegen',
        'category': 'profile',
        'description': 'Business-Profil Plattformen',
        'priority': 7
    },
    {
        'query': 'about.me alternative deutsch',
        'category': 'profile',
        'description': 'About.me Alternativen',
        'priority': 5
    },
    {
        'query': 'online visitenkarte erstellen',
        'category': 'profile',
        'description': 'Online-Visitenkarten-Services',
        'priority': 6
    },

    # ===================
    # WIKI (wiki)
    # ===================
    {
        'query': 'wiki artikel erstellen',
        'category': 'wiki',
        'description': 'Wiki-Plattformen für Artikelerstellung',
        'priority': 5
    },
    {
        'query': 'open wiki deutsch',
        'category': 'wiki',
        'description': 'Offene deutsche Wikis',
        'priority': 4
    },
    {
        'query': 'unternehmenswiki eintragen',
        'category': 'wiki',
        'description': 'Unternehmens-Wikis',
        'priority': 5
    },

    # ===================
    # NEWS/PRESSE (news)
    # ===================
    {
        'query': 'pressemitteilung veröffentlichen kostenlos',
        'category': 'news',
        'description': 'Kostenlose Pressemitteilungs-Portale',
        'priority': 8
    },
    {
        'query': 'presseportal kostenlos',
        'category': 'news',
        'description': 'Kostenlose Presseportale',
        'priority': 8
    },
    {
        'query': 'news einreichen portal',
        'category': 'news',
        'description': 'News-Einreichungs-Portale',
        'priority': 7
    },
    {
        'query': 'pressemeldung verteilen',
        'category': 'news',
        'description': 'Pressemeldungs-Verteilung',
        'priority': 7
    },

    # ===================
    # VIDEO (video) - Für YouTube-Suche
    # ===================
    {
        'query': 'backlinks aufbauen tutorial',
        'category': 'video',
        'description': 'YouTube: Backlink-Tutorials',
        'priority': 5
    },
    {
        'query': 'SEO linkbuilding deutsch',
        'category': 'video',
        'description': 'YouTube: SEO Linkbuilding Videos',
        'priority': 5
    },
    {
        'query': 'kostenlose backlinks bekommen',
        'category': 'video',
        'description': 'YouTube: Kostenlose Backlink-Strategien',
        'priority': 6
    },

    # ===================
    # SONSTIGE (other)
    # ===================
    {
        'query': 'link eintragen kostenlos',
        'category': 'other',
        'description': 'Allgemeine kostenlose Linkeinträge',
        'priority': 6
    },
    {
        'query': 'website eintragen',
        'category': 'other',
        'description': 'Website-Eintragungs-Services',
        'priority': 6
    },
    {
        'query': 'backlink quellen deutsch 2024',
        'category': 'other',
        'description': 'Aktuelle Backlink-Quellen',
        'priority': 7
    },
]


def get_default_queries():
    """Gibt alle vordefinierten Suchbegriffe zurück"""
    return DEFAULT_SEARCH_QUERIES


def get_queries_by_category(category):
    """Gibt Suchbegriffe einer bestimmten Kategorie zurück"""
    return [q for q in DEFAULT_SEARCH_QUERIES if q['category'] == category]
