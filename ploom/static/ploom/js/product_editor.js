/**
 * P-Loom Product Editor JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Character counters
    initCharCounters();

    // AI Generation
    initAIGeneration();

    // History modals
    initHistory();

    // Image handling
    initImageHandling();

    // Variants
    initVariants();

    // Collections
    initCollections();

    // Shopify upload
    initShopifyUpload();

    // SEO Preview
    initSEOPreview();
});

// ============================================================================
// Character Counters
// ============================================================================

function initCharCounters() {
    const titleField = document.getElementById('id_title');
    const seoTitleField = document.getElementById('id_seo_title');
    const seoDescField = document.getElementById('id_seo_description');

    if (titleField) {
        titleField.addEventListener('input', function() {
            updateCounter(this, 'title-count', 70);
        });
        updateCounter(titleField, 'title-count', 70);
    }

    if (seoTitleField) {
        seoTitleField.addEventListener('input', function() {
            updateCounter(this, 'seo-title-count', 70);
            updateSEOPreview();
        });
        updateCounter(seoTitleField, 'seo-title-count', 70);
    }

    if (seoDescField) {
        seoDescField.addEventListener('input', function() {
            updateCounter(this, 'seo-desc-count', 160);
            updateSEOPreview();
        });
        updateCounter(seoDescField, 'seo-desc-count', 160);
    }
}

function updateCounter(field, counterId, max) {
    const counter = document.getElementById(counterId);
    if (!counter) return;

    const length = field.value.length;
    counter.textContent = length;

    counter.classList.remove('char-counter-warning', 'char-counter-danger');
    if (length > max) {
        counter.classList.add('char-counter-danger');
    } else if (length > max * 0.9) {
        counter.classList.add('char-counter-warning');
    }
}

// ============================================================================
// AI Generation
// ============================================================================

function initAIGeneration() {
    document.querySelectorAll('.btn-ai-generate').forEach(btn => {
        btn.addEventListener('click', function() {
            const field = this.dataset.field;
            const target = this.dataset.target;
            generateAIContent(field, target, this);
        });
    });

    // SEO generation button
    const seoBtn = document.getElementById('btn-generate-seo');
    if (seoBtn) {
        seoBtn.addEventListener('click', generateSEO);
    }
}

async function generateAIContent(field, targetId, btn) {
    const title = document.getElementById('id_title')?.value || '';
    if (!title) {
        alert('Bitte gib zuerst einen Produkttitel ein');
        return;
    }

    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span>';
    btn.disabled = true;

    try {
        let endpoint = '';
        let body = { product_name: title };

        switch (field) {
            case 'title':
                endpoint = '/ploom/api/generate/title/';
                break;
            case 'description':
                endpoint = '/ploom/api/generate/description/';
                body.tone = 'professional';
                break;
            case 'tags':
                endpoint = '/ploom/api/generate/tags/';
                body.description = document.getElementById('id_description')?.value || '';
                break;
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();
        if (data.success && data.content) {
            const target = document.getElementById(targetId);
            if (target) {
                target.value = data.content;
                target.dispatchEvent(new Event('input'));
            }
        } else {
            alert(data.error || 'Fehler bei der Generierung');
        }
    } catch (error) {
        console.error('AI Generation error:', error);
        alert('Fehler bei der Verbindung');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

async function generateSEO() {
    const btn = document.getElementById('btn-generate-seo');
    const title = document.getElementById('id_title')?.value || '';

    if (!title) {
        alert('Bitte gib zuerst einen Produkttitel ein');
        return;
    }

    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> Generiere...';
    btn.disabled = true;

    try {
        const response = await fetch('/ploom/api/generate/seo/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({
                product_name: title,
                description: document.getElementById('id_description')?.value || ''
            })
        });

        const data = await response.json();
        if (data.success && data.content) {
            if (data.content.seo_title) {
                document.getElementById('id_seo_title').value = data.content.seo_title;
                document.getElementById('id_seo_title').dispatchEvent(new Event('input'));
            }
            if (data.content.seo_description) {
                document.getElementById('id_seo_description').value = data.content.seo_description;
                document.getElementById('id_seo_description').dispatchEvent(new Event('input'));
            }
        } else {
            alert(data.error || 'Fehler bei der SEO-Generierung');
        }
    } catch (error) {
        console.error('SEO Generation error:', error);
        alert('Fehler bei der Verbindung');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

// ============================================================================
// History
// ============================================================================

let currentHistoryTarget = null;
let currentHistoryField = null;

function initHistory() {
    document.querySelectorAll('.btn-history').forEach(btn => {
        btn.addEventListener('click', function() {
            currentHistoryField = this.dataset.field;
            currentHistoryTarget = this.dataset.target;
            loadHistory(currentHistoryField);
            new bootstrap.Modal(document.getElementById('historyModal')).show();
        });
    });
}

async function loadHistory(field, page = 1) {
    const container = document.getElementById('history-items');
    container.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';

    try {
        let endpoint = `/ploom/api/history/${field}/?page=${page}`;
        if (field === 'prices') {
            endpoint = `/ploom/api/history/prices/?page=${page}`;
        }

        const response = await fetch(endpoint);
        const data = await response.json();

        if (data.success) {
            if (field === 'prices') {
                renderPriceHistory(data.items, container);
            } else {
                renderHistory(data.items, container);
            }
            renderPagination(data, field);
        } else {
            container.innerHTML = '<p class="text-muted text-center">Fehler beim Laden</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="text-muted text-center">Fehler beim Laden</p>';
    }
}

function renderHistory(items, container) {
    if (items.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">Kein Verlauf vorhanden</p>';
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="history-item" data-content="${escapeHtml(item.content)}">
            ${escapeHtml(item.content).substring(0, 150)}${item.content.length > 150 ? '...' : ''}
        </div>
    `).join('');

    container.querySelectorAll('.history-item').forEach(el => {
        el.addEventListener('click', function() {
            const content = this.dataset.content;
            const target = document.getElementById(currentHistoryTarget);
            if (target) {
                target.value = content;
                target.dispatchEvent(new Event('input'));
            }
            bootstrap.Modal.getInstance(document.getElementById('historyModal')).hide();
        });
    });
}

function renderPriceHistory(items, container) {
    if (items.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">Kein Preisverlauf vorhanden</p>';
        return;
    }

    container.innerHTML = items.map(item => `
        <span class="price-item ${item.is_favorite ? 'favorite' : ''}" data-price="${item.price}">
            ${item.price} EUR
            ${item.label ? `<small class="text-muted">(${item.label})</small>` : ''}
        </span>
    `).join('');

    container.querySelectorAll('.price-item').forEach(el => {
        el.addEventListener('click', function() {
            const price = this.dataset.price;
            const target = document.getElementById(currentHistoryTarget);
            if (target) {
                target.value = price;
            }
            bootstrap.Modal.getInstance(document.getElementById('historyModal')).hide();
        });
    });
}

function renderPagination(data, field) {
    const container = document.getElementById('history-pagination');
    if (!data.has_prev && !data.has_next) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = `
        <button class="btn btn-sm btn-outline-secondary" ${!data.has_prev ? 'disabled' : ''}
                onclick="loadHistory('${field}', ${data.page - 1})">
            <i class="bi bi-chevron-left"></i> Zurück
        </button>
        <span class="text-muted">Seite ${data.page}</span>
        <button class="btn btn-sm btn-outline-secondary" ${!data.has_next ? 'disabled' : ''}
                onclick="loadHistory('${field}', ${data.page + 1})">
            Weiter <i class="bi bi-chevron-right"></i>
        </button>
    `;
}

// ============================================================================
// Image Handling
// ============================================================================

function initImageHandling() {
    // File upload
    const uploadInput = document.getElementById('image-upload');
    if (uploadInput) {
        uploadInput.addEventListener('change', handleImageUpload);
    }

    // ImageForge modal
    const modal = document.getElementById('imageforgeModal');
    if (modal) {
        modal.addEventListener('shown.bs.modal', loadImageForgeContent);
    }

    // Delete image buttons
    document.querySelectorAll('.btn-delete-image').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            deleteImage(this.dataset.id);
        });
    });

    // Set featured buttons
    document.querySelectorAll('.btn-set-featured').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            setFeaturedImage(this.dataset.id);
        });
    });

    // Assign variant buttons
    document.querySelectorAll('.btn-assign-variant').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            openVariantImageModal(this.dataset.id, this.dataset.variant || '');
        });
    });

    // Save variant assignment button
    const saveVariantImageBtn = document.getElementById('btn-save-variant-image');
    if (saveVariantImageBtn) {
        saveVariantImageBtn.addEventListener('click', saveVariantImageAssignment);
    }
}

function openVariantImageModal(imageId, currentVariantId) {
    document.getElementById('variant-image-id').value = imageId;
    document.getElementById('variant-image-select').value = currentVariantId;
    new bootstrap.Modal(document.getElementById('variantImageModal')).show();
}

async function saveVariantImageAssignment() {
    const imageId = document.getElementById('variant-image-id').value;
    const variantId = document.getElementById('variant-image-select').value;

    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/images/${imageId}/set-variant/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ variant_id: variantId })
        });

        const data = await response.json();
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('variantImageModal')).hide();
            location.reload();
        } else {
            alert(data.error || 'Fehler beim Zuweisen');
        }
    } catch (error) {
        alert('Fehler beim Zuweisen');
    }
}

async function handleImageUpload(e) {
    if (!PRODUCT_ID) {
        alert('Bitte speichere das Produkt zuerst');
        return;
    }

    const files = e.target.files;
    for (const file of files) {
        const formData = new FormData();
        formData.append('image', file);

        try {
            const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/images/upload/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': CSRF_TOKEN },
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                location.reload();
            } else {
                alert(data.error || 'Fehler beim Upload');
            }
        } catch (error) {
            alert('Fehler beim Upload');
        }
    }
}

async function loadImageForgeContent() {
    // Load generations
    const genContainer = document.getElementById('imageforge-generations');
    try {
        const response = await fetch('/ploom/api/imageforge/generations/');
        const data = await response.json();
        if (data.success) {
            renderImageForgeItems(data.items, genContainer, 'generation');
        } else {
            genContainer.innerHTML = '<p class="text-muted text-center col-12">Keine Bilder gefunden</p>';
        }
    } catch (error) {
        genContainer.innerHTML = '<p class="text-danger text-center col-12">Fehler beim Laden</p>';
    }

    // Load mockups
    const mockContainer = document.getElementById('imageforge-mockups');
    try {
        const response = await fetch('/ploom/api/imageforge/mockups/');
        const data = await response.json();
        if (data.success) {
            renderImageForgeItems(data.items, mockContainer, 'mockup');
        } else {
            mockContainer.innerHTML = '<p class="text-muted text-center col-12">Keine Mockups gefunden</p>';
        }
    } catch (error) {
        mockContainer.innerHTML = '<p class="text-danger text-center col-12">Fehler beim Laden</p>';
    }
}

function renderImageForgeItems(items, container, type) {
    if (items.length === 0) {
        container.innerHTML = '<p class="text-muted text-center col-12">Keine Bilder vorhanden</p>';
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="col-4 mb-2">
            <img src="${item.url}" data-id="${item.id}" data-type="${type}"
                 title="${item.prompt || item.name || ''}"
                 onclick="addImageFromImageForge(this)">
        </div>
    `).join('');
}

async function addImageFromImageForge(img) {
    if (!PRODUCT_ID) {
        alert('Bitte speichere das Produkt zuerst');
        return;
    }

    const sourceType = img.dataset.type;
    const sourceId = img.dataset.id;

    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/images/from-imageforge/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({
                source_type: sourceType,
                source_id: sourceId
            })
        });

        const data = await response.json();
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('imageforgeModal')).hide();
            location.reload();
        } else {
            alert(data.error || 'Fehler beim Hinzufügen');
        }
    } catch (error) {
        alert('Fehler beim Hinzufügen');
    }
}

async function deleteImage(imageId) {
    if (!confirm('Bild wirklich löschen?')) return;

    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/images/${imageId}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN }
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || 'Fehler beim Löschen');
        }
    } catch (error) {
        alert('Fehler beim Löschen');
    }
}

async function setFeaturedImage(imageId) {
    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/images/${imageId}/set-featured/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN }
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        }
    } catch (error) {
        console.error('Error setting featured image:', error);
    }
}

// ============================================================================
// Variants
// ============================================================================

function initVariants() {
    const addBtn = document.getElementById('btn-add-variant');
    if (addBtn) {
        addBtn.addEventListener('click', () => openVariantModal());
    }

    document.querySelectorAll('.btn-edit-variant').forEach(btn => {
        btn.addEventListener('click', async function(e) {
            e.stopPropagation();
            const variantId = this.dataset.id;
            await loadAndEditVariant(variantId);
        });
    });

    document.querySelectorAll('.btn-delete-variant').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            deleteVariant(this.dataset.id);
        });
    });

    const saveBtn = document.getElementById('btn-save-variant');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveVariant);
    }
}

function openVariantModal(variantId = null) {
    // Reset form
    document.getElementById('variant-id').value = variantId || '';
    document.getElementById('variant-option1-name').value = '';
    document.getElementById('variant-option1-value').value = '';
    document.getElementById('variant-option2-name').value = '';
    document.getElementById('variant-option2-value').value = '';
    document.getElementById('variant-sku').value = '';
    document.getElementById('variant-price').value = '';
    document.getElementById('variant-quantity').value = '0';
    document.getElementById('variant-barcode').value = '';

    new bootstrap.Modal(document.getElementById('variantModal')).show();
}

async function loadAndEditVariant(variantId) {
    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/variants/${variantId}/`);
        const data = await response.json();

        if (data.success && data.variant) {
            const v = data.variant;
            document.getElementById('variant-id').value = v.id;
            document.getElementById('variant-option1-name').value = v.option1_name || '';
            document.getElementById('variant-option1-value').value = v.option1_value || '';
            document.getElementById('variant-option2-name').value = v.option2_name || '';
            document.getElementById('variant-option2-value').value = v.option2_value || '';
            document.getElementById('variant-sku').value = v.sku || '';
            document.getElementById('variant-price').value = v.price || '';
            document.getElementById('variant-quantity').value = v.inventory_quantity || 0;
            document.getElementById('variant-barcode').value = v.barcode || '';

            new bootstrap.Modal(document.getElementById('variantModal')).show();
        } else {
            alert(data.error || 'Fehler beim Laden der Variante');
        }
    } catch (error) {
        console.error('Error loading variant:', error);
        alert('Fehler beim Laden der Variante');
    }
}

async function saveVariant() {
    if (!PRODUCT_ID) {
        alert('Bitte speichere das Produkt zuerst');
        return;
    }

    const variantId = document.getElementById('variant-id').value;
    const data = {
        option1_name: document.getElementById('variant-option1-name').value,
        option1_value: document.getElementById('variant-option1-value').value,
        option2_name: document.getElementById('variant-option2-name').value,
        option2_value: document.getElementById('variant-option2-value').value,
        sku: document.getElementById('variant-sku').value,
        price: document.getElementById('variant-price').value || null,
        inventory_quantity: parseInt(document.getElementById('variant-quantity').value) || 0,
        barcode: document.getElementById('variant-barcode').value
    };

    const endpoint = variantId
        ? `/ploom/api/products/${PRODUCT_ID}/variants/${variantId}/update/`
        : `/ploom/api/products/${PRODUCT_ID}/variants/add/`;

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (result.success) {
            bootstrap.Modal.getInstance(document.getElementById('variantModal')).hide();
            location.reload();
        } else {
            alert(result.error || 'Fehler beim Speichern');
        }
    } catch (error) {
        alert('Fehler beim Speichern');
    }
}

async function deleteVariant(variantId) {
    if (!confirm('Variante wirklich löschen?')) return;

    try {
        const response = await fetch(`/ploom/api/products/${PRODUCT_ID}/variants/${variantId}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN }
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        }
    } catch (error) {
        alert('Fehler beim Löschen');
    }
}

// ============================================================================
// Collections
// ============================================================================

function initCollections() {
    const btn = document.getElementById('btn-select-collection');
    if (btn) {
        btn.addEventListener('click', loadCollections);
    }
}

async function loadCollections() {
    const modal = new bootstrap.Modal(document.getElementById('collectionModal'));
    modal.show();

    const container = document.getElementById('collections-list');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';

    const storeSelect = document.getElementById('id_shopify_store');
    const storeId = storeSelect ? storeSelect.value : '';

    try {
        const response = await fetch(`/ploom/api/shopify/collections/?store_id=${storeId}`);
        const data = await response.json();

        if (data.success) {
            if (data.collections.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">Keine Collections gefunden</p>';
            } else {
                container.innerHTML = data.collections.map(col => `
                    <div class="collection-item" data-id="${col.id}" data-title="${escapeHtml(col.title)}">
                        ${escapeHtml(col.title)}
                        <small class="text-muted">(${col.type})</small>
                    </div>
                `).join('');

                container.querySelectorAll('.collection-item').forEach(el => {
                    el.addEventListener('click', function() {
                        document.getElementById('id_collection_id').value = this.dataset.id;
                        document.getElementById('collection-display').value = this.dataset.title;
                        modal.hide();
                    });
                });
            }
        } else {
            container.innerHTML = `<p class="text-danger text-center">${data.error || 'Fehler beim Laden'}</p>`;
        }
    } catch (error) {
        container.innerHTML = '<p class="text-danger text-center">Fehler beim Laden</p>';
    }
}

// ============================================================================
// Shopify Upload
// ============================================================================

function initShopifyUpload() {
    const btn = document.getElementById('btn-upload-shopify');
    if (btn) {
        btn.addEventListener('click', uploadToShopify);
    }
}

async function uploadToShopify() {
    if (!PRODUCT_ID) return;

    const btn = document.getElementById('btn-upload-shopify');
    if (!confirm('Produkt als Entwurf zu Shopify hochladen?')) return;

    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> Hochladen...';
    btn.disabled = true;

    try {
        const response = await fetch(`/ploom/api/shopify/upload/${PRODUCT_ID}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF_TOKEN }
        });

        const data = await response.json();
        if (data.success) {
            alert(data.message || 'Produkt erfolgreich hochgeladen!');
            location.reload();
        } else {
            alert(data.error || 'Fehler beim Upload');
        }
    } catch (error) {
        alert('Fehler beim Upload');
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

// ============================================================================
// SEO Preview
// ============================================================================

function initSEOPreview() {
    updateSEOPreview();
}

function updateSEOPreview() {
    const title = document.getElementById('id_seo_title')?.value ||
                  document.getElementById('id_title')?.value ||
                  'Titel hier...';
    const desc = document.getElementById('id_seo_description')?.value || 'Beschreibung hier...';

    document.getElementById('seo-preview-title').textContent = title;
    document.getElementById('seo-preview-desc').textContent = desc;
}

// ============================================================================
// Utilities
// ============================================================================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
