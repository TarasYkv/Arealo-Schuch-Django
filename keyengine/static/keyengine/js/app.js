// KeyEngine JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // CSRF Token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    // Toast-Funktion
    function showToast(message, type = 'success') {
        const toastEl = document.getElementById('toast');
        const toastBody = document.getElementById('toast-message');

        // Toast-Klassen zurücksetzen
        toastEl.classList.remove('text-bg-success', 'text-bg-danger', 'text-bg-warning');

        // Typ-spezifische Klasse hinzufügen
        if (type === 'error') {
            toastEl.classList.add('text-bg-danger');
        } else if (type === 'warning') {
            toastEl.classList.add('text-bg-warning');
        } else {
            toastEl.classList.add('text-bg-success');
        }

        toastBody.textContent = message;

        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    }

    // Copy-to-Clipboard
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(`✓ "${text}" kopiert!`, 'success');
        }).catch(err => {
            console.error('Fehler beim Kopieren:', err);
            showToast('Fehler beim Kopieren', 'error');
        });
    }

    // ============================================
    // DASHBOARD: Keyword-Generierung
    // ============================================
    const keywordForm = document.getElementById('keyword-form');
    if (keywordForm) {
        keywordForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const seedKeyword = document.getElementById('seed-keyword').value.trim();
            const count = document.getElementById('keyword-count').value;
            const generateBtn = document.getElementById('generate-btn');
            const loading = document.getElementById('loading');
            const resultsSection = document.getElementById('results-section');

            if (!seedKeyword) {
                showToast('Bitte gib ein Seed-Keyword ein', 'error');
                return;
            }

            // UI Update
            generateBtn.disabled = true;
            loading.classList.remove('d-none');
            resultsSection.style.display = 'none';

            try {
                const formData = new FormData();
                formData.append('seed_keyword', seedKeyword);
                formData.append('count', count);
                formData.append('csrfmiddlewaretoken', csrfToken);

                const response = await fetch('/keyengine/generate/', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    displayKeywords(data.keywords, seedKeyword);
                    showToast(`${data.keywords.length} Keywords generiert!`, 'success');
                } else {
                    showToast(data.error || 'Fehler bei der Generierung', 'error');
                }

            } catch (error) {
                console.error('Error:', error);
                showToast('Netzwerkfehler. Bitte versuche es erneut.', 'error');
            } finally {
                generateBtn.disabled = false;
                loading.classList.add('d-none');
            }
        });
    }

    // Keywords anzeigen
    function displayKeywords(keywords, seedKeyword) {
        const container = document.getElementById('keywords-container');
        const resultsSection = document.getElementById('results-section');
        const resultsTitle = document.getElementById('results-title');

        if (!container) return;

        // Titel aktualisieren
        resultsTitle.textContent = `Verwandte Keywords für "${seedKeyword}" (${keywords.length})`;

        // Container leeren
        container.innerHTML = '';

        // Keywords rendern
        keywords.forEach((kw, index) => {
            const keywordCard = createKeywordCard(kw, index);
            container.appendChild(keywordCard);
        });

        // Ergebnisse anzeigen
        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Keyword-Card erstellen
    function createKeywordCard(kw, index) {
        const card = document.createElement('div');
        card.className = 'keyword-card';
        card.innerHTML = `
            <div class="keyword-card-header">
                <h6 class="keyword-title">${kw.keyword}</h6>
                <span class="intent-badge intent-${kw.intent.toLowerCase().replace(/\s+/g, '')}">${kw.intent}</span>
            </div>
            <p class="keyword-description">${kw.description}</p>
            <div class="keyword-actions">
                <button class="btn btn-sm btn-outline-primary copy-btn" data-keyword="${kw.keyword}">
                    <i class="fas fa-copy"></i> Kopieren
                </button>
                <button class="btn btn-sm btn-success add-to-watchlist-btn"
                    data-keyword="${kw.keyword}"
                    data-intent="${kw.intent}"
                    data-description="${kw.description}">
                    <i class="fas fa-star"></i> Merkliste
                </button>
            </div>
        `;

        return card;
    }

    // Event Delegation für Copy-Buttons
    document.addEventListener('click', function(e) {
        if (e.target.closest('.copy-btn')) {
            const btn = e.target.closest('.copy-btn');
            const keyword = btn.dataset.keyword;
            copyToClipboard(keyword);
        }
    });

    // Event Delegation für Add-to-Watchlist
    document.addEventListener('click', async function(e) {
        if (e.target.closest('.add-to-watchlist-btn')) {
            const btn = e.target.closest('.add-to-watchlist-btn');
            const keyword = btn.dataset.keyword;
            const intent = btn.dataset.intent;
            const description = btn.dataset.description;

            await addToWatchlist(keyword, intent, description, btn);
        }
    });

    // Zu Merkliste hinzufügen
    async function addToWatchlist(keyword, intent, description, btn) {
        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('keyword', keyword);
            formData.append('intent', intent);
            formData.append('description', description);
            formData.append('csrfmiddlewaretoken', csrfToken);

            const response = await fetch('/keyengine/add/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                showToast(data.message, 'success');
                btn.innerHTML = '<i class="fas fa-check"></i> Hinzugefügt';
                btn.classList.remove('btn-success');
                btn.classList.add('btn-secondary');

                // Watchlist-Counter aktualisieren
                updateWatchlistCount();
            } else {
                showToast(data.error, data.duplicate ? 'warning' : 'error');
                btn.disabled = false;
            }

        } catch (error) {
            console.error('Error:', error);
            showToast('Fehler beim Hinzufügen zur Merkliste', 'error');
            btn.disabled = false;
        }
    }

    // Watchlist-Counter aktualisieren (optional)
    async function updateWatchlistCount() {
        // Einfache Implementierung: Counter hochzählen
        const counter = document.getElementById('watchlist-count');
        if (counter) {
            const current = parseInt(counter.textContent) || 0;
            counter.textContent = current + 1;
        }
    }

    // ============================================
    // WATCHLIST: Checkbox Toggle
    // ============================================
    document.querySelectorAll('.keyword-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', async function() {
            const keywordId = this.dataset.id;
            const isDone = this.checked;

            await updateKeyword(keywordId, 'is_done', isDone);

            // Visual Update
            const keywordItem = this.closest('.keyword-item');
            if (isDone) {
                keywordItem.classList.add('keyword-done');
            } else {
                keywordItem.classList.remove('keyword-done');
            }
        });
    });

    // ============================================
    // WATCHLIST: Priorität ändern
    // ============================================
    document.querySelectorAll('.priority-select').forEach(select => {
        select.addEventListener('change', async function() {
            const keywordId = this.dataset.id;
            const priority = this.value;

            await updateKeyword(keywordId, 'priority', priority);
        });
    });

    // ============================================
    // WATCHLIST: Keyword löschen
    // ============================================
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            if (!confirm('Keyword wirklich löschen?')) return;

            const keywordId = this.dataset.id;

            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);

                const response = await fetch(`/keyengine/delete/${keywordId}/`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    showToast(data.message, 'success');

                    // Element entfernen
                    const keywordItem = this.closest('.keyword-item');
                    keywordItem.style.opacity = '0';
                    setTimeout(() => keywordItem.remove(), 300);
                } else {
                    showToast(data.error, 'error');
                }

            } catch (error) {
                console.error('Error:', error);
                showToast('Fehler beim Löschen', 'error');
            }
        });
    });

    // Keyword aktualisieren (generisch)
    async function updateKeyword(keywordId, field, value) {
        try {
            const formData = new FormData();
            formData.append('field', field);
            formData.append('value', value);
            formData.append('csrfmiddlewaretoken', csrfToken);

            const response = await fetch(`/keyengine/update/${keywordId}/`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                // Optional: Success-Feedback
            } else {
                showToast(data.error, 'error');
            }

        } catch (error) {
            console.error('Error:', error);
            showToast('Fehler beim Aktualisieren', 'error');
        }
    }
});
