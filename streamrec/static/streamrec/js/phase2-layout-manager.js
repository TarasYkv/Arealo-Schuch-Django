/**
 * StreamRec Phase 2: Layout Management & Multi-Stream Handling
 * Advanced drag-and-drop layout system for multiple streams
 */

class LayoutManager {
    constructor(streamRecorder) {
        this.streamRecorder = streamRecorder;
        this.layouts = new Map();
        this.activeLayout = null;
        this.draggedElement = null;
        this.isDragging = false;
        this.isResizing = false;
        this.resizeHandle = null; // 'n','s','e','w','ne','nw','se','sw'
        this.handleSize = 10;
        this.minSize = 40;
        
        this.initializePresetLayouts();
        this.setupLayoutControls();
    }

    initializePresetLayouts() {
        // Preset 1: Picture-in-Picture (Screen + Camera overlay)
        this.layouts.set('pip-top-right', {
            id: 'pip-top-right',
            name: '2 Fenster · PiP (oben rechts)',
            description: 'Bildschirm als Hintergrund, Kamera oben rechts (2 Fenster)',
            streams: {
                screen: {
                    x: 0, y: 0,
                    width: 360, height: 640,
                    zIndex: 1,
                    aspectRatio: 'fill'
                },
                camera: {
                    x: 240, y: 20,
                    width: 100, height: 75,
                    zIndex: 2,
                    aspectRatio: 'contain'
                }
            }
        });

        // Preset 2: Side-by-Side
        this.layouts.set('side-by-side', {
            id: 'side-by-side',
            name: '2 Fenster · Nebeneinander (halb/halb)',
            description: 'Kamera und Bildschirm nebeneinander (2 Fenster)',
            streams: {
                camera: {
                    x: 0, y: 160,
                    width: 180, height: 320,
                    zIndex: 1,
                    aspectRatio: 'contain'
                },
                screen: {
                    x: 180, y: 160,
                    width: 180, height: 320,
                    zIndex: 1,
                    aspectRatio: 'contain'
                }
            }
        });

        // Preset 3: Split Screen (Top/Bottom)
        this.layouts.set('split-vertical', {
            id: 'split-vertical',
            name: '2 Fenster · Oben/Unten',
            description: 'Bildschirm oben, Kamera unten (2 Fenster)',
            streams: {
                screen: {
                    x: 0, y: 0,
                    width: 360, height: 320,
                    zIndex: 1,
                    aspectRatio: 'cover'
                },
                camera: {
                    x: 0, y: 320,
                    width: 360, height: 320,
                    zIndex: 1,
                    aspectRatio: 'cover'
                }
            }
        });

        // Preset 4: Full Screen Camera with Screen overlay
        this.layouts.set('camera-main', {
            id: 'camera-main',
            name: '2 Fenster · Kamera Hauptbild',
            description: 'Kamera als Hintergrund, Bildschirm als Overlay (2 Fenster)',
            streams: {
                camera: {
                    x: 0, y: 0,
                    width: 360, height: 640,
                    zIndex: 1,
                    aspectRatio: 'cover'
                },
                screen: {
                    x: 20, y: 20,
                    width: 120, height: 90,
                    zIndex: 2,
                    aspectRatio: 'cover'
                }
            }
        });

        // NEW: 2 Fenster · Vollhöhe nebeneinander
        this.layouts.set('two-side-full', {
            id: 'two-side-full',
            name: '2 Fenster · Nebeneinander (voll)',
            description: 'Beide Streams über volle Höhe nebeneinander (2 Fenster)',
            streams: {
                screen: { x: 0, y: 0, width: 180, height: 640, zIndex: 1, aspectRatio: 'contain' },
                camera: { x: 180, y: 0, width: 180, height: 640, zIndex: 1, aspectRatio: 'contain' }
            }
        });

        // NEW: 2 Fenster · PiP Varianten
        this.layouts.set('pip-top-left', {
            id: 'pip-top-left',
            name: '2 Fenster · PiP (oben links)',
            description: 'Bildschirm voll, Kamera oben links (2 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 360, height: 640, zIndex: 1, aspectRatio: 'fill' },
                camera:  { x: 20,  y: 20,  width: 100, height: 75,  zIndex: 2, aspectRatio: 'contain' }
            }
        });
        this.layouts.set('pip-bottom-left', {
            id: 'pip-bottom-left',
            name: '2 Fenster · PiP (unten links)',
            description: 'Bildschirm voll, Kamera unten links (2 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 360, height: 640, zIndex: 1, aspectRatio: 'fill' },
                camera:  { x: 20,  y: 545, width: 100, height: 75,  zIndex: 2, aspectRatio: 'contain' }
            }
        });
        this.layouts.set('pip-bottom-right', {
            id: 'pip-bottom-right',
            name: '2 Fenster · PiP (unten rechts)',
            description: 'Bildschirm voll, Kamera unten rechts (2 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 360, height: 640, zIndex: 1, aspectRatio: 'fill' },
                camera:  { x: 240, y: 545, width: 100, height: 75,  zIndex: 2, aspectRatio: 'contain' }
            }
        });

        // NEW: 2 Fenster · Goldener Schnitt (2/3 · 1/3) horizontal
        this.layouts.set('two-golden-left', {
            id: 'two-golden-left',
            name: '2 Fenster · 2/3 links, 1/3 rechts',
            description: 'Groß links, klein rechts (2 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0, width: 225, height: 640, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 225, y: 0, width: 135, height: 640, zIndex: 1, aspectRatio: 'contain' }
            }
        });
        this.layouts.set('two-golden-top', {
            id: 'two-golden-top',
            name: '2 Fenster · 2/3 oben, 1/3 unten',
            description: 'Groß oben, klein unten (2 Fenster)',
            streams: {
                screen:  { x: 0, y: 0,   width: 360, height: 426, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 0, y: 426, width: 360, height: 214, zIndex: 1, aspectRatio: 'contain' }
            }
        });

        // NEW: 3 Fenster · Oben groß, unten zwei
        this.layouts.set('three-top-2bottom', {
            id: 'three-top-2bottom',
            name: '3 Fenster · 1 oben, 2 unten',
            description: 'Oben groß, unten zwei kleinere (3 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 360, height: 360, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 0,   y: 360, width: 180, height: 280, zIndex: 2, aspectRatio: 'contain' },
                screen2: { x: 180, y: 360, width: 180, height: 280, zIndex: 2, aspectRatio: 'contain' }
            }
        });

        // NEW: 3 Fenster · Gleichmäßig gestapelt
        this.layouts.set('three-stacked', {
            id: 'three-stacked',
            name: '3 Fenster · Gestapelt',
            description: 'Drei Streams untereinander (3 Fenster)',
            streams: {
                screen:  { x: 0, y: 0,   width: 360, height: 213, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 0, y: 213, width: 360, height: 213, zIndex: 1, aspectRatio: 'contain' },
                screen2: { x: 0, y: 426, width: 360, height: 214, zIndex: 1, aspectRatio: 'contain' }
            }
        });

        // NEW: 3 Fenster · Links groß, rechts 2 gestapelt
        this.layouts.set('three-left-big', {
            id: 'three-left-big',
            name: '3 Fenster · Links groß, rechts 2',
            description: 'Links groß, rechts zwei gestapelt (3 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0, width: 240, height: 640, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 240, y: 0, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' },
                screen2: { x: 240, y: 320, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' }
            }
        });
        // NEW: 3 Fenster · Rechts groß, links 2 gestapelt
        this.layouts.set('three-right-big', {
            id: 'three-right-big',
            name: '3 Fenster · Rechts groß, links 2',
            description: 'Rechts groß, links zwei gestapelt (3 Fenster)',
            streams: {
                camera:  { x: 120, y: 0, width: 240, height: 640, zIndex: 1, aspectRatio: 'contain' },
                screen:  { x: 0,   y: 0, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' },
                screen2: { x: 0,   y: 320, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' }
            }
        });
        // NEW: 3 Fenster · Drei Spalten
        this.layouts.set('three-columns', {
            id: 'three-columns',
            name: '3 Fenster · Drei Spalten',
            description: 'Drei gleich breite Spalten (3 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0, width: 120, height: 640, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 120, y: 0, width: 120, height: 640, zIndex: 1, aspectRatio: 'contain' },
                screen2: { x: 240, y: 0, width: 120, height: 640, zIndex: 1, aspectRatio: 'contain' }
            }
        });

        // NEW: 4 Fenster · 2x2 Grid
        this.layouts.set('four-grid', {
            id: 'four-grid',
            name: '4 Fenster · 2×2 Raster',
            description: 'Vier Streams in 2×2 Anordnung (4 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 180, height: 320, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 180, y: 0,   width: 180, height: 320, zIndex: 1, aspectRatio: 'contain' },
                screen2: { x: 0,   y: 320, width: 180, height: 320, zIndex: 1, aspectRatio: 'contain' },
                screen3: { x: 180, y: 320, width: 180, height: 320, zIndex: 1, aspectRatio: 'contain' }
            }
        });

        // NEW: 4 Fenster · Vier Reihen (gestapelt)
        this.layouts.set('four-rows', {
            id: 'four-rows',
            name: '4 Fenster · Vier Reihen',
            description: 'Vier Streams untereinander (4 Fenster)',
            streams: {
                screen:  { x: 0, y: 0,   width: 360, height: 160, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 0, y: 160, width: 360, height: 160, zIndex: 1, aspectRatio: 'contain' },
                screen2: { x: 0, y: 320, width: 360, height: 160, zIndex: 1, aspectRatio: 'contain' },
                screen3: { x: 0, y: 480, width: 360, height: 160, zIndex: 1, aspectRatio: 'contain' }
            }
        });
        // NEW: 4 Fenster · Groß oben, drei unten
        this.layouts.set('four-top-three', {
            id: 'four-top-three',
            name: '4 Fenster · 1 oben, 3 unten',
            description: 'Oben groß, unten drei nebeneinander (4 Fenster)',
            streams: {
                screen:  { x: 0,   y: 0,   width: 360, height: 320, zIndex: 1, aspectRatio: 'contain' },
                camera:  { x: 0,   y: 320, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' },
                screen2: { x: 120, y: 320, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' },
                screen3: { x: 240, y: 320, width: 120, height: 320, zIndex: 2, aspectRatio: 'contain' }
            }
        });

        console.log(`📐 ${this.layouts.size} Layout-Vorlagen geladen`);
    }

    setupLayoutControls() {
        const layoutContainer = document.getElementById('layoutControls');
        if (!layoutContainer) return;

        // Create layout selector
        this.createLayoutSelector();
        
        // Create layout editor
        this.createLayoutEditor();
        
        // Setup drag and drop for canvas
        this.setupCanvasDragDrop();
    }

    getAvailableStreamKeys() {
        const keys = new Set();
        if (this.streamRecorder && this.streamRecorder.streams) {
            this.streamRecorder.streams.forEach((_, key) => keys.add(key));
        }
        return keys;
    }

    filterLayoutsForAvailable() {
        const available = this.getAvailableStreamKeys();
        const availableCount = available.size;
        // Zeige nur Vorlagen, deren Stream-Anzahl GENAU der aktuellen Anzahl entspricht
        const relevant = [];
        this.layouts.forEach(layout => {
            const required = Object.keys(layout.streams);
            if (required.length !== availableCount) return;
            const allPresent = required.every(k => available.has(k));
            if (allPresent) relevant.push(layout);
        });
        return relevant;
    }

    createLayoutSelector() {
        const selectorHTML = `
            <div class="layout-selector mb-3">
                <h6 class="text-muted mb-2 d-flex align-items-center justify-content-between">
                    <span><i class="fas fa-th-large me-2"></i>Layout Vorlagen</span>
                    <button class="btn btn-sm btn-outline-secondary" id="refreshLayoutsBtn">
                        <i class="fas fa-sync-alt me-1"></i>Aktualisieren
                    </button>
                </h6>
                <div class="layout-preset-compact">
                    ${this.filterLayoutsForAvailable().map(layout => `
                        <button type="button" class="btn btn-outline-primary btn-sm layout-chip" data-layout="${layout.id}">
                            ${this.getLayoutBadge(layout)} ${layout.name}
                        </button>
                    `).join('') || '<div class="text-muted small">Keine passenden Vorlagen — bitte Streams starten.</div>'}
                </div>
            </div>
        `;

        const container = document.getElementById('layoutControls');
        // Insert or replace selector (keep editor below)
        const tmp = document.createElement('div');
        tmp.innerHTML = selectorHTML;
        const selector = tmp.firstElementChild;
        const old = container.querySelector('.layout-selector');
        if (old) {
            old.replaceWith(selector);
        } else {
            container.insertAdjacentElement('afterbegin', selector);
        }

        // Add click handlers
        container.querySelectorAll('.layout-chip').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const layoutId = e.currentTarget.dataset.layout;
                this.applyLayout(layoutId);
            });
        });
        container.querySelector('#refreshLayoutsBtn')?.addEventListener('click', () => this.refreshLayoutSelector());
    }

    refreshLayoutSelector() {
        this.createLayoutSelector();
    }

    generateLayoutPreview(layout) {
        const previewWidth = 60;
        const previewHeight = 106; // 9:16 aspect ratio
        
        let previewHTML = `
            <svg width="${previewWidth}" height="${previewHeight}" class="layout-preview-svg">
        `;

        Object.entries(layout.streams).forEach(([streamType, config]) => {
            const scaleX = previewWidth / 360;
            const scaleY = previewHeight / 640;
            
            const x = config.x * scaleX;
            const y = config.y * scaleY;
            const width = config.width * scaleX;
            const height = config.height * scaleY;
            
            const color = streamType === 'camera' ? '#28a745' : '#007bff';
            const opacity = config.zIndex === 1 ? 0.8 : 0.6;
            
            previewHTML += `
                <rect x="${x}" y="${y}" width="${width}" height="${height}" 
                      fill="${color}" opacity="${opacity}" rx="2"/>
                <text x="${x + width/2}" y="${y + height/2}" 
                      text-anchor="middle" dominant-baseline="middle" 
                      font-size="8" fill="white">
                    ${streamType === 'camera' ? 'K' : 'S'}
                </text>
            `;
        });

        previewHTML += `</svg>`;
        return previewHTML;
    }

    getLayoutBadge(layout) {
        const count = Object.keys(layout.streams).length;
        return `<span class="badge bg-light text-dark me-1">${count}</span>`;
    }

    createLayoutEditor() {
        const editorHTML = `
            <div class="layout-editor mt-4">
                <h6 class="text-muted mb-3">
                    <i class="fas fa-edit me-2"></i>Layout Anpassung
                </h6>
                <div class="stream-controls" id="streamControls">
                    <!-- Dynamic stream controls will be added here -->
                </div>
                <div class="layout-actions mt-3">
                    <button class="btn btn-sm btn-outline-primary" id="resetLayoutBtn">
                        <i class="fas fa-undo me-1"></i>Zurücksetzen
                    </button>
                    <button class="btn btn-sm btn-outline-success" id="saveLayoutBtn">
                        <i class="fas fa-save me-1"></i>Layout speichern
                    </button>
                </div>
            </div>
        `;

        const container = document.getElementById('layoutControls');
        container.innerHTML += editorHTML;

        // Add action handlers
        document.getElementById('resetLayoutBtn')?.addEventListener('click', () => {
            this.resetToDefaultLayout();
        });

        document.getElementById('saveLayoutBtn')?.addEventListener('click', () => {
            this.saveCustomLayout();
        });
    }

    setupCanvasDragDrop() {
        const canvas = this.streamRecorder.canvas;
        const canvasContainer = canvas.parentElement;

        let isDragging = false;
        let isResizing = false;
        let dragOffset = { x: 0, y: 0 };
        let selectedStream = null;
        let resizeHandle = null;

        // Create overlay for drag handles
        const overlay = document.createElement('div');
        overlay.className = 'canvas-overlay';
        overlay.style.cssText = `
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
            z-index: 10;
        `;
        canvasContainer.appendChild(overlay);

        // Mouse down on canvas
        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) * (canvas.width / rect.width);
            const y = (e.clientY - rect.top) * (canvas.height / rect.height);

            selectedStream = this.getStreamAtPosition(x, y);
            if (selectedStream && this.activeLayout) {
                const streamConfig = this.activeLayout.streams[selectedStream];
                // Check if on resize handle
                const handle = this.getResizeHandleAtPosition(streamConfig, x, y);
                if (handle) {
                    isResizing = true;
                    resizeHandle = handle;
                    canvas.style.cursor = this.getCursorForHandle(handle);
                } else {
                    isDragging = true;
                    dragOffset = { x: x - streamConfig.x, y: y - streamConfig.y };
                    canvas.style.cursor = 'grabbing';
                }
                this.highlightSelectedStream(selectedStream);
            }
        });

        // Mouse move
        document.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
            const cy = (e.clientY - rect.top) * (canvas.height / rect.height);

            // Hover cursor over handles when not dragging/resizing
            if (!isDragging && !isResizing && this.activeLayout) {
                const hoverStream = this.getStreamAtPosition(cx, cy);
                if (hoverStream) {
                    const conf = this.activeLayout.streams[hoverStream];
                    const handle = this.getResizeHandleAtPosition(conf, cx, cy);
                    canvas.style.cursor = handle ? this.getCursorForHandle(handle) : 'grab';
                } else {
                    canvas.style.cursor = 'default';
                }
            }

            if ((!isDragging && !isResizing) || !selectedStream || !this.activeLayout) return;

            const streamConfig = this.activeLayout.streams[selectedStream];

            if (isDragging) {
                const newX = cx - dragOffset.x;
                const newY = cy - dragOffset.y;
                // Constrain within canvas
                streamConfig.x = Math.max(0, Math.min(newX, canvas.width - streamConfig.width));
                streamConfig.y = Math.max(0, Math.min(newY, canvas.height - streamConfig.height));
            }

            if (isResizing && resizeHandle) {
                // Start values
                let { x, y, width, height } = streamConfig;
                const maxW = canvas.width;
                const maxH = canvas.height;
                // Calculate new dimensions based on handle
                if (resizeHandle.includes('e')) {
                    width = Math.max(this.minSize, Math.min(maxW - x, cx - x));
                }
                if (resizeHandle.includes('s')) {
                    height = Math.max(this.minSize, Math.min(maxH - y, cy - y));
                }
                if (resizeHandle.includes('w')) {
                    const newX = Math.max(0, Math.min(x + width - this.minSize, cx));
                    width = Math.max(this.minSize, (x + width) - newX);
                    x = newX;
                }
                if (resizeHandle.includes('n')) {
                    const newY = Math.max(0, Math.min(y + height - this.minSize, cy));
                    height = Math.max(this.minSize, (y + height) - newY);
                    y = newY;
                }
                // Apply constraints
                streamConfig.x = Math.max(0, Math.min(x, maxW - width));
                streamConfig.y = Math.max(0, Math.min(y, maxH - height));
                streamConfig.width = Math.max(this.minSize, Math.min(width, maxW - streamConfig.x));
                streamConfig.height = Math.max(this.minSize, Math.min(height, maxH - streamConfig.y));
            }

            this.updateStreamControls();
        });

        // Mouse up
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                selectedStream = null;
                canvas.style.cursor = 'default';
                this.clearStreamHighlight();
            }
            if (isResizing) {
                isResizing = false;
                selectedStream = null;
                resizeHandle = null;
                canvas.style.cursor = 'default';
                this.clearStreamHighlight();
            }
        });
    }

    getStreamAtPosition(x, y) {
        if (!this.activeLayout) return null;

        // Check streams in reverse z-index order (top to bottom)
        const streams = Object.entries(this.activeLayout.streams)
            .sort(([,a], [,b]) => b.zIndex - a.zIndex);

        for (const [streamType, config] of streams) {
            if (x >= config.x && x <= config.x + config.width &&
                y >= config.y && y <= config.y + config.height) {
                return streamType;
            }
        }
        return null;
    }

    applyLayout(layoutId) {
        const layout = this.layouts.get(layoutId);
        if (!layout) return;

        this.activeLayout = JSON.parse(JSON.stringify(layout)); // Deep copy
        
        // Update active preset indicator
        document.querySelectorAll('.layout-preset-card').forEach(card => {
            card.classList.toggle('active', card.dataset.layout === layoutId);
        });

        // Update stream controls
        this.updateStreamControls();

        // Update composition if active
        if (this.streamRecorder.isComposing) {
            this.streamRecorder.updateCompositionLayout(this.activeLayout);
        } else if (this.streamRecorder.streams && this.streamRecorder.streams.size > 0) {
            // Auto-start composition so the user sees the layout effect immediately
            if (typeof this.streamRecorder.startComposition === 'function') {
                this.streamRecorder.startComposition();
            }
        }

        console.log(`📐 Layout "${layout.name}" angewendet`);
    }

    updateStreamControls() {
        const container = document.getElementById('streamControls');
        if (!container || !this.activeLayout) return;

        container.innerHTML = Object.entries(this.activeLayout.streams).map(([streamType, config]) => `
            <div class="stream-control mb-3" data-stream="${streamType}">
                <h6 class="stream-label">
                    <i class="fas fa-${streamType === 'camera' ? 'camera' : 'desktop'} me-2"></i>
                    ${streamType === 'camera' ? 'Kamera' : 'Bildschirm'}
                </h6>
                <div class="row">
                    <div class="col-6">
                        <label class="form-label">Position X:</label>
                        <input type="range" class="form-range position-x" 
                               min="0" max="${360 - config.width}" value="${config.x}"
                               data-stream="${streamType}">
                        <small class="text-muted">${config.x}px</small>
                    </div>
                    <div class="col-6">
                        <label class="form-label">Position Y:</label>
                        <input type="range" class="form-range position-y" 
                               min="0" max="${640 - config.height}" value="${config.y}"
                               data-stream="${streamType}">
                        <small class="text-muted">${config.y}px</small>
                    </div>
                </div>
                <div class="row">
                    <div class="col-6">
                        <label class="form-label">Breite:</label>
                        <input type="range" class="form-range width" 
                               min="50" max="360" value="${config.width}"
                               data-stream="${streamType}">
                        <small class="text-muted">${config.width}px</small>
                    </div>
                    <div class="col-6">
                        <label class="form-label">Höhe:</label>
                        <input type="range" class="form-range height" 
                               min="50" max="640" value="${config.height}"
                               data-stream="${streamType}">
                        <small class="text-muted">${config.height}px</small>
                    </div>
                </div>
                <div class="row">
                    <div class="col-6">
                        <label class="form-label">Ebene:</label>
                        <select class="form-select form-select-sm z-index" data-stream="${streamType}">
                            <option value="1" ${config.zIndex === 1 ? 'selected' : ''}>Hintergrund</option>
                            <option value="2" ${config.zIndex === 2 ? 'selected' : ''}>Vordergrund</option>
                        </select>
                    </div>
                    <div class="col-6">
                        <label class="form-label">Seitenverhältnis:</label>
                        <select class="form-select form-select-sm aspect-ratio" data-stream="${streamType}">
                            <option value="fill" ${config.aspectRatio === 'fill' ? 'selected' : ''}>Füllen</option>
                            <option value="cover" ${config.aspectRatio === 'cover' ? 'selected' : ''}>Abdecken</option>
                            <option value="contain" ${config.aspectRatio === 'contain' ? 'selected' : ''}>Einpassen</option>
                        </select>
                    </div>
                </div>
            </div>
        `).join('');

        // Add event listeners for controls
        container.querySelectorAll('.position-x, .position-y, .width, .height').forEach(input => {
            input.addEventListener('input', (e) => {
                this.updateStreamProperty(e.target);
            });
        });

        container.querySelectorAll('.z-index, .aspect-ratio').forEach(select => {
            select.addEventListener('change', (e) => {
                this.updateStreamProperty(e.target);
            });
        });
    }

    updateStreamProperty(input) {
        const streamType = input.dataset.stream;
        const property = input.className.split(' ')[1].replace('-', '');
        let value = input.value;

        if (['x', 'y', 'width', 'height', 'zIndex'].includes(property)) {
            value = parseInt(value);
        }

        if (property === 'zIndex') {
            this.activeLayout.streams[streamType].zIndex = value;
        } else if (property === 'aspectRatio') {
            this.activeLayout.streams[streamType].aspectRatio = value;
        } else {
            this.activeLayout.streams[streamType][property] = value;
        }

        // Update the display text
        const textElement = input.nextElementSibling;
        if (textElement && textElement.tagName === 'SMALL') {
            textElement.textContent = `${value}${['x', 'y', 'width', 'height'].includes(property) ? 'px' : ''}`;
        }

        // Update composition
        if (this.streamRecorder.isComposing) {
            this.streamRecorder.updateCompositionLayout(this.activeLayout);
        }
    }

    highlightSelectedStream(streamType) {
        // Add visual feedback for selected stream (could be enhanced with overlay graphics)
        console.log(`🎯 Stream "${streamType}" ausgewählt`);
    }

    clearStreamHighlight() {
        console.log('🎯 Stream-Auswahl aufgehoben');
    }

    getResizeHandleAtPosition(config, px, py) {
        const h = this.handleSize;
        const within = (x, y, w, h2) => (px >= x && px <= x + w && py >= y && py <= y + h2);
        const corners = {
            nw: { x: config.x - h/2, y: config.y - h/2 },
            ne: { x: config.x + config.width - h/2, y: config.y - h/2 },
            sw: { x: config.x - h/2, y: config.y + config.height - h/2 },
            se: { x: config.x + config.width - h/2, y: config.y + config.height - h/2 },
        };
        for (const [name, pos] of Object.entries(corners)) {
            if (within(pos.x, pos.y, h, h)) return name;
        }
        // Edges (exclude corners to favor corners first)
        const edgePad = 6;
        if (within(config.x + edgePad, config.y - h/2, config.width - 2*edgePad, h)) return 'n';
        if (within(config.x + edgePad, config.y + config.height - h/2, config.width - 2*edgePad, h)) return 's';
        if (within(config.x - h/2, config.y + edgePad, h, config.height - 2*edgePad)) return 'w';
        if (within(config.x + config.width - h/2, config.y + edgePad, h, config.height - 2*edgePad)) return 'e';
        return null;
    }

    getCursorForHandle(handle) {
        switch (handle) {
            case 'n': return 'ns-resize';
            case 's': return 'ns-resize';
            case 'e': return 'ew-resize';
            case 'w': return 'ew-resize';
            case 'ne': return 'nesw-resize';
            case 'sw': return 'nesw-resize';
            case 'nw': return 'nwse-resize';
            case 'se': return 'nwse-resize';
            default: return 'default';
        }
    }

    resetToDefaultLayout() {
        if (this.activeLayout) {
            const layoutId = this.activeLayout.id;
            this.applyLayout(layoutId);
        }
    }

    saveCustomLayout() {
        if (!this.activeLayout) return;

        const layoutName = prompt('Layout-Name:', `Custom Layout ${Date.now()}`);
        if (!layoutName) return;

        const customLayout = JSON.parse(JSON.stringify(this.activeLayout));
        customLayout.id = `custom-${Date.now()}`;
        customLayout.name = layoutName;
        customLayout.description = 'Benutzerdefiniertes Layout';

        this.layouts.set(customLayout.id, customLayout);
        
        // Refresh layout selector to include new layout
        this.createLayoutSelector();

        console.log(`💾 Benutzerdefiniertes Layout "${layoutName}" gespeichert`);
        alert(`Layout "${layoutName}" wurde gespeichert!`);
    }

    getActiveLayout() {
        return this.activeLayout;
    }

    // Method called by StreamRecorder to apply layout during composition
    applyLayoutToComposition(ctx, canvas, streams) {
        if (!this.activeLayout) return;

        const drawn = new Set();
        // 1) Draw configured streams in zIndex order
        Object.entries(this.activeLayout.streams)
            .sort(([,a], [,b]) => (a.zIndex||1) - (b.zIndex||1))
            .forEach(([streamType, config]) => {
            const stream = streams.get(streamType);
            if (!stream) return;

            const video = this.streamRecorder.getVideoElement(streamType, stream);
            if (!video || video.readyState < 2) return;

            ctx.save();

            // Apply aspect ratio handling
            let sx = 0, sy = 0, sw = video.videoWidth, sh = video.videoHeight;
            let dx = config.x, dy = config.y, dw = config.width, dh = config.height;

            if (config.aspectRatio === 'cover') {
                const videoAspect = video.videoWidth / video.videoHeight;
                const targetAspect = config.width / config.height;

                if (videoAspect > targetAspect) {
                    // Video is wider, crop sides
                    sw = video.videoHeight * targetAspect;
                    sx = (video.videoWidth - sw) / 2;
                } else {
                    // Video is taller, crop top/bottom
                    sh = video.videoWidth / targetAspect;
                    sy = (video.videoHeight - sh) / 2;
                }
            } else if (config.aspectRatio === 'contain') {
                const videoAspect = video.videoWidth / video.videoHeight;
                const targetAspect = config.width / config.height;

                if (videoAspect > targetAspect) {
                    // Video is wider, add letterboxing
                    dh = config.width / videoAspect;
                    dy = config.y + (config.height - dh) / 2;
                } else {
                    // Video is taller, add pillarboxing
                    dw = config.height * videoAspect;
                    dx = config.x + (config.width - dw) / 2;
                }
            }

            // Draw the video frame
            ctx.drawImage(video, sx, sy, sw, sh, dx, dy, dw, dh);

            // Draw border and resize handles
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.strokeRect(config.x, config.y, config.width, config.height);
            // Handles (corners + edges)
            const hs = this.handleSize;
            const handles = [
                { x: config.x, y: config.y },
                { x: config.x + config.width/2, y: config.y },
                { x: config.x + config.width, y: config.y },
                { x: config.x, y: config.y + config.height/2 },
                { x: config.x + config.width, y: config.y + config.height/2 },
                { x: config.x, y: config.y + config.height },
                { x: config.x + config.width/2, y: config.y + config.height },
                { x: config.x + config.width, y: config.y + config.height }
            ];
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            handles.forEach(pos => {
                ctx.fillRect(pos.x - hs/2, pos.y - hs/2, hs, hs);
                ctx.strokeStyle = '#000000';
                ctx.lineWidth = 1;
                ctx.strokeRect(pos.x - hs/2, pos.y - hs/2, hs, hs);
            });

            ctx.restore();
            drawn.add(streamType);
        });

        // 2) Auto-place any additional streams not defined in the layout (e.g., screen2, screen3)
        const remaining = Array.from(streams.keys()).filter(k => !drawn.has(k));
        if (remaining.length > 0) {
            // Simple tiling at bottom area
            const cols = Math.min(remaining.length, 3);
            const rows = Math.ceil(remaining.length / cols);
            const tileWidth = Math.floor(canvas.width / cols);
            const tileHeight = Math.floor(canvas.height / (rows * 3)); // bottom third
            const startY = canvas.height - tileHeight * rows - 10;

            remaining.forEach((key, idx) => {
                const stream = streams.get(key);
                const video = this.streamRecorder.getVideoElement(key, stream);
                if (!video || video.readyState < 2) return;

                const col = idx % cols;
                const row = Math.floor(idx / cols);
                const dx = col * tileWidth + 10;
                const dy = startY + row * tileHeight + 10;
                const dw = tileWidth - 20;
                const dh = tileHeight - 20;

                // contain fit for thumbnails
                let sx = 0, sy = 0, sw = video.videoWidth, sh = video.videoHeight;
                const videoAspect = sw / sh;
                const targetAspect = dw / dh;
                if (videoAspect > targetAspect) {
                    // letterbox
                    const newDh = dw / videoAspect;
                    const offsetY = dy + (dh - newDh) / 2;
                    ctx.drawImage(video, 0, 0, sw, sh, dx, offsetY, dw, newDh);
                } else {
                    // pillarbox
                    const newDw = dh * videoAspect;
                    const offsetX = dx + (dw - newDw) / 2;
                    ctx.drawImage(video, 0, 0, sw, sh, offsetX, dy, newDw, dh);
                }

                // border
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2;
                ctx.strokeRect(dx, dy, dw, dh);
            });
        }
    }
}

// CSS for layout manager (to be added to streamrec.css)
const layoutManagerStyles = `
<style>
.layout-presets {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
}

.layout-preset-compact {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.layout-chip {
    white-space: nowrap;
}

.layout-preset-card {
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 1rem;
}

.layout-preset-card:hover {
    border-color: #667eea;
    transform: translateY(-2px);
}

.layout-preset-card.active {
    border-color: #667eea;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
}

.layout-preview-svg {
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background: #000;
}

.stream-control {
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 1rem;
    background: #f8f9fa;
}

.stream-label {
    color: #495057;
    border-bottom: 1px solid #dee2e6;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

.canvas-overlay {
    pointer-events: none;
}

/* Dark mode support */
[data-theme="dark"] .stream-control {
    background: #495057;
    border-color: #6c757d;
}

[data-theme="dark"] .layout-preset-card {
    border-color: #495057;
    background: #343a40;
}

[data-theme="dark"] .layout-preset-card.active {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
}
</style>
`;

// Export for use in main StreamRecorder
window.LayoutManager = LayoutManager;
