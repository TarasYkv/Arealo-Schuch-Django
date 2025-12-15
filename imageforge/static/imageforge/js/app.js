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
    initMockupWizard();
});

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
    const mockupWizardSection = document.querySelector('.mockup-wizard-section');
    const standardFormSections = document.querySelectorAll('.standard-form-section');

    if (!modeOptions.length) return;

    // Funktion zum Aktivieren eines Modus
    function activateMode(mode) {
        // Update active state auf dem Button
        modeOptions.forEach(o => {
            if (o.dataset.mode === mode) {
                o.classList.add('active');
            } else {
                o.classList.remove('active');
            }
        });

        // Update hidden input
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

        // Mockup-Text Modus: Wizard anzeigen, Standard-Formular verstecken
        if (mockupWizardSection) {
            mockupWizardSection.style.display = (mode === 'mockup_text') ? 'block' : 'none';
        }

        // Standard-Formular-Elemente bei mockup_text verstecken
        standardFormSections.forEach(section => {
            section.style.display = (mode === 'mockup_text') ? 'none' : '';
        });
    }

    // Click-Handler für Mode-Buttons
    modeOptions.forEach(option => {
        option.addEventListener('click', function() {
            activateMode(this.dataset.mode);
        });
    });

    // URL-Parameter prüfen und Modus beim Laden aktivieren
    const urlParams = new URLSearchParams(window.location.search);
    const urlMode = urlParams.get('mode');
    if (urlMode) {
        activateMode(urlMode);
    }
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
    const mockupWizardSection = document.querySelector('.mockup-wizard-section');
    if (productSection) productSection.style.display = 'none';
    if (characterSection) characterSection.style.display = 'none';
    if (mockupWizardSection) mockupWizardSection.style.display = 'none';

    // Show standard form sections
    const standardFormSections = document.querySelectorAll('.standard-form-section');
    standardFormSections.forEach(section => section.style.display = '');
}

/**
 * Mockup Wizard - 2-Step Workflow für Produkt-Mockups mit Text
 */
function initMockupWizard() {
    const mockupProductZone = document.getElementById('mockup-product-upload-zone');
    const mockupProductInput = document.getElementById('mockup-product-image');
    const styleRefZone = document.getElementById('mockup-style-ref-zone');
    const styleRefInput = document.getElementById('style-reference-image');
    const generateMockupBtn = document.getElementById('generate-mockup-btn');
    const savedMockupSelect = document.getElementById('saved-mockup-select');
    const step2Card = document.getElementById('mockup-step2-card');
    const previewCard = document.getElementById('mockup-preview-card');
    const previewImage = document.getElementById('mockup-preview-image');
    const currentMockupIdInput = document.getElementById('current-mockup-id');
    const loadingOverlay = document.getElementById('loading-overlay');
    const resultModal = document.getElementById('result-modal');

    // Initialize mockup product upload zone
    if (mockupProductZone && mockupProductInput) {
        initUploadZone(mockupProductZone, mockupProductInput);
    }

    // Initialize style reference upload zone
    if (styleRefZone && styleRefInput) {
        initUploadZone(styleRefZone, styleRefInput);
    }

    // Saved Mockup Dropdown
    if (savedMockupSelect) {
        savedMockupSelect.addEventListener('change', function() {
            const mockupId = this.value;
            if (mockupId) {
                // Use saved mockup - skip to step 2
                const selectedOption = this.options[this.selectedIndex];
                const imageUrl = selectedOption.dataset.image;
                activateStep2(mockupId, imageUrl);
            } else {
                // Create new mockup - reset to step 1
                deactivateStep2();
            }
        });
    }

    // Generate Mockup Button (Step 1)
    if (generateMockupBtn) {
        generateMockupBtn.addEventListener('click', async function() {
            const textContent = document.getElementById('mockup-text-content')?.value?.trim();
            const productFile = mockupProductInput?.files?.[0];

            if (!textContent) {
                alert('Bitte gib einen Text ein.');
                return;
            }
            if (!productFile) {
                alert('Bitte lade ein Produktbild hoch.');
                return;
            }

            // Show loading
            if (loadingOverlay) loadingOverlay.classList.remove('d-none');
            generateMockupBtn.disabled = true;
            generateMockupBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Mockup wird generiert...';

            try {
                const formData = new FormData();
                formData.append('text_content', textContent);
                formData.append('text_application_type', document.querySelector('input[name="text_application_type"]:checked')?.value || 'druck');
                formData.append('text_position', document.getElementById('mockup-text-position')?.value || 'center');
                formData.append('font_style', document.getElementById('mockup-font-style')?.value || 'modern');
                formData.append('text_color_hint', document.getElementById('mockup-text-color')?.value || '');
                formData.append('text_size_hint', document.getElementById('mockup-text-size')?.value || 'medium');
                formData.append('product_image', productFile);

                // Style reference image (optional)
                const styleRefFile = styleRefInput?.files?.[0];
                if (styleRefFile) {
                    formData.append('style_reference_image', styleRefFile);
                }

                // CSRF Token
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

                const response = await fetch('/imageforge/generate/mockup/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                });

                const data = await response.json();

                if (data.success) {
                    // Show mockup preview and activate step 2
                    activateStep2(data.mockup_id, data.mockup_image_url);
                    alert(`Mockup erfolgreich erstellt! (${data.generation_time}s)`);
                } else {
                    alert('Fehler: ' + (data.error || 'Unbekannter Fehler'));
                }

            } catch (error) {
                console.error('Error:', error);
                alert('Netzwerkfehler. Bitte erneut versuchen.');
            } finally {
                if (loadingOverlay) loadingOverlay.classList.add('d-none');
                generateMockupBtn.disabled = false;
                generateMockupBtn.innerHTML = '<i class="fas fa-magic me-2"></i>Mockup generieren';
            }
        });
    }

    // Helper: Activate Step 2
    function activateStep2(mockupId, imageUrl) {
        if (currentMockupIdInput) currentMockupIdInput.value = mockupId;
        if (previewImage) previewImage.src = imageUrl;
        if (previewCard) previewCard.classList.remove('d-none');
        if (step2Card) {
            step2Card.style.opacity = '1';
            step2Card.style.pointerEvents = 'auto';
            step2Card.querySelector('.card-header').classList.remove('bg-secondary');
            step2Card.querySelector('.card-header').classList.add('bg-primary');

            // Replace hint with scene form
            const step2Body = step2Card.querySelector('.card-body');
            step2Body.innerHTML = `
                <div class="mb-3">
                    <label class="form-label fw-bold">Szenen-/Hintergrund-Beschreibung *</label>
                    <textarea id="mockup-scene-prompt" class="form-control" rows="3"
                              placeholder="z.B. Eleganter Holztisch mit warmem Licht, Kaffeebohnen im Hintergrund"></textarea>
                </div>
                <div class="row mb-3">
                    <div class="col-md-4">
                        <label class="form-label">Format</label>
                        <select id="mockup-aspect-ratio" class="form-select form-select-sm">
                            <option value="1:1" selected>Square (1:1)</option>
                            <option value="4:3">Standard (4:3)</option>
                            <option value="16:9">Widescreen (16:9)</option>
                            <option value="9:16">Portrait (9:16)</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Lichtstil</label>
                        <select id="mockup-lighting" class="form-select form-select-sm">
                            <option value="natural" selected>Natürlich</option>
                            <option value="studio">Studio</option>
                            <option value="dramatic">Dramatisch</option>
                            <option value="golden_hour">Golden Hour</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Stil</label>
                        <select id="mockup-style" class="form-select form-select-sm">
                            <option value="lifestyle" selected>Lifestyle</option>
                            <option value="ecommerce">E-Commerce</option>
                            <option value="minimal">Minimalistisch</option>
                            <option value="luxury">Luxus</option>
                        </select>
                    </div>
                </div>
                <button type="button" class="btn btn-success w-100" id="generate-scene-btn">
                    <i class="fas fa-image me-2"></i>In Szene generieren
                </button>
            `;

            // Add event listener for scene generation
            const generateSceneBtn = document.getElementById('generate-scene-btn');
            if (generateSceneBtn) {
                generateSceneBtn.addEventListener('click', generateMockupScene);
            }
        }
    }

    // Helper: Deactivate Step 2
    function deactivateStep2() {
        if (currentMockupIdInput) currentMockupIdInput.value = '';
        if (previewCard) previewCard.classList.add('d-none');
        if (step2Card) {
            step2Card.style.opacity = '0.5';
            step2Card.style.pointerEvents = 'none';
            step2Card.querySelector('.card-header').classList.add('bg-secondary');
            step2Card.querySelector('.card-header').classList.remove('bg-primary');
            step2Card.querySelector('.card-body').innerHTML = `
                <div class="alert alert-info mb-3" id="step2-hint">
                    <i class="fas fa-info-circle me-2"></i>
                    Erst Mockup erstellen (Step 1) oder gespeichertes Mockup wählen.
                </div>
            `;
        }
    }

    // Generate Mockup Scene (Step 2)
    async function generateMockupScene() {
        const mockupId = currentMockupIdInput?.value;
        const scenePrompt = document.getElementById('mockup-scene-prompt')?.value?.trim();

        if (!mockupId) {
            alert('Kein Mockup ausgewählt.');
            return;
        }
        if (!scenePrompt) {
            alert('Bitte gib eine Szenen-Beschreibung ein.');
            return;
        }

        const generateSceneBtn = document.getElementById('generate-scene-btn');
        if (loadingOverlay) loadingOverlay.classList.remove('d-none');
        if (generateSceneBtn) {
            generateSceneBtn.disabled = true;
            generateSceneBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Szene wird generiert...';
        }

        try {
            const formData = new FormData();
            formData.append('mockup_id', mockupId);
            formData.append('background_prompt', scenePrompt);
            formData.append('aspect_ratio', document.getElementById('mockup-aspect-ratio')?.value || '1:1');
            formData.append('lighting_style', document.getElementById('mockup-lighting')?.value || 'natural');
            formData.append('style_preset', document.getElementById('mockup-style')?.value || 'lifestyle');

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            const response = await fetch('/imageforge/generate/mockup-scene/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
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
            } else {
                alert('Fehler: ' + (data.error || 'Unbekannter Fehler'));
            }

        } catch (error) {
            console.error('Error:', error);
            alert('Netzwerkfehler. Bitte erneut versuchen.');
        } finally {
            if (loadingOverlay) loadingOverlay.classList.add('d-none');
            if (generateSceneBtn) {
                generateSceneBtn.disabled = false;
                generateSceneBtn.innerHTML = '<i class="fas fa-image me-2"></i>In Szene generieren';
            }
        }
    }
}

/**
 * Generic Upload Zone Initializer
 */
function initUploadZone(zone, input) {
    // Click to upload
    zone.addEventListener('click', (e) => {
        if (!e.target.closest('.remove-image')) {
            input.click();
        }
    });

    // Drag and drop
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            handleUploadPreview(zone, input.files[0]);
        }
    });

    // File input change
    input.addEventListener('change', () => {
        if (input.files.length) {
            handleUploadPreview(zone, input.files[0]);
        }
    });

    // Remove image
    const removeBtn = zone.querySelector('.remove-image');
    if (removeBtn) {
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            input.value = '';
            const placeholder = zone.querySelector('.upload-placeholder');
            const preview = zone.querySelector('.upload-preview');
            if (placeholder) placeholder.classList.remove('d-none');
            if (preview) preview.classList.add('d-none');
        });
    }
}

function handleUploadPreview(zone, file) {
    const placeholder = zone.querySelector('.upload-placeholder');
    const preview = zone.querySelector('.upload-preview');
    const previewImg = preview?.querySelector('img');

    if (!file.type.startsWith('image/')) {
        alert('Bitte nur Bilddateien hochladen');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        if (previewImg) previewImg.src = e.target.result;
        if (placeholder) placeholder.classList.add('d-none');
        if (preview) preview.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
}
