/**
 * ImageForge JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initModeSelector();
    initProductUpload();
    initMultiUpload();
    initGenerateForm();
    initModelHints();
    initTextEmbedding();
});

/**
 * Text Embedding Options - Toggle basierend auf Text-Eingabe
 */
function initTextEmbedding() {
    const overlayTextInput = document.getElementById('overlay-text');
    const textOptions = document.getElementById('text-options');
    const textBgEnabled = document.getElementById('text-bg-enabled');
    const creativeShapesOption = document.getElementById('creative-shapes-option');

    if (!overlayTextInput || !textOptions) return;

    // Text-Optionen ein-/ausblenden basierend auf Text-Eingabe
    function updateTextOptionsVisibility() {
        const hasText = overlayTextInput.value.trim().length > 0;
        textOptions.style.display = hasText ? 'block' : 'none';

        // Kreative Formen nur anzeigen wenn Text-Hintergrund aktiviert
        if (creativeShapesOption && textBgEnabled) {
            creativeShapesOption.style.display = textBgEnabled.checked ? 'block' : 'none';
        }
    }

    // Event Listener
    overlayTextInput.addEventListener('input', updateTextOptionsVisibility);

    if (textBgEnabled) {
        textBgEnabled.addEventListener('change', function() {
            if (creativeShapesOption) {
                creativeShapesOption.style.display = this.checked ? 'block' : 'none';

                // Wenn Text-Hintergrund deaktiviert, auch kreative Formen deaktivieren
                if (!this.checked) {
                    const creativeCheckbox = document.getElementById('text-bg-creative');
                    if (creativeCheckbox) creativeCheckbox.checked = false;
                }
            }
        });
    }

    // Initial state setzen
    updateTextOptionsVisibility();
}

/**
 * Model Hints - Zeigt Tipps basierend auf gewähltem Modell
 */
function initModelHints() {
    const modelSelect = document.getElementById('ai-model-select');
    const hintText = document.getElementById('model-hint-text');

    if (!modelSelect || !hintText) return;

    const hints = {
        // Nano Banana
        'gemini-2.5-flash-image': 'Schnell, guter Text in Bildern, bis 14 Referenzbilder. Ideal für Produktfotos & Social Media.',
        'gemini-3-pro-image-preview': 'Profi-Qualität bis 4K, perfekter Text, komplexe Kompositionen. Ideal für Print & Marketing.',
        // Imagen 4
        'imagen-4.0-ultra-generate-001': 'Höchste Bildqualität, fotorealistisch. Ideal für hochwertige Werbung & Kataloge.',
        'imagen-4.0-generate-001': 'Ausgewogene Qualität & Geschwindigkeit. Guter Allrounder für die meisten Anwendungen.',
        'imagen-4.0-fast-generate-001': 'Schnelle Generierung, gute Qualität. Ideal für Previews & schnelle Iterationen.',
        // Imagen 3
        'imagen-3.0-generate-002': 'Bewährtes Modell, stabil und zuverlässig. Gut für konsistente Ergebnisse.',
        // OpenAI
        'gpt-image-1': 'GPT-4o basiert, bis 4K, transparente Hintergründe, perfekter Text. Bestes OpenAI-Modell!',
        'dall-e-3': 'Kreativ & künstlerisch, gute Prompt-Interpretation. Ideal für Illustrationen & kreative Konzepte.',
        'dall-e-2': 'Schnell & günstig, einfache Generierung. Gut für schnelle Entwürfe & Variationen.'
    };

    modelSelect.addEventListener('change', function() {
        const hint = hints[this.value] || 'Wähle ein Modell für mehr Infos.';
        hintText.textContent = hint;
    });
}

/**
 * Mode Selector
 */
function initModeSelector() {
    const modeOptions = document.querySelectorAll('.mode-option');
    const modeInput = document.getElementById('generation-mode');
    const productSection = document.querySelector('.product-upload-section');
    const characterSection = document.querySelector('.character-section');

    if (!modeOptions.length) return;

    modeOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Update active state
            modeOptions.forEach(o => o.classList.remove('active'));
            this.classList.add('active');

            // Update hidden input
            const mode = this.dataset.mode;
            if (modeInput) modeInput.value = mode;

            // Show/hide sections based on mode
            if (productSection) {
                productSection.style.display =
                    (mode === 'product' || mode === 'character_product') ? 'block' : 'none';
            }

            if (characterSection) {
                characterSection.style.display =
                    (mode === 'character' || mode === 'character_product') ? 'block' : 'none';
            }
        });
    });
}

/**
 * Single Product Upload
 */
function initProductUpload() {
    const uploadZone = document.getElementById('product-upload-zone');
    const fileInput = document.getElementById('product-image');

    if (!uploadZone || !fileInput) return;

    // Click to upload
    uploadZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleProductPreview(fileInput.files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleProductPreview(fileInput.files[0]);
        }
    });

    // Remove image
    const removeBtn = uploadZone.querySelector('.remove-image');
    if (removeBtn) {
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.value = '';
            const placeholder = uploadZone.querySelector('.upload-placeholder');
            const preview = uploadZone.querySelector('.upload-preview');
            if (placeholder) placeholder.classList.remove('d-none');
            if (preview) preview.classList.add('d-none');
        });
    }
}

function handleProductPreview(file) {
    const uploadZone = document.getElementById('product-upload-zone');
    const placeholder = uploadZone.querySelector('.upload-placeholder');
    const preview = uploadZone.querySelector('.upload-preview');
    const previewImg = preview.querySelector('img');

    if (!file.type.startsWith('image/')) {
        alert('Bitte nur Bilddateien hochladen');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        previewImg.src = e.target.result;
        placeholder.classList.add('d-none');
        preview.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
}

/**
 * Multi Upload for Characters
 */
function initMultiUpload() {
    const uploadZone = document.getElementById('multi-upload-zone');
    const fileInput = document.getElementById('character-images');
    const previewContainer = document.getElementById('image-previews');

    if (!uploadZone || !fileInput) return;

    let selectedFiles = [];

    // Click to upload
    uploadZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleMultiFiles(e.dataTransfer.files);
    });

    // File input change
    fileInput.addEventListener('change', () => {
        handleMultiFiles(fileInput.files);
    });

    function handleMultiFiles(files) {
        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/') && selectedFiles.length < 10) {
                selectedFiles.push(file);
                addPreview(file, selectedFiles.length - 1);
            }
        });

        // Update file input with DataTransfer
        const dt = new DataTransfer();
        selectedFiles.forEach(f => dt.items.add(f));
        fileInput.files = dt.files;
    }

    function addPreview(file, index) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const div = document.createElement('div');
            div.className = 'image-preview-item';
            div.dataset.index = index;
            div.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <button type="button" class="remove-btn" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            `;
            previewContainer.appendChild(div);

            // Remove handler
            div.querySelector('.remove-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                removeFile(index);
            });
        };
        reader.readAsDataURL(file);
    }

    function removeFile(index) {
        selectedFiles = selectedFiles.filter((_, i) => i !== index);

        // Rebuild file input
        const dt = new DataTransfer();
        selectedFiles.forEach(f => dt.items.add(f));
        fileInput.files = dt.files;

        // Rebuild previews
        previewContainer.innerHTML = '';
        selectedFiles.forEach((file, i) => addPreview(file, i));
    }
}

/**
 * Generate Form Handler
 */
function initGenerateForm() {
    const form = document.getElementById('generate-form');
    const generateBtn = document.getElementById('generate-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resultModal = document.getElementById('result-modal');

    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Show loading
        if (loadingOverlay) loadingOverlay.classList.remove('d-none');
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generiere...';
        }

        try {
            const formData = new FormData(form);
            const response = await fetch(form.action || '/imageforge/generate/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await response.json();

            if (data.success) {
                // Show result in modal
                if (resultModal) {
                    const resultImage = document.getElementById('result-image');
                    const resultInfo = document.getElementById('result-info');
                    const downloadBtn = document.getElementById('download-btn');
                    const viewDetailBtn = document.getElementById('view-detail-btn');

                    if (resultImage) resultImage.src = data.image_url;
                    if (resultInfo) resultInfo.textContent = `Generiert in ${data.generation_time}s`;
                    if (downloadBtn) downloadBtn.href = data.image_url;
                    if (viewDetailBtn) viewDetailBtn.href = `/imageforge/generation/${data.generation_id}/`;

                    const modal = new bootstrap.Modal(resultModal);
                    modal.show();
                }

                // Reset form
                form.reset();
                resetUploads();

            } else {
                alert('Fehler: ' + (data.error || 'Unbekannter Fehler'));
            }

        } catch (error) {
            console.error('Error:', error);
            alert('Netzwerkfehler. Bitte erneut versuchen.');
        } finally {
            // Hide loading
            if (loadingOverlay) loadingOverlay.classList.add('d-none');
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '<i class="fas fa-magic me-2"></i>Bild generieren';
            }
        }
    });
}

function resetUploads() {
    // Reset product upload
    const productUploadZone = document.getElementById('product-upload-zone');
    if (productUploadZone) {
        const placeholder = productUploadZone.querySelector('.upload-placeholder');
        const preview = productUploadZone.querySelector('.upload-preview');
        if (placeholder) placeholder.classList.remove('d-none');
        if (preview) preview.classList.add('d-none');
    }

    // Reset multi upload
    const previewContainer = document.getElementById('image-previews');
    if (previewContainer) previewContainer.innerHTML = '';

    // Reset mode
    const modeOptions = document.querySelectorAll('.mode-option');
    modeOptions.forEach((o, i) => {
        if (i === 0) o.classList.add('active');
        else o.classList.remove('active');
    });

    const modeInput = document.getElementById('generation-mode');
    if (modeInput) modeInput.value = 'background';

    // Hide conditional sections
    const productSection = document.querySelector('.product-upload-section');
    const characterSection = document.querySelector('.character-section');
    if (productSection) productSection.style.display = 'none';
    if (characterSection) characterSection.style.display = 'none';
}
