/**
 * ImageForge JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('ImageForge JS loaded');
    // Initialize components
    initModeSelector();
    initProductUpload();
    initMultiUpload();
    initGenerateForm();
});

/**
 * Mode Selector
 */
function initModeSelector() {
    const modeOptions = document.querySelectorAll('.mode-option');
    const modeInput = document.getElementById('generation-mode');
    const productSection = document.querySelector('.product-upload-section');
    const characterSection = document.querySelector('.character-section');

    console.log('Mode options found:', modeOptions.length);
    if (!modeOptions.length) {
        console.log('No mode options found, exiting');
        return;
    }

    modeOptions.forEach(option => {
        option.addEventListener('click', function() {
            console.log('Mode clicked:', this.dataset.mode);
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
