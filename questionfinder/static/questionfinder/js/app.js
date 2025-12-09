/**
 * QuestionFinder App - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elemente
    const searchForm = document.getElementById('search-form');
    const keywordInput = document.getElementById('keyword');
    const searchBtn = document.getElementById('search-btn');
    const loadingDiv = document.getElementById('loading');
    const resultsSection = document.getElementById('results-section');
    const allQuestionsDiv = document.getElementById('all-questions');
    const totalCount = document.getElementById('total-count');

    // Debug: Check if elements exist
    console.log('Elements found:', {
        allQuestionsDiv: !!allQuestionsDiv,
        totalCount: !!totalCount,
        resultsSection: !!resultsSection
    });

    // CSRF Token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    // Aktuelles Keyword und Search ID
    let currentKeyword = '';
    let currentSearchId = null;

    // Suchformular Handler
    if (searchForm) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const keyword = keywordInput.value.trim();
            if (!keyword) {
                showToast('Bitte ein Keyword eingeben', 'warning');
                return;
            }

            currentKeyword = keyword;

            // UI aktualisieren
            searchBtn.disabled = true;
            loadingDiv.classList.remove('d-none');
            resultsSection.style.display = 'none';

            try {
                const formData = new FormData();
                formData.append('keyword', keyword);
                formData.append('csrfmiddlewaretoken', csrfToken);

                const response = await fetch('/questionfinder/search/', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    currentSearchId = data.search_id;
                    displayResults(data);
                    showToast(`${data.total_found} Fragen gefunden, ${data.total_generated} KI-generiert`, 'success');
                } else {
                    showToast(data.error || 'Fehler bei der Suche', 'danger');
                }
            } catch (error) {
                console.error('Search error:', error);
                showToast('Netzwerkfehler - bitte erneut versuchen', 'danger');
            } finally {
                searchBtn.disabled = false;
                loadingDiv.classList.add('d-none');
            }
        });
    }

    // Ergebnisse anzeigen
    function displayResults(data) {
        // Alle Fragen sammeln
        let allQuestions = [];

        // Internet-Fragen (Google, Reddit, Quora)
        if (data.scraped_questions && data.scraped_questions.length > 0) {
            data.scraped_questions.forEach(q => {
                allQuestions.push({
                    question: q.question || q,
                    intent: q.intent || 'informational',
                    category: q.category || '',
                    source: q.source || 'google'
                });
            });
        }

        // KI-generierte Fragen
        if (data.ai_generated_questions && data.ai_generated_questions.length > 0) {
            data.ai_generated_questions.forEach(q => {
                allQuestions.push({
                    question: q.question || q,
                    intent: q.intent || 'informational',
                    category: q.category || '',
                    source: 'ai'
                });
            });
        }

        // Counter aktualisieren
        if (totalCount) {
            totalCount.textContent = allQuestions.length;
        }

        // Alle Fragen anzeigen
        if (!allQuestionsDiv) {
            console.error('Element #all-questions not found!');
            return;
        }
        allQuestionsDiv.innerHTML = '';
        if (allQuestions.length > 0) {
            allQuestions.forEach(q => {
                allQuestionsDiv.appendChild(createQuestionItem(q, q.source));
            });
        } else {
            allQuestionsDiv.innerHTML = '<div class="p-3 text-muted text-center">Keine Fragen gefunden</div>';
        }

        // Ergebnisse anzeigen
        resultsSection.style.display = 'flex';
    }

    // Source Badge erstellen
    function getSourceBadge(source) {
        const badges = {
            'google': '<span class="badge bg-primary source-badge"><i class="fab fa-google"></i> Google</span>',
            'bing': '<span class="badge bg-info source-badge"><i class="fab fa-microsoft"></i> Bing</span>',
            'reddit': '<span class="badge bg-danger source-badge"><i class="fab fa-reddit"></i> Reddit</span>',
            'duckduckgo': '<span class="badge bg-secondary source-badge"><i class="fas fa-search"></i> DuckDuckGo</span>',
            'yahoo': '<span class="badge source-badge" style="background-color: #6f42c1;"><i class="fab fa-yahoo"></i> Yahoo</span>',
            'ai': '<span class="badge bg-success source-badge"><i class="fas fa-robot"></i> KI</span>',
            'ai_generated': '<span class="badge bg-success source-badge"><i class="fas fa-robot"></i> KI</span>',
            'google_paa': '<span class="badge bg-primary source-badge"><i class="fab fa-google"></i> Google</span>'
        };
        return badges[source] || '<span class="badge bg-secondary source-badge">' + source + '</span>';
    }

    // Fragen-Item erstellen
    function createQuestionItem(q, defaultSource) {
        const div = document.createElement('div');
        div.className = 'question-item d-flex justify-content-between align-items-start';

        const question = q.question || q;
        const intent = q.intent || 'informational';
        const category = q.category || '';
        const source = q.source || defaultSource;

        div.innerHTML = `
            <div class="question-content">
                <span class="question-text">${escapeHtml(question)}</span>
                <div class="mt-1">
                    ${getSourceBadge(source)}
                    <span class="badge intent-${intent} ms-1">${intent}</span>
                    ${category ? `<span class="badge bg-secondary ms-1">${escapeHtml(category)}</span>` : ''}
                </div>
            </div>
            <button class="btn btn-sm btn-outline-primary save-btn ms-2" title="Speichern">
                <i class="fas fa-bookmark"></i>
            </button>
        `;

        // Save Button Handler
        const saveBtn = div.querySelector('.save-btn');
        saveBtn.addEventListener('click', async function() {
            try {
                const formData = new FormData();
                formData.append('question', question);
                formData.append('keyword', currentKeyword);
                formData.append('intent', intent);
                formData.append('category', category);
                formData.append('source', source);
                formData.append('search_id', currentSearchId);
                formData.append('csrfmiddlewaretoken', csrfToken);

                const response = await fetch('/questionfinder/save/', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    div.classList.add('saved');
                    saveBtn.innerHTML = '<i class="fas fa-check"></i>';
                    saveBtn.classList.remove('btn-outline-primary');
                    saveBtn.classList.add('btn-success');
                    saveBtn.disabled = true;
                    showToast(data.already_saved ? 'Bereits gespeichert' : 'Frage gespeichert', 'success');
                } else {
                    showToast(data.error || 'Fehler beim Speichern', 'danger');
                }
            } catch (error) {
                console.error('Save error:', error);
                showToast('Fehler beim Speichern', 'danger');
            }
        });

        return div;
    }

    // Letzte Suchen klickbar machen
    document.querySelectorAll('.search-keyword').forEach(el => {
        el.addEventListener('click', function() {
            const keyword = this.dataset.keyword;
            if (keyword && keywordInput) {
                keywordInput.value = keyword;
                searchForm.dispatchEvent(new Event('submit'));
            }
        });
    });

    // Toast Notification
    function showToast(message, type = 'success') {
        const toastEl = document.getElementById('toast');
        const toastBody = document.getElementById('toast-message');

        if (!toastEl || !toastBody) return;

        toastBody.textContent = message;
        toastEl.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'text-white', 'text-dark');

        if (type === 'success') {
            toastEl.classList.add('bg-success', 'text-white');
        } else if (type === 'danger') {
            toastEl.classList.add('bg-danger', 'text-white');
        } else if (type === 'warning') {
            toastEl.classList.add('bg-warning', 'text-dark');
        }

        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    }

    // HTML escapen
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
