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
            this.hasUnsavedChanges = true;
            this.updateClip(clip);
        };

        this.timeline.onClipTrimmed = (clip) => {
            this.hasUnsavedChanges = true;
            this.updateClip(clip);
        };

        this.timeline.onClipSplit = (original, newClip) => {
            this.hasUnsavedChanges = true;
            this.project.clips.push(newClip);
            this.saveClips();
        };

        this.timeline.onClipDeleted = (clip) => {
            this.hasUnsavedChanges = true;
            this.deleteClip(clip.id);
        };

        this.timeline.onClipDoubleClick = (clip) => {
            this.editClip(clip);
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
                        this.undo();
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
            if (result.success) {
                this.project.clips = result.clips || [];
                this.project.subtitles = result.subtitles || [];
                this.project.suggestions = result.suggestions || [];

                this.timeline.setClips(this.project.clips);
                this.renderSubtitlesList();
                this.renderSuggestionsList();
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
        if (!confirm('Transkription starten? Dies kann einige Minuten dauern.')) return;

        this.showProgress('Transkribiere Audio...');

        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/transcribe/`, 'POST');

            if (result.success) {
                this.showSuccess(`Fertig! ${result.segments} Segmente erkannt.`);
                setTimeout(() => location.reload(), 1500);
            } else {
                this.showError('Fehler: ' + result.error);
            }
        } catch (error) {
            this.showError('Fehler bei der Transkription');
        }
    }

    async startAnalysis() {
        this.showProgress('Analysiere fuer Auto-Edit...');

        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/analyze/`, 'POST');

            if (result.success) {
                this.showSuccess(`${result.filler_words} Fuellwoerter, ${result.silences} Pausen gefunden.`);
                setTimeout(() => location.reload(), 2000);
            } else {
                this.showError('Fehler: ' + result.error);
            }
        } catch (error) {
            this.showError('Fehler bei der Analyse');
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

        try {
            const result = await this.apiCall(`/mycut/api/project/${this.projectId}/export/`, 'POST', {
                quality, format, burn_subtitles: burnSubtitles
            });

            if (result.success) {
                this.showSuccess('Export gestartet! Du wirst benachrichtigt, wenn er fertig ist.');
                bootstrap.Modal.getInstance(document.getElementById('exportModal'))?.hide();
                this.pollExportStatus(result.job_id);
            } else {
                this.showError('Fehler: ' + result.error);
            }
        } catch (error) {
            this.showError('Fehler beim Starten des Exports');
        }
    }

    async pollExportStatus(jobId) {
        const poll = async () => {
            try {
                const result = await this.apiCall(`/mycut/api/project/${this.projectId}/export/status/?job_id=${jobId}`);
                if (result.status === 'completed') {
                    this.showSuccess('Export abgeschlossen!');
                    if (result.download_url) {
                        window.open(result.download_url, '_blank');
                    }
                } else if (result.status === 'failed') {
                    this.showError('Export fehlgeschlagen: ' + result.error);
                } else {
                    // Still processing
                    this.updateExportProgress(result.progress);
                    setTimeout(poll, 2000);
                }
            } catch (error) {
                console.error('Error polling export status:', error);
            }
        };

        poll();
    }

    updateExportProgress(progress) {
        const progressBar = document.querySelector('#export-progress .progress-bar');
        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.textContent = progress + '%';
        }
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
        if (status) status.textContent = message;
    }

    showSuccess(message) {
        const status = document.getElementById('ai-status');
        if (status) {
            status.textContent = message;
            status.classList.add('text-success');
        }
    }

    showError(message) {
        const status = document.getElementById('ai-status');
        if (status) {
            status.textContent = message;
            status.classList.add('text-danger');
        }
        console.error(message);
    }

    undo() {
        // Placeholder for undo functionality
        console.log('Undo not implemented yet');
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
