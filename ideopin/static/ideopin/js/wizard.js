/**
 * IdeoPin Wizard JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Auto-resize textareas
    document.querySelectorAll('textarea').forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 300) + 'px';
        });
    });
});

/**
 * Copy text to clipboard with visual feedback
 * @param {string} elementId - ID of the element containing text to copy
 */
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const text = element.value || element.textContent || element.innerText;

    navigator.clipboard.writeText(text).then(() => {
        showToast('Erfolgreich kopiert!', 'success');
    }).catch(err => {
        console.error('Copy failed:', err);
        showToast('Kopieren fehlgeschlagen', 'error');
    });
}

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - 'success', 'error', 'info'
 */
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';

    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${type === 'success' ? '<i class="bi bi-check-circle me-2"></i>' : ''}
                    ${type === 'error' ? '<i class="bi bi-exclamation-circle me-2"></i>' : ''}
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();

    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

/**
 * AJAX helper for API calls
 * @param {string} url - API endpoint
 * @param {object} options - fetch options
 * @returns {Promise}
 */
async function apiCall(url, options = {}) {
    const defaultOptions = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        ...options
    };

    // Add CSRF token if available
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (csrfToken) {
        defaultOptions.headers['X-CSRFToken'] = csrfToken;
    }

    try {
        const response = await fetch(url, defaultOptions);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Update text preview with styling
 * @param {string} text - Text to preview
 * @param {object} styles - Style options
 */
function updateTextPreview(text, styles = {}) {
    const preview = document.getElementById('previewText');
    if (!preview) return;

    preview.textContent = text || 'Dein Text hier...';

    if (styles.color) {
        preview.style.color = styles.color;
    }
    if (styles.fontSize) {
        preview.style.fontSize = styles.fontSize + 'px';
    }
    if (styles.fontFamily) {
        preview.style.fontFamily = styles.fontFamily;
    }
}

/**
 * Handle form submission with loading state
 * @param {HTMLFormElement} form
 * @param {HTMLButtonElement} button
 */
function handleFormSubmit(form, button) {
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Wird verarbeitet...';

    // Form will submit normally, this is just for visual feedback
    setTimeout(() => {
        button.disabled = false;
        button.innerHTML = originalText;
    }, 10000); // Reset after 10 seconds if page hasn't redirected
}
