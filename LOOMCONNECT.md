# LoomConnect - Implementierungsdokumentation

**Status:** 🟡 In Entwicklung
**Version:** 1.0.0-alpha
**Letzte Aktualisierung:** 2025-01-12

---

## 📋 Projektübersicht

**LoomConnect** ist ein Skill-Matching & Networking-Tool für WorkLoom, das es Benutzern ermöglicht, ihre Fähigkeiten anzubieten, benötigte Skills zu finden und sich mit anderen Nutzern zu vernetzen.

### Kern-Features
- ✅ Profil-System mit Skills & Bedarfen
- ✅ Discovery Feed (Instagram-Style)
- ✅ Connect-Request System mit Chat-Integration
- ✅ Posts & Kommentar-System
- ✅ Skill-basiertes Matching
- ✅ Stories (24h verfügbar)
- ✅ LoomAds Integration
- ✅ Stats & Analytics Tracking
- ✅ SEO-optimierte Info-Seiten

---

## 🏗️ Architektur

### Datenbank-Modelle

#### 1. **ConnectProfile**
User-Profil für LoomConnect

**Felder:**
- `user` - OneToOne zu CustomUser
- `bio` - Über mich Text (max 500 Zeichen)
- `avatar` - Profilbild
- `is_public` - Öffentlich sichtbar
- `show_online_status` - Online-Status anzeigen
- `profile_views_count` - Anzahl Profil-Aufrufe
- `karma_score` - Karma-Punkte
- `successful_connections` - Erfolgreiche Verbindungen
- `onboarding_completed` - Onboarding abgeschlossen

**Methoden:**
- `get_skills()` - Alle Skills die User anbietet
- `get_needs()` - Alle aktiven Bedarfe
- `get_connections_count()` - Anzahl Verbindungen
- `is_online()` - Online-Status prüfen

#### 2. **SkillCategory**
Kategorien für Skills (z.B. Entwicklung, Design)

**Felder:**
- `name`, `slug`, `icon`, `description`
- `order` - Sortierung
- `is_active` - Aktiv/Inaktiv

#### 3. **Skill**
Einzelne Skills (vordefiniert oder custom)

**Felder:**
- `category` - FK zu SkillCategory
- `name`, `slug`, `icon`, `description`
- `is_predefined` - Vordefiniert oder custom
- `created_by` - User der Skill erstellt hat (bei custom)
- `usage_count` - Wie oft verwendet
- `is_active`

#### 4. **UserSkill**
Skills die ein User hat/anbietet

**Felder:**
- `profile` - FK zu ConnectProfile
- `skill` - FK zu Skill
- `level` - Anfänger, Fortgeschritten, Experte, Profi
- `years_experience` - Jahre Erfahrung (optional)
- `is_offering` - Bietet Hilfe an
- `description` - Zusatzinfos

#### 5. **UserNeed**
Skills die ein User sucht

**Felder:**
- `profile`, `skill`
- `description` - Was genau gesucht wird
- `urgency` - Niedrig, Mittel, Hoch
- `is_active`

#### 6. **ConnectPost**
Feed-Posts

**Felder:**
- `author` - FK zu ConnectProfile
- `content` - Post-Inhalt (max 1000 Zeichen)
- `post_type` - offering, seeking, update, achievement, question
- `image` - Optional
- `related_skills` - M2M zu Skill
- Stats: `likes_count`, `comments_count`, `views_count`

#### 7. **PostComment**
Kommentare zu Posts

**Felder:**
- `post`, `author`, `content`
- `parent_comment` - Für Replies
- `is_edited`

#### 8. **PostLike**
Likes für Posts

#### 9. **ConnectRequest**
Connect-Anfragen zwischen Usern

**Felder:**
- `from_profile`, `to_profile`
- `message` - Anfrage-Nachricht
- `request_type` - skill_exchange, help_request, networking, collaboration
- `related_skill` - Bezug zu Skill (optional)
- `status` - pending, accepted, declined, expired
- `chat_room` - FK zu ChatRoom (nach Accept)
- `expires_at` - Ablaufdatum

**Methoden:**
- `accept()` - Anfrage akzeptieren
- `decline()` - Anfrage ablehnen
- `is_expired()` - Prüfen ob abgelaufen

#### 10. **Connection**
Aktive Verbindungen zwischen Usern

**Felder:**
- `profile_1`, `profile_2`
- `chat_room` - Zugehöriger Chat
- `connect_request` - Original Request
- `is_active`

#### 11. **SkillExchange**
Tracking von Skill-Tausch

**Felder:**
- `connection`
- `skill_offered`, `skill_requested`
- `status` - active, completed, cancelled
- `notes`

#### 12. **ProfileView**
Tracking von Profil-Aufrufen

#### 13. **ConnectStory**
Stories (24h verfügbar)

**Felder:**
- `profile`, `content`, `story_type`, `image`
- `views_count`
- `expires_at` - 24h nach Erstellung

#### 14. **StoryView**
Story-View-Tracking

---

## 🔧 Installation & Setup

### Schritt 1: App registrieren

In `Schuch/settings.py`:
```python
INSTALLED_APPS = [
    # ... andere Apps
    'loomconnect',
]
```

### Schritt 2: AppPermission erstellen

In `accounts/models.py` → `APP_CHOICES` hinzufügen:
```python
('loomconnect', 'LoomConnect'),
```

Initial nur für Superuser:
- Zugriffsebene: "Nur Superuser"
- Später: "Alle registrierten Nutzer"

### Schritt 3: Migrations erstellen

```bash
python manage.py makemigrations loomconnect
python manage.py migrate loomconnect
```

### Schritt 4: AppPermission in Admin erstellen

Im Django-Admin:
1. Accounts → App-Berechtigungen → Hinzufügen
2. App: "loomconnect"
3. Zugriffsebene: "Nur Superuser"
4. Aktiv: ✓
5. Speichern

### Schritt 5: Default Skills laden

Management Command erstellen:
```bash
python manage.py create_default_skills
```

---

## 📂 Dateistruktur

```
loomconnect/
├── models.py ✅               # Alle Datenbank-Modelle
├── admin.py ✅                # Admin-Interface Konfiguration
├── apps.py ✅                 # App-Konfiguration
├── signals.py ✅              # Signal-Handler (Chat-Integration)
├── views.py ⏳                # View-Logic
├── urls.py ⏳                 # URL-Routing
├── forms.py ⏳                # Forms & Validation
├── decorators.py ⏳           # Custom Decorators
├── utils.py ⏳                # Utility Functions
├── templatetags/              # Custom Template Tags
│   └── loomconnect_tags.py ⏳
├── templates/
│   └── loomconnect/
│       ├── base.html
│       ├── dashboard.html
│       ├── feed.html
│       ├── discover.html
│       ├── profile.html
│       ├── post_detail.html
│       ├── onboarding/
│       │   ├── welcome.html
│       │   ├── step_skills.html
│       │   ├── step_level.html
│       │   ├── step_needs.html
│       │   ├── step_availability.html
│       │   └── step_profile.html
│       ├── includes/
│       │   ├── profile_card.html
│       │   ├── post_card.html
│       │   ├── story_circle.html
│       │   └── connect_request_card.html
│       └── info.html
├── static/
│   └── loomconnect/
│       ├── css/
│       │   ├── loomconnect.css
│       │   └── glassmorphism.css
│       ├── js/
│       │   ├── feed.js
│       │   ├── swipe.js
│       │   └── stories.js
│       └── img/
└── management/
    └── commands/
        ├── create_default_skills.py ⏳
        ├── cleanup_expired_stories.py ⏳
        └── create_loomconnect_zones.py ⏳
```

**Legende:** ✅ Fertig | ⏳ In Arbeit | ❌ Nicht gestartet

---

## 🎯 Implementierungs-Roadmap

### ✅ Phase 1: Grundgerüst (ABGESCHLOSSEN)
- [x] App erstellt
- [x] Models definiert
- [x] Admin-Interface konfiguriert
- [x] Signals eingerichtet

### ⏳ Phase 2: Onboarding & Profile
1. Onboarding-Flow Views
2. Profile Views (Detail, Edit, Public)
3. Skill-Management (Hinzufügen, Bearbeiten, Löschen)
4. Need-Management

### ⏳ Phase 3: Discovery & Feed
1. Feed-View (Posts anzeigen)
2. Discover-View (Browse/Search)
3. Matching-Algorithmus
4. Filter & Sortierung

### ⏳ Phase 4: Posts & Interaktion
1. Post erstellen/bearbeiten/löschen
2. Like-Funktion (AJAX)
3. Kommentar-System (nested)
4. Share-Funktion

### ⏳ Phase 5: Connect-Requests
1. Request senden
2. Request-Inbox
3. Accept/Decline Logic
4. Chat-Room Auto-Creation (via Signal)

### ⏳ Phase 6: Stories
1. Story erstellen
2. Story-Anzeige (Horizontal Scroll)
3. Story-Viewer
4. Auto-Cleanup (Cron-Job)

### ⏳ Phase 7: LoomAds
1. Ad-Zones erstellen (Management Command)
2. Template-Integration
3. App-Campaign Setup

### ⏳ Phase 8: Stats & Analytics
1. PageVisit Tracking
2. Custom Metrics
3. Admin-Dashboard

### ⏳ Phase 9: SEO & Public Pages
1. Info-Seite
2. Meta Tags
3. Sitemap-Eintrag
4. Structured Data

### ⏳ Phase 10: UI/UX Polish
1. Responsive Design
2. Glassmorphism CSS
3. Micro-Interactions
4. Loading States

---

## 🎨 Design-System

### Farben
```css
:root {
  --primary: #667eea;        /* Soft Purple */
  --secondary: #764ba2;      /* Deep Purple */
  --accent: #f093fb;         /* Pink */
  --success: #10b981;        /* Green */
  --background: #0f172a;     /* Dark Blue */
  --card: rgba(255,255,255,0.05); /* Glassmorphic */
  --text: #e2e8f0;          /* Light Gray */
}
```

### Komponenten

#### Profile Card
```html
<div class="profile-card glassmorphic">
  <img src="avatar" class="avatar-3d">
  <h3>Name</h3>
  <p class="bio">...</p>
  <div class="skills">
    <span class="skill-pill">Python</span>
    ...
  </div>
  <button class="btn-connect">Verbinden</button>
</div>
```

#### Post Card
```html
<div class="post-card">
  <div class="post-header">
    <img src="avatar"> <span>Username</span>
  </div>
  <div class="post-content">...</div>
  <div class="post-actions">
    <button class="btn-like">💚 Like</button>
    <button class="btn-comment">💬 Comment</button>
  </div>
</div>
```

---

## 🔌 Integration

### Chat-System
```python
# signals.py
@receiver(post_save, sender=ConnectRequest)
def create_chat_on_accept(sender, instance, created, **kwargs):
    if instance.status == 'accepted' and not instance.chat_room:
        # ChatRoom erstellen
        # Connection erstellen
        # Karma erhöhen
```

### LoomAds
```python
# Management Command
python manage.py create_loomconnect_zones

# Template
{% load loomads_tags %}
{% show_ad 'loomconnect_feed_inline' %}
```

### Stats
```python
# In Views
from stats.models import PageVisit
PageVisit.objects.create(...)
```

### SEO
```python
# core/sitemaps.py
class LoomConnectSitemap(Sitemap):
    def items(self):
        return ['loomconnect:info']
```

---

## 🧪 Testing

### Unit Tests
```python
# tests/test_models.py
class ConnectProfileTest(TestCase):
    def test_profile_creation(self):...
    def test_karma_increase(self):...
```

### Integration Tests
```python
# tests/test_connect_flow.py
def test_full_connect_flow(self):
    # 1. Send Request
    # 2. Accept Request
    # 3. Verify Chat Created
    # 4. Verify Connection Exists
```

---

## 📝 Management Commands

### create_default_skills
Lädt vordefinierte Skills aus JSON

**Usage:**
```bash
python manage.py create_default_skills
```

**JSON-Struktur:**
```json
{
  "Entwicklung": {
    "icon": "💻",
    "skills": ["Python", "Django", "React", ...]
  },
  "Design": {
    "icon": "🎨",
    "skills": ["Figma", "Photoshop", ...]
  }
}
```

### cleanup_expired_stories
Löscht abgelaufene Stories (>24h)

**Usage:**
```bash
python manage.py cleanup_expired_stories
```

**Cron:** Täglich um 3 Uhr

### create_loomconnect_zones
Erstellt LoomAds Zones

**Zones:**
- `loomconnect_feed_top` - Header Banner (728x90)
- `loomconnect_feed_inline` - In-Feed (350x250)
- `loomconnect_discovery_sidebar` - Sidebar (300x250)
- `loomconnect_profile_bottom` - Profile Bottom (728x90)

---

## 🚀 Deployment Checklist

- [ ] Migrations auf Production ausführen
- [ ] AppPermission für Superuser erstellen
- [ ] Default Skills laden
- [ ] Ad-Zones erstellen
- [ ] Cron-Jobs einrichten (Story Cleanup)
- [ ] Static Files sammeln
- [ ] Email-Templates konfigurieren
- [ ] Monitoring einrichten (Sentry)
- [ ] Performance-Tests durchführen

---

## 📚 Weitere Dokumentation

- [Django Models Reference](https://docs.djangoproject.com/en/5.0/topics/db/models/)
- [Chat-System Integration](./chat/README.md)
- [LoomAds System](./loomads/README.md)
- [Stats Tracking](./stats/README.md)

---

## 🐛 Known Issues

*Keine aktuellen Issues*

---

## 🔮 Future Features (v2.0)

- [ ] AI-basiertes Skill-Matching
- [ ] Video-Call Integration
- [ ] Skill-Zertifikate
- [ ] Reputation-System mit Badges
- [ ] Advanced Search (Filters, Faceted Search)
- [ ] Notification-Center
- [ ] Email-Digests
- [ ] Export-Funktion (Skills PDF)
- [ ] Mobile App (React Native)

---

**Entwickelt für WorkLoom by Claude** 🤖
