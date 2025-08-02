/**
 * Advanced UX Features für Social Media Planer
 * Bulk-Actions, Auto-save, Keyboard Shortcuts
 */

class AdvancedSomiPlanFeatures {
    constructor() {
        this.selectedItems = new Set();
        this.autoSaveTimeout = null;
        this.keyboardShortcuts = new Map();
        this.bulkActionMode = false;
        
        this.init();
    }

    init() {
        this.initBulkActions();
        this.initAutoSave();
        this.initKeyboardShortcuts();
        this.initDragAndDrop();
        this.initQuickActions();
    }

    // ===== BULK ACTIONS =====
    
    initBulkActions() {
        // Add bulk action controls to pages with multiple items
        const postLists = document.querySelectorAll('.post-list, .post-grid');
        
        postLists.forEach(list => {
            this.addBulkActionControls(list);
            this.setupItemSelection(list);
        });
    }

    addBulkActionControls(container) {
        const bulkControls = document.createElement('div');
        bulkControls.className = 'bulk-actions-toolbar';
        bulkControls.style.display = 'none';
        bulkControls.innerHTML = `
            <div class="d-flex align-items-center justify-content-between p-3 bg-light border rounded mb-3">
                <div class="d-flex align-items-center">
                    <span class="me-3">
                        <strong id="selected-count">0</strong> Posts ausgewählt
                    </span>
                    <button type="button" class="btn btn-sm btn-outline-primary me-2" onclick="advancedFeatures.selectAll()">
                        <i class="fas fa-check-square me-1"></i>Alle auswählen
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="advancedFeatures.clearSelection()">
                        <i class="fas fa-times me-1"></i>Auswahl aufheben
                    </button>
                </div>
                <div class="d-flex gap-2">
                    <div class="dropdown">
                        <button class="btn btn-sm btn-primary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                            <i class="fas fa-cog me-1"></i>Aktionen
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="#" onclick="advancedFeatures.bulkSchedule()">
                                <i class="fas fa-calendar me-2"></i>Terminieren
                            </a></li>
                            <li><a class="dropdown-item" href="#" onclick="advancedFeatures.bulkEdit()">
                                <i class="fas fa-edit me-2"></i>Bearbeiten
                            </a></li>
                            <li><a class="dropdown-item" href="#" onclick="advancedFeatures.bulkDuplicate()">
                                <i class="fas fa-copy me-2"></i>Duplizieren
                            </a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-danger" href="#" onclick="advancedFeatures.bulkDelete()">
                                <i class="fas fa-trash me-2"></i>Löschen
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
        
        container.parentNode.insertBefore(bulkControls, container);
    }

    setupItemSelection(container) {
        const items = container.querySelectorAll('.post-card, .post-item');
        
        items.forEach(item => {
            // Add selection checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'item-selection-checkbox position-absolute';
            checkbox.style.cssText = 'top: 10px; left: 10px; z-index: 10; transform: scale(1.2);';
            checkbox.style.display = 'none';
            
            checkbox.addEventListener('change', (e) => {
                const itemId = item.dataset.postId || item.dataset.id;
                if (e.target.checked) {
                    this.selectedItems.add(itemId);
                    item.classList.add('selected');
                } else {
                    this.selectedItems.delete(itemId);
                    item.classList.remove('selected');
                }
                this.updateBulkActionControls();
            });
            
            item.style.position = 'relative';
            item.appendChild(checkbox);
            
            // Toggle selection mode on long press (mobile) or Ctrl+click
            item.addEventListener('click', (e) => {
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    this.toggleBulkMode();
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            });
            
            // Long press for mobile
            let longPressTimer;
            item.addEventListener('touchstart', (e) => {
                longPressTimer = setTimeout(() => {
                    this.toggleBulkMode();
                    checkbox.checked = true;
                    checkbox.dispatchEvent(new Event('change'));
                }, 800);
            });
            
            item.addEventListener('touchend', () => {
                clearTimeout(longPressTimer);
            });
        });
    }

    toggleBulkMode() {
        this.bulkActionMode = !this.bulkActionMode;
        const toolbar = document.querySelector('.bulk-actions-toolbar');
        const checkboxes = document.querySelectorAll('.item-selection-checkbox');
        
        if (this.bulkActionMode) {
            toolbar.style.display = 'block';
            checkboxes.forEach(cb => cb.style.display = 'block');
            document.body.classList.add('bulk-selection-mode');
        } else {
            toolbar.style.display = 'none';
            checkboxes.forEach(cb => {
                cb.style.display = 'none';
                cb.checked = false;
            });
            document.body.classList.remove('bulk-selection-mode');
            this.selectedItems.clear();
            document.querySelectorAll('.selected').forEach(item => {
                item.classList.remove('selected');
            });
        }
    }

    updateBulkActionControls() {
        const countEl = document.getElementById('selected-count');
        if (countEl) {
            countEl.textContent = this.selectedItems.size;
        }
        
        const toolbar = document.querySelector('.bulk-actions-toolbar');
        if (toolbar) {
            toolbar.style.display = this.selectedItems.size > 0 ? 'block' : 'none';
        }
    }

    selectAll() {
        const checkboxes = document.querySelectorAll('.item-selection-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = true;
            cb.dispatchEvent(new Event('change'));
        });
    }

    clearSelection() {
        const checkboxes = document.querySelectorAll('.item-selection-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.dispatchEvent(new Event('change'));
        });
    }

    // Bulk action implementations
    async bulkSchedule() {
        if (this.selectedItems.size === 0) return;
        
        const modal = this.createBulkScheduleModal();
        document.body.appendChild(modal);
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }

    async bulkEdit() {
        if (this.selectedItems.size === 0) return;
        
        const modal = this.createBulkEditModal();
        document.body.appendChild(modal);
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }

    async bulkDuplicate() {
        if (this.selectedItems.size === 0) return;
        
        const confirm = await this.showConfirmDialog(
            'Posts duplizieren',
            `Möchtest du ${this.selectedItems.size} Posts duplizieren?`
        );
        
        if (confirm) {
            this.showToast('Posts werden dupliziert...', 'info');
            // Implementation would make API calls to duplicate posts
        }
    }

    async bulkDelete() {
        if (this.selectedItems.size === 0) return;
        
        const confirm = await this.showConfirmDialog(
            'Posts löschen', 
            `Möchtest du wirklich ${this.selectedItems.size} Posts löschen? Diese Aktion kann nicht rückgängig gemacht werden.`,
            'danger'
        );
        
        if (confirm) {
            this.showToast('Posts werden gelöscht...', 'info');
            // Implementation would make API calls to delete posts
        }
    }

    // ===== AUTO-SAVE =====
    
    initAutoSave() {
        const forms = document.querySelectorAll('form[data-auto-save]');
        
        forms.forEach(form => {
            const saveUrl = form.dataset.autoSave;
            const interval = parseInt(form.dataset.autoSaveInterval) || 30000;
            
            this.setupAutoSave(form, saveUrl, interval);
        });
    }

    setupAutoSave(form, saveUrl, interval) {
        const inputs = form.querySelectorAll('input, textarea, select');
        let isDirty = false;
        let lastSaveData = this.getFormData(form);
        
        // Track form changes
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                isDirty = true;
                this.showAutoSaveIndicator('pending');
                
                // Debounced auto-save
                clearTimeout(this.autoSaveTimeout);
                this.autoSaveTimeout = setTimeout(() => {
                    if (isDirty) {
                        this.performAutoSave(form, saveUrl);
                    }
                }, interval);
            });
        });
        
        // Save on form focus loss
        form.addEventListener('focusout', (e) => {
            if (!form.contains(e.relatedTarget) && isDirty) {
                this.performAutoSave(form, saveUrl);
            }
        });
        
        // Save on page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && isDirty) {
                this.performAutoSave(form, saveUrl);
            }
        });
        
        // Periodic save
        setInterval(() => {
            if (isDirty) {
                this.performAutoSave(form, saveUrl);
            }
        }, interval * 2);
        
        const markClean = () => {
            isDirty = false;
            lastSaveData = this.getFormData(form);
        };
        
        const markDirty = () => {
            const currentData = this.getFormData(form);
            isDirty = JSON.stringify(currentData) !== JSON.stringify(lastSaveData);
        };
        
        // Initial state
        markClean();
    }

    async performAutoSave(form, saveUrl) {
        try {
            this.showAutoSaveIndicator('saving');
            
            const formData = new FormData(form);
            const response = await fetch(saveUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            if (response.ok) {
                this.showAutoSaveIndicator('saved');
                setTimeout(() => this.hideAutoSaveIndicator(), 2000);
            } else {
                throw new Error('Save failed');
            }
        } catch (error) {
            this.showAutoSaveIndicator('error');
            console.error('Auto-save failed:', error);
        }
    }

    getFormData(form) {
        const formData = new FormData(form);
        const data = {};
        for (let [key, value] of formData.entries()) {
            data[key] = value;
        }
        return data;
    }

    showAutoSaveIndicator(state) {
        let indicator = document.getElementById('auto-save-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'auto-save-indicator';
            indicator.className = 'auto-save-indicator';
            document.body.appendChild(indicator);
        }
        
        const states = {
            pending: { icon: '⏳', text: 'Änderungen erkannt...', class: 'warning' },
            saving: { icon: '💾', text: 'Speichere automatisch...', class: 'info' },
            saved: { icon: '✅', text: 'Automatisch gespeichert', class: 'success' },
            error: { icon: '❌', text: 'Auto-Save fehlgeschlagen', class: 'danger' }
        };
        
        const stateConfig = states[state];
        indicator.innerHTML = `${stateConfig.icon} ${stateConfig.text}`;
        indicator.className = `auto-save-indicator alert alert-${stateConfig.class}`;
        indicator.style.display = 'block';
    }

    hideAutoSaveIndicator() {
        const indicator = document.getElementById('auto-save-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    // ===== KEYBOARD SHORTCUTS =====
    
    initKeyboardShortcuts() {
        // Define shortcuts
        this.keyboardShortcuts.set('ctrl+s', () => this.saveCurrentForm());
        this.keyboardShortcuts.set('ctrl+n', () => this.createNewPost());
        this.keyboardShortcuts.set('ctrl+a', () => this.selectAll());
        this.keyboardShortcuts.set('escape', () => this.clearSelection());
        this.keyboardShortcuts.set('ctrl+d', () => this.duplicateSelected());
        this.keyboardShortcuts.set('delete', () => this.deleteSelected());
        this.keyboardShortcuts.set('ctrl+/', () => this.showShortcutsHelp());
        
        document.addEventListener('keydown', (e) => {
            const shortcut = this.getShortcutString(e);
            const handler = this.keyboardShortcuts.get(shortcut);
            
            if (handler && !this.isTyping(e.target)) {
                e.preventDefault();
                handler();
            }
        });
        
        // Add shortcuts help button
        this.addShortcutsHelpButton();
    }

    getShortcutString(event) {
        const parts = [];
        if (event.ctrlKey || event.metaKey) parts.push('ctrl');
        if (event.altKey) parts.push('alt');
        if (event.shiftKey) parts.push('shift');
        
        const key = event.key.toLowerCase();
        if (key !== 'control' && key !== 'alt' && key !== 'shift' && key !== 'meta') {
            parts.push(key);
        }
        
        return parts.join('+');
    }

    isTyping(element) {
        const typingElements = ['input', 'textarea', 'select'];
        return typingElements.includes(element.tagName.toLowerCase()) ||
               element.contentEditable === 'true';
    }

    // Shortcut handlers
    saveCurrentForm() {
        const form = document.querySelector('form:focus-within, form');
        if (form) {
            this.performAutoSave(form, form.dataset.autoSave || form.action);
        }
    }

    createNewPost() {
        const createButton = document.querySelector('[href*="post/create"], .btn-create-post');
        if (createButton) {
            createButton.click();
        }
    }

    duplicateSelected() {
        if (this.selectedItems.size > 0) {
            this.bulkDuplicate();
        }
    }

    deleteSelected() {
        if (this.selectedItems.size > 0) {
            this.bulkDelete();
        }
    }

    showShortcutsHelp() {
        const modal = this.createShortcutsModal();
        document.body.appendChild(modal);
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }

    addShortcutsHelpButton() {
        const helpButton = document.createElement('button');
        helpButton.className = 'btn btn-outline-secondary btn-sm shortcuts-help-btn';
        helpButton.innerHTML = '<i class="fas fa-keyboard me-1"></i>';
        helpButton.title = 'Keyboard Shortcuts (Ctrl+/)';
        helpButton.onclick = () => this.showShortcutsHelp();
        
        // Add to header if exists
        const header = document.querySelector('.somi-plan-header .col-md-4');
        if (header) {
            header.appendChild(helpButton);
        }
    }

    // ===== DRAG AND DROP =====
    
    initDragAndDrop() {
        const postItems = document.querySelectorAll('.post-card, .post-item');
        const calendar = document.querySelector('.calendar');
        
        postItems.forEach(item => {
            item.draggable = true;
            item.addEventListener('dragstart', this.handleDragStart.bind(this));
            item.addEventListener('dragend', this.handleDragEnd.bind(this));
        });
        
        if (calendar) {
            const calendarDays = calendar.querySelectorAll('.calendar-day');
            calendarDays.forEach(day => {
                day.addEventListener('dragover', this.handleDragOver.bind(this));
                day.addEventListener('drop', this.handleDrop.bind(this));
            });
        }
    }

    handleDragStart(e) {
        e.dataTransfer.setData('text/plain', e.target.dataset.postId);
        e.target.classList.add('dragging');
    }

    handleDragEnd(e) {
        e.target.classList.remove('dragging');
    }

    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('drag-over');
    }

    handleDrop(e) {
        e.preventDefault();
        const postId = e.dataTransfer.getData('text/plain');
        const date = e.currentTarget.dataset.date;
        
        e.currentTarget.classList.remove('drag-over');
        
        // Schedule post to this date
        this.schedulePost(postId, date);
    }

    async schedulePost(postId, date) {
        try {
            const response = await fetch('/somi-plan/post/schedule/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ post_id: postId, date: date })
            });
            
            if (response.ok) {
                this.showToast('Post erfolgreich terminiert!', 'success');
                // Refresh calendar or update UI
            } else {
                throw new Error('Scheduling failed');
            }
        } catch (error) {
            this.showToast('Fehler beim Terminieren des Posts', 'danger');
        }
    }

    // ===== QUICK ACTIONS =====
    
    initQuickActions() {
        this.addQuickActionButtons();
        this.initQuickTemplates();
    }

    addQuickActionButtons() {
        const quickActions = document.createElement('div');
        quickActions.className = 'quick-actions-panel';
        quickActions.innerHTML = `
            <div class="quick-actions-trigger" onclick="advancedFeatures.toggleQuickActions()">
                <i class="fas fa-bolt"></i>
            </div>
            <div class="quick-actions-menu" style="display: none;">
                <button class="quick-action-btn" onclick="advancedFeatures.quickCreatePost()" title="Schnell-Post erstellen">
                    <i class="fas fa-plus"></i>
                </button>
                <button class="quick-action-btn" onclick="advancedFeatures.openCalendar()" title="Kalender öffnen">
                    <i class="fas fa-calendar"></i>
                </button>
                <button class="quick-action-btn" onclick="advancedFeatures.toggleBulkMode()" title="Bulk-Modus">
                    <i class="fas fa-check-square"></i>
                </button>
                <button class="quick-action-btn" onclick="advancedFeatures.showAnalytics()" title="Analytics">
                    <i class="fas fa-chart-bar"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(quickActions);
    }

    toggleQuickActions() {
        const menu = document.querySelector('.quick-actions-menu');
        const isVisible = menu.style.display !== 'none';
        menu.style.display = isVisible ? 'none' : 'block';
    }

    quickCreatePost() {
        // Open quick create modal or navigate to create page
        window.location.href = '/somi-plan/post/create/';
    }

    openCalendar() {
        window.location.href = '/somi-plan/calendar/';
    }

    showAnalytics() {
        window.location.href = '/somi-plan/analytics/';
    }

    initQuickTemplates() {
        // Add quick template buttons to post creation forms
        const contentFields = document.querySelectorAll('textarea[name="content"]');
        
        contentFields.forEach(field => {
            const templates = this.createQuickTemplates();
            field.parentNode.insertBefore(templates, field.nextSibling);
        });
    }

    createQuickTemplates() {
        const templatesDiv = document.createElement('div');
        templatesDiv.className = 'quick-templates mt-2';
        templatesDiv.innerHTML = `
            <small class="text-muted">Schnell-Vorlagen:</small>
            <div class="btn-group btn-group-sm mt-1" role="group">
                <button type="button" class="btn btn-outline-secondary" onclick="advancedFeatures.insertTemplate('question')">
                    Frage
                </button>
                <button type="button" class="btn btn-outline-secondary" onclick="advancedFeatures.insertTemplate('tip')">
                    Tipp
                </button>
                <button type="button" class="btn btn-outline-secondary" onclick="advancedFeatures.insertTemplate('motivation')">
                    Motivation
                </button>
                <button type="button" class="btn btn-outline-secondary" onclick="advancedFeatures.insertTemplate('behind_scenes')">
                    Behind Scenes
                </button>
            </div>
        `;
        
        return templatesDiv;
    }

    insertTemplate(type) {
        const templates = {
            question: "Was denkst du über...?\n\n[Deine Frage hier]\n\nTeile deine Meinung in den Kommentaren! 💭",
            tip: "💡 Profi-Tipp:\n\n[Dein Tipp hier]\n\nHast du weitere Tipps? Lass es uns wissen! 👇",
            motivation: "🌟 Motivation des Tages:\n\n[Deine Motivation hier]\n\nDu schaffst das! 💪 #motivation",
            behind_scenes: "🎬 Behind the Scenes:\n\n[Zeige was hinter den Kulissen passiert]\n\n#behindthescenes #authentisch"
        };
        
        const contentField = document.querySelector('textarea[name="content"]');
        if (contentField && templates[type]) {
            contentField.value = templates[type];
            contentField.focus();
            contentField.dispatchEvent(new Event('input')); // Trigger character counter update
        }
    }

    // ===== UTILITY METHODS =====
    
    createBulkScheduleModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Posts terminieren</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="bulk-schedule-form">
                            <div class="mb-3">
                                <label class="form-label">Startdatum</label>
                                <input type="date" class="form-control" name="start_date" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Zeitabstand</label>
                                <select class="form-select" name="interval">
                                    <option value="daily">Täglich</option>
                                    <option value="every_2_days">Jeden 2. Tag</option>
                                    <option value="weekly">Wöchentlich</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Uhrzeit</label>
                                <input type="time" class="form-control" name="time" value="10:00">
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>
                        <button type="button" class="btn btn-primary" onclick="advancedFeatures.executeScheduling()">Terminieren</button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    createBulkEditModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Posts bearbeiten</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="bulk-edit-form">
                            <div class="mb-3">
                                <label class="form-label">Hashtags hinzufügen</label>
                                <input type="text" class="form-control" name="add_hashtags" placeholder="#neuerhashtag #zusätzlich">
                                <small class="text-muted">Wird zu bestehenden Hashtags hinzugefügt</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Hashtags entfernen</label>
                                <input type="text" class="form-control" name="remove_hashtags" placeholder="#entfernen #löschen">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Call-to-Action hinzufügen</label>
                                <textarea class="form-control" name="add_cta" rows="2" placeholder="Was denkst du? Kommentiere unten! 👇"></textarea>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Status ändern</label>
                                <select class="form-select" name="status">
                                    <option value="">Nicht ändern</option>
                                    <option value="draft">Entwurf</option>
                                    <option value="scheduled">Geplant</option>
                                    <option value="published">Veröffentlicht</option>
                                </select>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>
                        <button type="button" class="btn btn-primary" onclick="advancedFeatures.executeBulkEdit()">Änderungen anwenden</button>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    createShortcutsModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Keyboard Shortcuts</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + S</kbd></div>
                            <div class="col-6">Speichern</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + N</kbd></div>
                            <div class="col-6">Neuer Post</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + A</kbd></div>
                            <div class="col-6">Alle auswählen</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Escape</kbd></div>
                            <div class="col-6">Auswahl aufheben</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + D</kbd></div>
                            <div class="col-6">Auswahl duplizieren</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Delete</kbd></div>
                            <div class="col-6">Auswahl löschen</div>
                        </div>
                        <div class="row">
                            <div class="col-6"><kbd>Ctrl + /</kbd></div>
                            <div class="col-6">Diese Hilfe anzeigen</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        return modal;
    }

    async showConfirmDialog(title, message, type = 'primary') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-sm">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" onclick="this.closest('.modal').resolve(false)">Abbrechen</button>
                            <button type="button" class="btn btn-${type}" data-bs-dismiss="modal" onclick="this.closest('.modal').resolve(true)">Bestätigen</button>
                        </div>
                    </div>
                </div>
            `;
            
            modal.resolve = resolve;
            document.body.appendChild(modal);
            
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
            
            modal.addEventListener('hidden.bs.modal', () => {
                if (!modal.resolved) resolve(false);
                modal.remove();
            });
        });
    }

    showToast(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        const container = document.querySelector('.toast-container') || this.createToastContainer();
        container.appendChild(toast);
        
        const bootstrapToast = new bootstrap.Toast(toast, { delay: duration });
        bootstrapToast.show();
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }
}

// Initialize advanced features when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.advancedFeatures = new AdvancedSomiPlanFeatures();
});

// CSS for advanced features
const advancedFeaturesCSS = `
/* Bulk Selection Mode */
.bulk-selection-mode .post-card,
.bulk-selection-mode .post-item {
    cursor: pointer;
    transition: all 0.2s ease;
}

.bulk-selection-mode .post-card.selected,
.bulk-selection-mode .post-item.selected {
    border-color: #0d6efd !important;
    background-color: rgba(13, 110, 253, 0.1);
    transform: scale(0.98);
}

.item-selection-checkbox {
    background: white;
    border: 2px solid #0d6efd;
    border-radius: 4px;
}

/* Auto-save indicator */
.auto-save-indicator {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    font-size: 0.85rem;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: none;
    animation: slideInRight 0.3s ease;
}

@keyframes slideInRight {
    from { transform: translateX(100%); }
    to { transform: translateX(0); }
}

/* Quick Actions Panel */
.quick-actions-panel {
    position: fixed;
    bottom: 80px;
    right: 20px;
    z-index: 1000;
}

.quick-actions-trigger {
    width: 56px;
    height: 56px;
    background: linear-gradient(45deg, #667eea, #764ba2);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.25rem;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    transition: transform 0.3s ease;
}

.quick-actions-trigger:hover {
    transform: scale(1.1);
}

.quick-actions-menu {
    position: absolute;
    bottom: 70px;
    right: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.quick-action-btn {
    width: 48px;
    height: 48px;
    background: white;
    border: 2px solid #e9ecef;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #495057;
    font-size: 1.1rem;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    transition: all 0.3s ease;
}

.quick-action-btn:hover {
    background: #f8f9fa;
    transform: scale(1.1);
    color: #0d6efd;
}

/* Drag and Drop */
.dragging {
    opacity: 0.5;
    transform: rotate(5deg);
}

.drag-over {
    background-color: rgba(13, 110, 253, 0.1) !important;
    border: 2px dashed #0d6efd !important;
}

/* Quick Templates */
.quick-templates {
    border-top: 1px solid #e9ecef;
    padding-top: 0.5rem;
    margin-top: 0.5rem;
}

.quick-templates .btn-group .btn {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
}

/* Shortcuts Help Button */
.shortcuts-help-btn {
    margin-left: 0.5rem;
}

/* Modal improvements */
.modal-dialog-bulk {
    max-width: 800px;
}

/* Keyboard focus improvements */
.quick-action-btn:focus,
.quick-actions-trigger:focus {
    outline: 3px solid #0d6efd;
    outline-offset: 2px;
}

/* Mobile optimizations */
@media (max-width: 768px) {
    .quick-actions-panel {
        bottom: 20px;
        right: 20px;
    }
    
    .bulk-actions-toolbar {
        position: sticky;
        top: 0;
        z-index: 100;
        background: white;
        border-bottom: 1px solid #e9ecef;
        margin: 0 -1rem 1rem;
        padding: 1rem;
    }
    
    .auto-save-indicator {
        right: 10px;
        left: 10px;
        text-align: center;
    }
}
`;

// Inject CSS
const style = document.createElement('style');
style.textContent = advancedFeaturesCSS;
document.head.appendChild(style);