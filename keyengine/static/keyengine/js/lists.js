/**
 * KeyEngine - Listen-Management JavaScript
 */

// CSRF Token
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Toast anzeigen
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastBody = document.getElementById('toast-message');

    toastBody.textContent = message;
    toast.className = `toast align-items-center text-white bg-${type}`;

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// ==================== Listen-Verwaltung ====================

// Modal für neue Liste anzeigen
function showCreateListModal() {
    document.getElementById('listModalTitle').textContent = 'Neue Liste erstellen';
    document.getElementById('list_id').value = '';
    document.getElementById('list_name').value = '';
    document.getElementById('list_description').value = '';

    // Erste Farbe auswählen
    const firstColorRadio = document.querySelector('input[name="list_color"]');
    if (firstColorRadio) {
        firstColorRadio.checked = true;
    }

    const modal = new bootstrap.Modal(document.getElementById('listModal'));
    modal.show();
}

// Modal zum Bearbeiten einer Liste anzeigen
function editList(listId, name, color, description) {
    document.getElementById('listModalTitle').textContent = 'Liste bearbeiten';
    document.getElementById('list_id').value = listId;
    document.getElementById('list_name').value = name;
    document.getElementById('list_description').value = description;

    // Richtige Farbe auswählen
    const colorRadio = document.querySelector(`input[name="list_color"][value="${color}"]`);
    if (colorRadio) {
        colorRadio.checked = true;
    }

    const modal = new bootstrap.Modal(document.getElementById('listModal'));
    modal.show();
}

// Liste speichern (erstellen oder aktualisieren)
async function saveList() {
    const listId = document.getElementById('list_id').value;
    const name = document.getElementById('list_name').value.trim();
    const color = document.querySelector('input[name="list_color"]:checked').value;
    const description = document.getElementById('list_description').value.trim();

    if (!name) {
        showToast('Bitte gib einen Namen ein', 'danger');
        return;
    }

    const isEdit = listId !== '';
    const url = isEdit
        ? `/keyengine/list/${listId}/update/`
        : '/keyengine/list/create/';

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRFToken());
    formData.append('name', name);
    formData.append('color', color);
    formData.append('description', description);

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');

            // Modal schließen
            const modalElement = document.getElementById('listModal');
            const modal = bootstrap.Modal.getInstance(modalElement);
            modal.hide();

            // Bei Edit: Seite neu laden
            // Bei Create: Zur neuen Liste navigieren
            if (isEdit) {
                setTimeout(() => location.reload(), 800);
            } else {
                setTimeout(() => {
                    window.location.href = data.list_url;
                }, 800);
            }
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Fehler beim Speichern', 'danger');
    }
}

// Liste löschen
async function deleteList(listId, listName, keywordCount) {
    const confirmMessage = keywordCount > 0
        ? `Möchtest du die Liste "${listName}" wirklich löschen?\n\n⚠️ Alle ${keywordCount} Keywords werden ebenfalls gelöscht!`
        : `Möchtest du die Liste "${listName}" wirklich löschen?`;

    if (!confirm(confirmMessage)) {
        return;
    }

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRFToken());

    try {
        const response = await fetch(`/keyengine/list/${listId}/delete/`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(() => {
                window.location.href = '/keyengine/lists/';
            }, 800);
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Fehler beim Löschen', 'danger');
    }
}

// Liste archivieren/wiederherstellen
async function archiveList(listId, listName) {
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRFToken());

    try {
        const response = await fetch(`/keyengine/list/${listId}/archive/`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Fehler beim Archivieren', 'danger');
    }
}

// Liste duplizieren
async function duplicateList(listId, listName) {
    if (!confirm(`Möchtest du die Liste "${listName}" duplizieren?`)) {
        return;
    }

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRFToken());

    try {
        const response = await fetch(`/keyengine/list/${listId}/duplicate/`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(() => {
                window.location.href = data.list_url;
            }, 1000);
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Fehler beim Duplizieren', 'danger');
    }
}

// Archivierte Listen ein-/ausblenden
function toggleArchived() {
    const container = document.getElementById('archived-lists-container');
    const chevron = document.getElementById('archived-chevron');

    if (container.classList.contains('show')) {
        container.classList.remove('show');
        chevron.classList.remove('fa-chevron-up');
        chevron.classList.add('fa-chevron-down');
    } else {
        container.classList.add('show');
        chevron.classList.remove('fa-chevron-down');
        chevron.classList.add('fa-chevron-up');
    }
}

// ==================== Keyword-Verwaltung ====================

// Keyword verschieben
async function moveKeyword(keywordId, targetListId) {
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCSRFToken());
    formData.append('target_list_id', targetListId);

    try {
        const response = await fetch(`/keyengine/keyword/${keywordId}/move/`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');

            // Keyword-Item entfernen
            const keywordItem = document.querySelector(`[data-id="${keywordId}"]`);
            if (keywordItem) {
                keywordItem.style.transition = 'opacity 0.3s';
                keywordItem.style.opacity = '0';
                setTimeout(() => {
                    keywordItem.remove();
                    // Prüfe ob Liste leer ist
                    if (document.querySelectorAll('.keyword-item').length === 0) {
                        location.reload();
                    }
                }, 300);
            }
        } else {
            showToast(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Fehler beim Verschieben', 'danger');
    }
}
