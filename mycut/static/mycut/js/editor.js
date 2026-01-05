/**
 * MyCut Editor - Main Controller
 */
class MyCutEditor {
    constructor(config) {
        this.projectId = config.projectId;
        this.csrfToken = config.csrfToken;
        this.videoUrl = config.videoUrl;

        this.video = null;
        this.timeline = null;
        this.waveform = null;

        this.project = {
            clips: [],
            subtitles: [],
            textOverlays: [],
            suggestions: []
        };

        this.isPlaying = false;
        this.isSaving = false;
        this.hasUnsavedChanges = false;

        // Undo/Redo History
        this.history = [];
        this.historyIndex = -1;
        this.maxHistoryLength = 50;
        this.isUndoing = false;

        // Currently selected clip for properties panel
        this.selectedClip = null;

        this.init();
    }

    async init() {
        this.video = document.getElementById('video-player');
        this.setupVideoEvents();
        this.setupTimeline();
        this.setupKeyboardShortcuts();
        this.setupAutoSave();

        await this.loadProject();
        await this.loadWaveform();

        console.log('MyCut Editor initialized');
    }

    setupVideoEvents() {
        this.video.addEventListener('loadedmetadata', () => {
            const durationMs = this.video.duration * 1000;
            this.timeline.setDuration(durationMs);
            this.updateTimeDisplay();
        });

        this.video.addEventListener('timeupdate', () => {
            const currentTimeMs = this.video.currentTime * 1000;
            this.timeline.setCurrentTime(currentTimeMs);
            this.updateTimeDisplay();
            this.updateActiveSubtitle();
        });

        this.video.addEventListener('play', () => {
            this.isPlaying = true;
        });

        this.video.addEventListener('pause', () => {
            this.isPlaying = false;
        });
    }

    setupTimeline() {
        const container = document.getElementById('timeline-canvas-container');
        if (!container) {
            console.error('Timeline container not found');
            return;
        }

        this.timeline = new MyCutTimeline(container, {
            trackHeight: 50,
            rulerHeight: 30
        });

        // Timeline event handlers
        this.timeline.onSeek = (time) => {
            this.video.currentTime = time / 1000;
        };

        this.timeline.onClipMoved = (clip) => {
            this.saveState('Clip verschoben');
            this.hasUnsavedChanges = true;
            this.updateClip(clip);
        };

        this.timeline.onClipTrimmed = (clip) => {
            this.saveState('Clip getrimmt');
            this.hasUnsavedChanges = true;
            this.updateClip(clip);
        };

        this.timeline.onClipSplit = (original, newClip) => {
            this.saveState('Clip geteilt');
            this.hasUnsavedChanges = true;
            this.project.clips.push(newClip);
            this.saveClips();
        };

        this.timeline.onClipDeleted = (clip) => {
            this.saveState('Clip geloescht');
            this.hasUnsavedChanges = true;
            this.deleteClip(clip.id);
        };

        this.timeline.onClipDoubleClick = (clip) => {
            this.editClip(clip);
        };

        this.timeline.onClipSelected = (clip) => {
            if (clip && clip.clip_type === 'video') {
                this.selectClip(clip);
            } else {
                this.hideClipProperties();
            }
        };
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlayPause();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.seekRelative(-5000);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.seekRelative(5000);
                    break;
                case 's':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.saveProject();
                    }
                    break;
                case 'Delete':
                case 'Backspace':
                    if (this.timeline.selectedClip) {
                        e.preventDefault();
                        this.timeline.deleteSelectedClip();
                    }
                    break;
                case 'c':
                    if (e.ctrlKey || e.metaKey) {
                        // Copy clip
                    }
                    break;
                case 'z':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        if (e.shiftKey) {
                            this.redo();
                        } else {
                            this.undo();
                        }
                    }
                    break;
                case 'y':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.redo();
                    }
                    break;
                case '+':
                case '=':
                    this.timeline.zoomIn();
                    break;
                case '-':
                    this.timeline.zoomOut();
                    break;
            }
        });
    }

    setupAutoSave() {
        setInterval(() => {
            if (this.hasUnsavedChanges && !this.isSaving) {
                this.saveProject(true);
            }
        }, 30000); // Auto-save every 30 seconds

        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = 'Es gibt ungespeicherte Aenderungen. Wirklich verlassen?';
            }
        });
    }

    // Playback controls
    togglePlayPause() {
        if (this.isPlaying) {
            this.video.pause();
        } else {
            this.video.play();
        }
    }

    seekRelative(deltaMs) {
        const newTime = this.video.currentTime + (deltaMs / 1000);
        this.video.currentTime = Math.max(0, Math.min(newTime, this.video.duration));
    }

    seekTo(timeMs) {
        this.video.currentTime = timeMs / 1000;
    }

    // Data loading
    async loadProject() {
        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/`);

            // API returns data directly, not wrapped in {success: true}
            if (result.id) {
                this.project.clips = result.clips || [];
                this.project.subtitles = result.subtitles || [];
                this.project.textOverlays = result.text_overlays || [];
                this.project.suggestions = result.ai_suggestions || [];

                // Convert subtitles to timeline clips
                const subtitleClips = this.project.subtitles.map(sub => ({
                    id: 'sub_' + sub.id,
                    clip_type: 'subtitle',
                    start_time: sub.start_time,
                    duration: sub.end_time - sub.start_time,
                    text: sub.text,
                    source_id: sub.id
                }));

                // Convert text overlays to timeline clips
                const overlayClips = this.project.textOverlays.map(overlay => ({
                    id: 'overlay_' + overlay.id,
                    clip_type: 'text_overlay',
                    start_time: overlay.start_time,
                    duration: overlay.end_time - overlay.start_time,
                    text: overlay.text,
                    source_id: overlay.id
                }));

                // Combine all clips
                const allClips = [
                    ...this.project.clips,
                    ...subtitleClips,
                    ...overlayClips
                ];

                this.timeline.setClips(allClips);
                this.renderSubtitlesList();
                this.renderSuggestionsList();

                // Store video duration
                if (result.source_video && result.source_video.duration) {
                    this.videoDuration = result.source_video.duration * 1000; // Convert to ms
                }

                // Initialize Undo/Redo with initial state
                this.history = [];
                this.historyIndex = -1;
                this.saveState('Projekt geladen');
                this.updateUndoRedoButtons();
            }
        } catch (error) {
            console.error('Error loading project:', error);
        }
    }

    async loadWaveform() {
        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/waveform/`);
            if (result.success && result.waveform && result.waveform.length > 0) {
                this.timeline.setWaveform(result.waveform);
            } else {
                // Generate client-side if not available
                this.generateWaveformClientSide();
            }
        } catch (error) {
            console.error('Error loading waveform:', error);
            this.generateWaveformClientSide();
        }
    }

    async generateWaveformClientSide() {
        if (!this.video.src) return;

        this.waveform = new MyCutWaveform();
        try {
            const data = await this.waveform.extractFromUrl(this.video.src);
            if (data.length > 0) {
                const simplified = this.waveform.getSimplifiedData(300);
                this.timeline.setWaveform(simplified);

                // Save to server for future use
                await this.apiCall(`/mycut/api/project/${this.projectId}/waveform/`, 'POST', {
                    waveform: simplified
                });
            }
        } catch (error) {
            console.error('Error generating waveform:', error);
        }
    }

    // Project operations
    async saveProject(silent = false) {
        if (this.isSaving) return;
        this.isSaving = true;

        const btn = document.getElementById('btn-save');
        if (!silent && btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Speichern...';
        }

        try {
            const projectData = {
                clips: this.project.clips,
                subtitles: this.project.subtitles,
                export_quality: document.getElementById('export-quality')?.value || '1080p',
                export_format: document.getElementById('export-format')?.value || 'mp4'
            };

            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/save/`, 'POST', projectData);

            if (result.success) {
                this.hasUnsavedChanges = false;

                if (!silent && btn) {
                    btn.innerHTML = '<i class="fas fa-check me-1"></i> Gespeichert!';
                    setTimeout(() => {
                        btn.innerHTML = '<i class="fas fa-save me-1"></i> Speichern';
                        btn.disabled = false;
                    }, 2000);
                }
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('Error saving project:', error);
            if (!silent) {
                this.showError('Fehler beim Speichern: ' + error.message);
                if (btn) {
                    btn.innerHTML = '<i class="fas fa-save me-1"></i> Speichern';
                    btn.disabled = false;
                }
            }
        } finally {
            this.isSaving = false;
        }
    }

    // Clip operations
    async updateClip(clip) {
        try {
            await this.apiCall(`/mycut/api/project/${this.projectId}/clip/${clip.id}/`, 'PUT', clip);
        } catch (error) {
            console.error('Error updating clip:', error);
        }
    }

    async deleteClip(clipId) {
        try {
            await this.apiCall(`/mycut/api/project/${this.projectId}/clip/${clipId}/`, 'DELETE');
            this.project.clips = this.project.clips.filter(c => c.id !== clipId);
        } catch (error) {
            console.error('Error deleting clip:', error);
        }
    }

    async saveClips() {
        try {
            await this.apiCall(`/mycut/api/project/${this.projectId}/clips/`, 'POST', {
                clips: this.project.clips
            });
        } catch (error) {
            console.error('Error saving clips:', error);
        }
    }

    editClip(clip) {
        // Open clip edit modal/panel
        console.log('Edit clip:', clip);
    }

    splitClip() {
        const newClip = this.timeline.splitClipAtPlayhead();
        if (newClip) {
            this.showSuccess('Clip geteilt');
        }
    }

    deleteSelectedClip() {
        this.timeline.deleteSelectedClip();
    }

    // AI operations
    async startTranscription() {
        if (!confirm('Transkription starten? Dies kann je nach Videolänge 1-5 Minuten dauern.\n\nVoraussetzung: OpenAI API-Key in den Einstellungen konfiguriert.')) return;

        const btn = document.querySelector('[onclick="editor.startTranscription()"]');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Transkribiere...';
        }

        this.showProgress('Audio wird extrahiert...');
        this.updateProgressBar(10);

        try {
            // Simulate progress stages
            setTimeout(() => {
                this.showProgress('Sende an OpenAI Whisper API...');
                this.updateProgressBar(30);
            }, 1000);

            setTimeout(() => {
                this.showProgress('Transkription läuft...');
                this.updateProgressBar(50);
            }, 3000);

            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/transcribe/`, 'POST');

            if (result.success) {
                this.updateProgressBar(100);
                this.showSuccess(`Fertig! ${result.segments} Segmente, ${result.words} Woerter erkannt.`);

                // Show notification
                this.showNotification('success', 'Transkription abgeschlossen', `${result.segments} Untertitel wurden erstellt.`);

                setTimeout(() => location.reload(), 2000);
            } else {
                this.showError('Fehler: ' + result.error);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-microphone me-1"></i> Transkribieren';
                }
            }
        } catch (error) {
            this.showError('Fehler bei der Transkription: ' + error.message);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-microphone me-1"></i> Transkribieren';
            }
        }
    }

    async startAnalysis() {
        const btn = document.querySelector('[onclick="editor.startAnalysis()"]');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Analysiere...';
        }

        this.showProgress('Analysiere Transkription...');
        this.updateProgressBar(20);

        try {
            setTimeout(() => {
                this.showProgress('Suche Fuellwoerter...');
                this.updateProgressBar(40);
            }, 500);

            setTimeout(() => {
                this.showProgress('Erkenne Pausen...');
                this.updateProgressBar(60);
            }, 1000);

            setTimeout(() => {
                this.showProgress('Analysiere Sprechgeschwindigkeit...');
                this.updateProgressBar(80);
            }, 1500);

            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/analyze/`, 'POST');

            if (result.success) {
                this.updateProgressBar(100);
                const total = result.filler_words + result.silences + result.speed_changes;
                this.showSuccess(`${total} Vorschlaege erstellt!`);

                this.showNotification('success', 'Analyse abgeschlossen',
                    `${result.filler_words} Fuellwoerter, ${result.silences} Pausen, ${result.speed_changes} Speed-Aenderungen`);

                setTimeout(() => location.reload(), 2000);
            } else {
                this.showError('Fehler: ' + result.error);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-magic me-1"></i> Auto-Edit analysieren';
                }
            }
        } catch (error) {
            this.showError('Fehler bei der Analyse: ' + error.message);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-magic me-1"></i> Auto-Edit analysieren';
            }
        }
    }

    async applySuggestion(id) {
        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/apply-suggestion/${id}/`, 'POST');
            if (result.success) {
                document.querySelector(`.ai-suggestion[data-id="${id}"]`)?.remove();
                this.project.suggestions = this.project.suggestions.filter(s => s.id !== id);
                this.hasUnsavedChanges = true;
            }
        } catch (error) {
            this.showError('Fehler beim Anwenden');
        }
    }

    async rejectSuggestion(id) {
        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/reject-suggestion/${id}/`, 'POST');
            if (result.success) {
                document.querySelector(`.ai-suggestion[data-id="${id}"]`)?.remove();
                this.project.suggestions = this.project.suggestions.filter(s => s.id !== id);
            }
        } catch (error) {
            this.showError('Fehler beim Ablehnen');
        }
    }

    async applyAllSuggestions() {
        if (!confirm('Alle Vorschlaege anwenden?')) return;

        const suggestions = document.querySelectorAll('.ai-suggestion');
        for (const el of suggestions) {
            const id = el.dataset.id;
            await this.applySuggestion(id);
        }

        this.showSuccess('Alle Vorschlaege angewendet');
    }

    // Export
    async startExport() {
        const quality = document.getElementById('modal-export-quality')?.value || '1080p';
        const format = document.getElementById('modal-export-format')?.value || 'mp4';
        const burnSubtitles = document.getElementById('burn-subtitles')?.checked || false;

        // Export-Button deaktivieren
        const exportBtn = document.getElementById('start-export-btn');
        if (exportBtn) {
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Export wird gestartet...';
        }

        // Progress anzeigen
        this.showExportProgress(true);
        this.updateExportProgress(0, 'Export wird vorbereitet...');

        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/export/`, 'POST', {
                quality, format, burn_subtitles: burnSubtitles
            });

            if (result.success) {
                this.currentExportJobId = result.job_id;

                // Falls synchroner Export (Celery nicht verfuegbar)
                if (result.output_url) {
                    this.handleExportComplete(result);
                } else {
                    // Async Export - starte Polling
                    this.showNotification('info', 'Export gestartet', `${quality} ${format.toUpperCase()} wird erstellt...`);
                    this.pollExportStatus(result.job_id);
                }
            } else {
                this.handleExportError(result.error);
            }
        } catch (error) {
            this.handleExportError('Netzwerkfehler: ' + error.message);
        }
    }

    async pollExportStatus(jobId) {
        const poll = async () => {
            try {
                const result = await this.apiCall(`/mycut/api/project/${this.projectId}/export/status/`);

                if (result.status === 'completed') {
                    this.handleExportComplete(result);
                } else if (result.status === 'failed') {
                    this.handleExportError(result.error_message || 'Unbekannter Fehler');
                } else {
                    // Still processing
                    this.updateExportProgress(result.progress);
                    setTimeout(poll, 2000);
                }
            } catch (error) {
                console.error('Error polling export status:', error);
                // Retry nach Netzwerkfehler
                setTimeout(poll, 5000);
            }
        };

        poll();
    }

    handleExportComplete(result) {
        // Progress-UI aktualisieren
        this.updateExportProgress(100, 'Export abgeschlossen!');

        // Erfolgs-Benachrichtigung
        const sizeInfo = result.file_size_readable || '';
        this.showNotification('success', 'Export abgeschlossen!', `Video bereit (${sizeInfo})`);

        // Download-Button anzeigen
        const progressArea = document.getElementById('export-progress');
        if (progressArea) {
            progressArea.innerHTML = `
                <div class="alert alert-success mb-0">
                    <div class="d-flex align-items-center justify-content-between">
                        <div>
                            <i class="fas fa-check-circle me-2"></i>
                            <strong>Export abgeschlossen!</strong>
                            ${sizeInfo ? `<span class="text-muted ms-2">(${sizeInfo})</span>` : ''}
                        </div>
                        <div>
                            <a href="${result.download_url}" class="btn btn-success btn-sm" download>
                                <i class="fas fa-download me-1"></i> Herunterladen
                            </a>
                            <button onclick="editor.closeExportModal()" class="btn btn-outline-secondary btn-sm ms-2">
                                Schliessen
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        // Export-Button reaktivieren
        this.resetExportButton();
    }

    handleExportError(errorMessage) {
        this.updateExportProgress(0, 'Fehler!');

        // Fehler-Benachrichtigung
        this.showNotification('danger', 'Export fehlgeschlagen', errorMessage);

        // Fehler in Progress-Area anzeigen
        const progressArea = document.getElementById('export-progress');
        if (progressArea) {
            progressArea.innerHTML = `
                <div class="alert alert-danger mb-0">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <strong>Fehler:</strong> ${errorMessage}
                    <button onclick="editor.resetExportUI()" class="btn btn-outline-danger btn-sm ms-3">
                        Nochmal versuchen
                    </button>
                </div>
            `;
        }

        this.resetExportButton();
    }

    showExportProgress(show) {
        const progressArea = document.getElementById('export-progress');
        if (progressArea) {
            if (show) {
                progressArea.innerHTML = `
                    <div class="progress" style="height: 25px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated"
                             role="progressbar" style="width: 0%;">0%</div>
                    </div>
                    <small id="export-status" class="text-muted mt-1 d-block">Vorbereitung...</small>
                `;
                progressArea.classList.remove('d-none');
            } else {
                progressArea.classList.add('d-none');
            }
        }
    }

    updateExportProgress(progress, statusText = null) {
        const progressBar = document.querySelector('#export-progress .progress-bar');
        const statusEl = document.getElementById('export-status');

        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.textContent = progress + '%';
        }
        if (statusEl && statusText) {
            statusEl.textContent = statusText;
        }
    }

    resetExportButton() {
        const exportBtn = document.getElementById('start-export-btn');
        if (exportBtn) {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<i class="fas fa-download me-1"></i> Export starten';
        }
    }

    resetExportUI() {
        this.showExportProgress(true);
        this.updateExportProgress(0, 'Bereit zum Export');
        this.resetExportButton();
    }

    closeExportModal() {
        bootstrap.Modal.getInstance(document.getElementById('exportModal'))?.hide();
        this.resetExportUI();
    }

    // UI helpers
    updateTimeDisplay() {
        const current = document.getElementById('current-time');
        const total = document.getElementById('total-duration');

        if (current) {
            current.textContent = this.formatTime(this.video.currentTime * 1000);
        }
        if (total) {
            total.textContent = this.formatTime(this.video.duration * 1000);
        }
    }

    updateActiveSubtitle() {
        const currentTime = this.video.currentTime * 1000;
        const items = document.querySelectorAll('.subtitle-item');

        items.forEach(item => {
            const start = parseFloat(item.dataset.start);
            const end = parseFloat(item.dataset.end);

            if (currentTime >= start && currentTime <= end) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    renderSubtitlesList() {
        const container = document.getElementById('subtitles-list');
        if (!container) return;

        container.innerHTML = this.project.subtitles.map(sub => `
            <div class="subtitle-item" data-id="${sub.id}" data-start="${sub.start_time}" data-end="${sub.end_time}" onclick="editor.seekTo(${sub.start_time})">
                <div class="time">${this.formatTime(sub.start_time)} - ${this.formatTime(sub.end_time)}</div>
                <div>${sub.text}</div>
            </div>
        `).join('');
    }

    renderSuggestionsList() {
        const container = document.getElementById('suggestions-list');
        if (!container) return;

        const typeColors = {
            'filler_word': 'bg-warning text-dark',
            'silence': 'bg-info',
            'speed_up': 'bg-primary',
            'speed_down': 'bg-secondary'
        };

        container.innerHTML = this.project.suggestions.map(sug => `
            <div class="ai-suggestion" data-id="${sug.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <span class="badge ${typeColors[sug.suggestion_type] || 'bg-primary'}">${sug.suggestion_type}</span>
                    <small class="text-muted">${Math.round(sug.confidence * 100)}%</small>
                </div>
                <div class="mt-1 small">${sug.text || ''}</div>
                <div class="ai-suggestion-actions">
                    <button class="btn btn-xs btn-success" onclick="editor.applySuggestion(${sug.id})">
                        <i class="fas fa-check"></i>
                    </button>
                    <button class="btn btn-xs btn-danger" onclick="editor.rejectSuggestion(${sug.id})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    formatTime(ms) {
        if (isNaN(ms)) return '00:00:00';
        const hours = Math.floor(ms / 3600000);
        const minutes = Math.floor((ms % 3600000) / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    showProgress(message) {
        const progress = document.getElementById('ai-progress');
        const status = document.getElementById('ai-status');
        if (progress) progress.classList.remove('d-none');
        if (status) {
            status.textContent = message;
            status.classList.remove('text-success', 'text-danger');
            status.classList.add('text-warning');
        }
    }

    updateProgressBar(percent) {
        const progressBar = document.querySelector('#ai-progress .progress-bar');
        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.setAttribute('aria-valuenow', percent);
        }
    }

    showSuccess(message) {
        const status = document.getElementById('ai-status');
        if (status) {
            status.textContent = message;
            status.classList.remove('text-warning', 'text-danger');
            status.classList.add('text-success');
        }
        this.updateProgressBar(100);
    }

    showError(message) {
        const status = document.getElementById('ai-status');
        if (status) {
            status.textContent = message;
            status.classList.remove('text-warning', 'text-success');
            status.classList.add('text-danger');
        }
        this.updateProgressBar(0);
        console.error(message);
    }

    showNotification(type, title, message) {
        // Create toast notification
        const toastContainer = document.getElementById('toast-container') || this.createToastContainer();

        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'success' ? 'bg-success' : (type === 'error' ? 'bg-danger' : 'bg-info');

        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${title}</strong><br>
                        <small>${message}</small>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);

        const toastEl = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
        toast.show();

        // Remove after hidden
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }

    createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }

    // ===========================================
    // Undo/Redo System
    // ===========================================

    saveState(actionName = 'Aenderung') {
        if (this.isUndoing) return;

        // Aktuellen Zustand speichern
        const state = {
            action: actionName,
            timestamp: Date.now(),
            clips: JSON.parse(JSON.stringify(this.project.clips)),
            textOverlays: JSON.parse(JSON.stringify(this.project.textOverlays)),
        };

        // Alles nach aktuellem Index loeschen (bei neuer Aktion nach Undo)
        if (this.historyIndex < this.history.length - 1) {
            this.history = this.history.slice(0, this.historyIndex + 1);
        }

        this.history.push(state);
        this.historyIndex = this.history.length - 1;

        // Maximale Laenge einhalten
        if (this.history.length > this.maxHistoryLength) {
            this.history.shift();
            this.historyIndex--;
        }

        this.updateUndoRedoButtons();
    }

    undo() {
        if (this.historyIndex <= 0) {
            this.showNotification('info', 'Undo', 'Nichts mehr zum Rueckgaengig machen');
            return;
        }

        this.isUndoing = true;
        this.historyIndex--;

        const state = this.history[this.historyIndex];
        this.restoreState(state);

        this.isUndoing = false;
        this.updateUndoRedoButtons();
        this.showNotification('info', 'Rueckgaengig', state.action);
    }

    redo() {
        if (this.historyIndex >= this.history.length - 1) {
            this.showNotification('info', 'Redo', 'Nichts mehr zum Wiederherstellen');
            return;
        }

        this.isUndoing = true;
        this.historyIndex++;

        const state = this.history[this.historyIndex];
        this.restoreState(state);

        this.isUndoing = false;
        this.updateUndoRedoButtons();
        this.showNotification('info', 'Wiederherstellt', state.action);
    }

    restoreState(state) {
        this.project.clips = JSON.parse(JSON.stringify(state.clips));
        this.project.textOverlays = JSON.parse(JSON.stringify(state.textOverlays));

        // Timeline aktualisieren
        this.timeline.setClips([
            ...this.project.clips,
            ...this.project.subtitles.map(sub => ({
                id: 'sub_' + sub.id,
                clip_type: 'subtitle',
                start_time: sub.start_time,
                duration: sub.end_time - sub.start_time,
                text: sub.text
            })),
            ...this.project.textOverlays.map(overlay => ({
                id: 'overlay_' + overlay.id,
                clip_type: 'text_overlay',
                start_time: overlay.start_time,
                duration: overlay.end_time - overlay.start_time,
                text: overlay.text
            }))
        ]);

        this.hasUnsavedChanges = true;
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');

        if (undoBtn) {
            undoBtn.disabled = this.historyIndex <= 0;
        }
        if (redoBtn) {
            redoBtn.disabled = this.historyIndex >= this.history.length - 1;
        }
    }

    // ===========================================
    // Clip Properties Panel
    // ===========================================

    selectClip(clip) {
        this.selectedClip = clip;
        this.showClipProperties(clip);
    }

    showClipProperties(clip) {
        const panel = document.getElementById('clip-properties-panel');
        if (!panel) return;

        panel.classList.remove('d-none');

        // Felder fuellen
        document.getElementById('clip-speed').value = clip.speed || 1.0;
        document.getElementById('clip-speed-val').textContent = (clip.speed || 1.0).toFixed(2) + 'x';
        document.getElementById('clip-volume').value = (clip.volume || 1.0) * 100;
        document.getElementById('clip-volume-val').textContent = Math.round((clip.volume || 1.0) * 100) + '%';
        document.getElementById('clip-muted').checked = clip.is_muted || false;

        // Start/Ende anzeigen
        document.getElementById('clip-start').textContent = this.formatTime(clip.source_start);
        document.getElementById('clip-end').textContent = this.formatTime(clip.source_end);
        document.getElementById('clip-duration').textContent = this.formatTime(clip.duration);
    }

    hideClipProperties() {
        const panel = document.getElementById('clip-properties-panel');
        if (panel) {
            panel.classList.add('d-none');
        }
        this.selectedClip = null;
    }

    updateClipSpeed(speed) {
        if (!this.selectedClip) return;

        this.saveState('Geschwindigkeit geaendert');
        this.selectedClip.speed = parseFloat(speed);
        document.getElementById('clip-speed-val').textContent = speed + 'x';

        this.hasUnsavedChanges = true;
        this.updateClip(this.selectedClip);
    }

    updateClipVolume(volume) {
        if (!this.selectedClip) return;

        this.saveState('Lautstaerke geaendert');
        this.selectedClip.volume = volume / 100;
        document.getElementById('clip-volume-val').textContent = volume + '%';

        this.hasUnsavedChanges = true;
        this.updateClip(this.selectedClip);
    }

    toggleClipMute() {
        if (!this.selectedClip) return;

        this.saveState('Stummschaltung geaendert');
        this.selectedClip.is_muted = document.getElementById('clip-muted').checked;

        this.hasUnsavedChanges = true;
        this.updateClip(this.selectedClip);
    }

    // ===========================================
    // Text-Overlay Functions
    // ===========================================

    openTextOverlayModal(overlayId = null) {
        const modal = document.getElementById('textOverlayModal');
        const deleteBtn = document.getElementById('overlay-delete-btn');

        // Reset form
        document.getElementById('overlay-text').value = '';
        document.getElementById('overlay-start').value = Math.round(this.video.currentTime * 1000);
        document.getElementById('overlay-end').value = Math.round(this.video.currentTime * 1000) + 3000;
        document.getElementById('overlay-x').value = 50;
        document.getElementById('overlay-y').value = 50;
        document.getElementById('overlay-size').value = 48;
        document.getElementById('overlay-size-val').textContent = '48';
        document.getElementById('overlay-color').value = '#FFFFFF';
        document.getElementById('overlay-anim-in').value = 'fade_in';
        document.getElementById('overlay-anim-out').value = 'fade_out';
        document.getElementById('overlay-bold').checked = true;
        document.getElementById('overlay-shadow').checked = true;
        document.getElementById('overlay-edit-id').value = '';

        if (overlayId) {
            // Load existing overlay for editing
            const overlay = this.project.textOverlays.find(o => o.id === overlayId);
            if (overlay) {
                document.getElementById('overlay-text').value = overlay.text;
                document.getElementById('overlay-start').value = overlay.start_time;
                document.getElementById('overlay-end').value = overlay.end_time;
                document.getElementById('overlay-x').value = overlay.position_x;
                document.getElementById('overlay-y').value = overlay.position_y;
                if (overlay.style) {
                    document.getElementById('overlay-size').value = overlay.style.size || 48;
                    document.getElementById('overlay-size-val').textContent = overlay.style.size || 48;
                    document.getElementById('overlay-color').value = overlay.style.color || '#FFFFFF';
                    document.getElementById('overlay-bold').checked = overlay.style.bold !== false;
                    document.getElementById('overlay-shadow').checked = overlay.style.shadow !== false;
                }
                document.getElementById('overlay-anim-in').value = overlay.animation_in || 'fade_in';
                document.getElementById('overlay-anim-out').value = overlay.animation_out || 'fade_out';
                document.getElementById('overlay-edit-id').value = overlayId;
                deleteBtn.classList.remove('d-none');
            }
        } else {
            deleteBtn.classList.add('d-none');
        }

        this.updateOverlayPreview();
        this.setupOverlayModalListeners();

        new bootstrap.Modal(modal).show();
    }

    setupOverlayModalListeners() {
        const updatePreview = () => this.updateOverlayPreview();

        document.getElementById('overlay-text').addEventListener('input', updatePreview);
        document.getElementById('overlay-size').addEventListener('input', (e) => {
            document.getElementById('overlay-size-val').textContent = e.target.value;
            updatePreview();
        });
        document.getElementById('overlay-color').addEventListener('input', updatePreview);
        document.getElementById('overlay-bold').addEventListener('change', updatePreview);
        document.getElementById('overlay-shadow').addEventListener('change', updatePreview);
        document.getElementById('overlay-x').addEventListener('input', updatePreview);
        document.getElementById('overlay-y').addEventListener('input', updatePreview);
    }

    updateOverlayPreview() {
        const preview = document.getElementById('overlay-preview');
        const text = document.getElementById('overlay-text').value || 'Vorschau';
        const size = document.getElementById('overlay-size').value;
        const color = document.getElementById('overlay-color').value;
        const bold = document.getElementById('overlay-bold').checked;
        const shadow = document.getElementById('overlay-shadow').checked;
        const x = document.getElementById('overlay-x').value;
        const y = document.getElementById('overlay-y').value;

        preview.textContent = text;
        preview.style.fontSize = size + 'px';
        preview.style.color = color;
        preview.style.fontWeight = bold ? 'bold' : 'normal';
        preview.style.textShadow = shadow ? '2px 2px 4px rgba(0,0,0,0.8)' : 'none';
        preview.style.left = x + '%';
        preview.style.top = y + '%';
    }

    async saveTextOverlay() {
        const editId = document.getElementById('overlay-edit-id').value;
        const data = {
            text: document.getElementById('overlay-text').value,
            start_time: parseInt(document.getElementById('overlay-start').value),
            end_time: parseInt(document.getElementById('overlay-end').value),
            position_x: parseFloat(document.getElementById('overlay-x').value),
            position_y: parseFloat(document.getElementById('overlay-y').value),
            style: {
                font: 'Arial',
                size: parseInt(document.getElementById('overlay-size').value),
                color: document.getElementById('overlay-color').value,
                bold: document.getElementById('overlay-bold').checked,
                shadow: document.getElementById('overlay-shadow').checked,
            },
            animation_in: document.getElementById('overlay-anim-in').value,
            animation_out: document.getElementById('overlay-anim-out').value,
        };

        try {
            let result;
            if (editId) {
                result = await this.apiCall(`/mycut/api/project/${this.projectId}/text-overlays/${editId}/`, 'PUT', data);
            } else {
                result = await this.apiCall(`/mycut/api/project/${this.projectId}/text-overlays/`, 'POST', data);
            }

            if (result.success) {
                this.showNotification('success', 'Text-Overlay gespeichert', result.overlay.text);
                bootstrap.Modal.getInstance(document.getElementById('textOverlayModal')).hide();
                await this.loadProject();
            } else {
                this.showError('Fehler: ' + result.error);
            }
        } catch (error) {
            this.showError('Fehler beim Speichern: ' + error.message);
        }
    }

    async deleteTextOverlay() {
        const editId = document.getElementById('overlay-edit-id').value;
        if (!editId) return;

        if (!confirm('Text-Overlay wirklich loeschen?')) return;

        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/text-overlays/${editId}/`, 'DELETE');

            if (result.success) {
                this.showNotification('success', 'Text-Overlay geloescht', '');
                bootstrap.Modal.getInstance(document.getElementById('textOverlayModal')).hide();
                await this.loadProject();
            } else {
                this.showError('Fehler: ' + result.error);
            }
        } catch (error) {
            this.showError('Fehler beim Loeschen: ' + error.message);
        }
    }

    // API helper
    async apiCall(endpoint, method = 'GET', data = null) {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(endpoint, options);
        return response.json();
    }

    // Zoom controls (exposed for buttons)
    zoomIn() {
        this.timeline?.zoomIn();
    }

    zoomOut() {
        this.timeline?.zoomOut();
    }

    zoomToFit() {
        this.timeline?.zoomToFit();
    }
}

// Export for use
window.MyCutEditor = MyCutEditor;
