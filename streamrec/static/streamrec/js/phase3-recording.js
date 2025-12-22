/**
 * StreamRec Phase 3: Recording Engine with MediaRecorder API
 * Advanced recording functionality with duration limits and export
 */

class RecordingEngine {
    constructor(streamRecorder) {
        this.streamRecorder = streamRecorder;
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.isRecording = false;
        this.isPaused = false;
        this.startTime = null;
        this.pausedDuration = 0;
        this.maxDuration = 180000; // 3 minutes in milliseconds
        this.timer = null;
        this.durationDisplay = null;
        
        this.setupRecordingControls();
        this.checkMediaRecorderSupport();
    }

    checkMediaRecorderSupport() {
        if (!window.MediaRecorder) {
            console.error('❌ MediaRecorder API nicht unterstützt');
            this.showUnsupportedError();
            return false;
        }

        // Check supported MIME types
        const supportedTypes = [
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus', 
            'video/webm;codecs=h264,opus',
            'video/webm',
            'video/mp4;codecs=h264,aac',
            'video/mp4'
        ];

        this.supportedMimeType = supportedTypes.find(type => 
            MediaRecorder.isTypeSupported(type)
        );

        if (!this.supportedMimeType) {
            console.error('❌ Kein unterstütztes Video-Format gefunden');
            return false;
        }

        console.log(`✅ MediaRecorder unterstützt: ${this.supportedMimeType}`);
        return true;
    }

    setupRecordingControls() {
        const recordingControlsHTML = `
            <div class="recording-controls mt-4">
                <div class="card border-0 shadow-sm">
                    <div class="card-header bg-danger text-white">
                        <h6 class="mb-0">
                            <i class="fas fa-record-vinyl me-2"></i>
                            Aufnahme Kontrolle
                        </h6>
                    </div>
                    <div class="card-body">
                        <!-- Recording Status -->
                        <div class="recording-status text-center mb-4">
                            <div class="status-indicator" id="recordingStatusIndicator">
                                <i class="fas fa-circle text-secondary me-2"></i>
                                <span id="recordingStatusText">Bereit</span>
                            </div>
                            <div class="duration-display mt-2">
                                <div class="duration-timer" id="durationTimer">00:00</div>
                                <div class="duration-bar-container">
                                    <div class="progress" style="height: 6px;">
                                        <div class="progress-bar bg-danger" id="durationProgress" 
                                             role="progressbar" style="width: 0%"></div>
                                    </div>
                                </div>
                                <small class="text-muted">Maximum: 03:00</small>
                            </div>
                        </div>

                        <!-- Recording Controls -->
                        <div class="recording-buttons d-flex justify-content-center gap-3 mb-3">
                            <button id="startRecordingBtn" class="btn btn-danger btn-lg px-4" disabled>
                                <i class="fas fa-record-vinyl me-2"></i>
                                Aufnahme starten
                            </button>
                            <button id="pauseRecordingBtn" class="btn btn-warning btn-lg px-4" disabled>
                                <i class="fas fa-pause me-2"></i>
                                Pausieren
                            </button>
                            <button id="stopRecordingBtn" class="btn btn-dark btn-lg px-4" disabled>
                                <i class="fas fa-stop me-2"></i>
                                Stoppen
                            </button>
                        </div>

                        <!-- Recording Settings -->
                        <div class="recording-settings">
                            <div class="row">
                                <div class="col-md-6">
                                    <label class="form-label">Video-Qualität:</label>
                                    <select class="form-select" id="videoQuality">
                                        <option value="high">Hoch (8 Mbps)</option>
                                        <option value="medium" selected>Mittel (4 Mbps)</option>
                                        <option value="low">Niedrig (2 Mbps)</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Audio-Qualität:</label>
                                    <select class="form-select" id="audioQuality">
                                        <option value="high">Hoch (192 kbps)</option>
                                        <option value="medium" selected>Mittel (128 kbps)</option>
                                        <option value="low">Niedrig (96 kbps)</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Export Section (initially hidden) -->
                        <div class="export-section mt-4" id="exportSection" style="display: none;">
                            <hr>
                            <h6 class="text-success mb-3">
                                <i class="fas fa-check-circle me-2"></i>
                                Aufnahme abgeschlossen
                            </h6>
                            <div class="export-info mb-3">
                                <div class="row text-center">
                                    <div class="col-4">
                                        <div class="export-stat">
                                            <h5 id="recordedDuration" class="text-primary mb-0">--:--</h5>
                                            <small class="text-muted">Dauer</small>
                                        </div>
                                    </div>
                                    <div class="col-4">
                                        <div class="export-stat">
                                            <h5 id="recordedSize" class="text-info mb-0">-- MB</h5>
                                            <small class="text-muted">Dateigröße</small>
                                        </div>
                                    </div>
                                    <div class="col-4">
                                        <div class="export-stat">
                                            <h5 id="recordedFormat" class="text-success mb-0">WebM</h5>
                                            <small class="text-muted">Format</small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="export-actions d-grid gap-2 d-md-flex justify-content-md-center">
                                <button id="downloadVideoBtn" class="btn btn-success btn-lg px-4">
                                    <i class="fas fa-download me-2"></i>
                                    Video herunterladen
                                </button>
                                <button id="previewVideoBtn" class="btn btn-outline-primary btn-lg px-4">
                                    <i class="fas fa-play me-2"></i>
                                    Vorschau
                                </button>
                                <button id="newRecordingBtn" class="btn btn-outline-secondary btn-lg px-4">
                                    <i class="fas fa-redo me-2"></i>
                                    Neue Aufnahme
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Prefer dedicated container in enhanced template, fallback to left control panel
        const container = document.getElementById('recordingControlsContainer');
        if (container) {
            container.innerHTML = recordingControlsHTML;
        } else {
            const controlPanel = document.querySelector('.col-12.col-xl-4, .col-12.col-lg-4');
            if (controlPanel) {
                controlPanel.insertAdjacentHTML('beforeend', recordingControlsHTML);
            } else {
                document.body.insertAdjacentHTML('beforeend', recordingControlsHTML);
            }
        }

        this.setupRecordingEventListeners();
    }

    setupRecordingEventListeners() {
        // Recording control buttons
        document.getElementById('startRecordingBtn')?.addEventListener('click', () => {
            this.startRecording();
        });

        document.getElementById('pauseRecordingBtn')?.addEventListener('click', () => {
            if (this.isPaused) {
                this.resumeRecording();
            } else {
                this.pauseRecording();
            }
        });

        document.getElementById('stopRecordingBtn')?.addEventListener('click', () => {
            this.stopRecording();
        });

        // Export buttons
        document.getElementById('downloadVideoBtn')?.addEventListener('click', () => {
            this.downloadRecording();
        });

        document.getElementById('previewVideoBtn')?.addEventListener('click', () => {
            this.previewRecording();
        });

        document.getElementById('newRecordingBtn')?.addEventListener('click', () => {
            this.resetRecording();
        });

        // Listen for composition changes to enable/disable recording
        document.addEventListener('compositionStateChanged', (e) => {
            this.updateRecordingAvailability(e.detail.isComposing);
        });
    }

    updateRecordingAvailability(canRecord) {
        const startBtn = document.getElementById('startRecordingBtn');
        if (startBtn) {
            startBtn.disabled = !canRecord || this.isRecording;
            
            if (!canRecord) {
                this.updateStatus('Keine Komposition aktiv', 'secondary');
            } else if (!this.isRecording) {
                this.updateStatus('Bereit', 'secondary');
            }
        }
    }

    async startRecording() {
        try {
            // Get the composition stream from canvas
            const compositionStream = this.streamRecorder.getCompositionStream();
            if (!compositionStream) {
                throw new Error('Keine Kompositions-Stream verfügbar');
            }

            // Get recording quality settings
            const videoQuality = document.getElementById('videoQuality').value;
            const audioQuality = document.getElementById('audioQuality').value;

            const options = this.getRecordingOptions(videoQuality, audioQuality);
            
            // Create MediaRecorder
            this.mediaRecorder = new MediaRecorder(compositionStream, options);
            this.recordedChunks = [];

            // Setup event handlers
            this.setupMediaRecorderEvents();

            // Start recording - WICHTIG: Kürzeres Intervall für flüssigere Aufnahme
            // 100ms statt 1000ms verhindert Ruckeln und Frame-Verlust
            this.mediaRecorder.start(100); // Collect data every 100ms for smooth playback
            
            this.isRecording = true;
            this.isPaused = false;
            this.startTime = Date.now();
            this.pausedDuration = 0;
            
            // Update UI
            this.updateStatus('Aufnahme läuft', 'danger');
            // während der Aufnahme: Start deaktiviert, Pause & Stop aktiv
            this.updateRecordingButtons(false, true, true);
            this.startDurationTimer();
            
            // Set maximum duration timeout
            setTimeout(() => {
                if (this.isRecording && !this.isPaused) {
                    this.stopRecording();
                }
            }, this.maxDuration);

            console.log('🎬 Aufnahme gestartet');
            
        } catch (error) {
            console.error('❌ Aufnahme-Start fehlgeschlagen:', error);
            this.showRecordingError('Aufnahme konnte nicht gestartet werden', error.message);
        }
    }

    pauseRecording() {
        if (this.mediaRecorder && this.isRecording && !this.isPaused) {
            this.mediaRecorder.pause();
            this.isPaused = true;
            
            this.updateStatus('Aufnahme pausiert', 'warning');
            // im Pause-Zustand: Start deaktiviert, Fortsetzen (Pause-Button aktiv) & Stop aktiv
            this.updateRecordingButtons(false, true, true);
            this.pauseDurationTimer();
            
            // Update pause button text
            const pauseBtn = document.getElementById('pauseRecordingBtn');
            pauseBtn.innerHTML = '<i class="fas fa-play me-2"></i>Fortsetzen';
            
            console.log('⏸️ Aufnahme pausiert');
        }
    }

    resumeRecording() {
        if (this.mediaRecorder && this.isRecording && this.isPaused) {
            this.mediaRecorder.resume();
            this.isPaused = false;
            
            this.updateStatus('Aufnahme läuft', 'danger');
            // nach Fortsetzen: Pause & Stop aktiv lassen
            this.updateRecordingButtons(false, true, true);
            this.resumeDurationTimer();
            
            // Update pause button text
            const pauseBtn = document.getElementById('pauseRecordingBtn');
            pauseBtn.innerHTML = '<i class="fas fa-pause me-2"></i>Pausieren';
            
            console.log('▶️ Aufnahme fortgesetzt');
        }
    }

    stopRecording() {
        return new Promise((resolve) => {
            if (this.mediaRecorder && this.isRecording) {
                this.mediaRecorder.onstop = () => {
                    this.finalizeRecording();
                    resolve();
                };
                
                this.mediaRecorder.stop();
                this.isRecording = false;
                this.isPaused = false;
                
                this.updateStatus('Aufnahme gestoppt', 'dark');
                // nach Stopp: Start wieder aktivieren, Pause/Stop deaktivieren
                this.updateRecordingButtons(true, false, false);
                this.stopDurationTimer();
                
                console.log('🛑 Aufnahme gestoppt');
            } else {
                resolve();
            }
        });
    }

    setupMediaRecorderEvents() {
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.recordedChunks.push(event.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            this.finalizeRecording();
        };

        this.mediaRecorder.onerror = (event) => {
            console.error('❌ MediaRecorder Fehler:', event);
            this.showRecordingError('Aufnahme-Fehler', 'Ein unbekannter Fehler ist aufgetreten');
        };

        this.mediaRecorder.onpause = () => {
            console.log('⏸️ MediaRecorder pausiert');
        };

        this.mediaRecorder.onresume = () => {
            console.log('▶️ MediaRecorder fortgesetzt');
        };
    }

    getRecordingOptions(videoQuality, audioQuality) {
        const videoBitrates = {
            high: 8000000,   // 8 Mbps
            medium: 4000000, // 4 Mbps  
            low: 2000000     // 2 Mbps
        };

        const audioBitrates = {
            high: 192000,    // 192 kbps
            medium: 128000,  // 128 kbps
            low: 96000       // 96 kbps
        };

        return {
            mimeType: this.supportedMimeType,
            videoBitsPerSecond: videoBitrates[videoQuality] || videoBitrates.medium,
            audioBitsPerSecond: audioBitrates[audioQuality] || audioBitrates.medium
        };
    }

    finalizeRecording() {
        if (this.recordedChunks.length === 0) {
            console.warn('⚠️ Keine Aufnahme-Daten vorhanden');
            return;
        }

        // Create blob from recorded chunks
        this.recordedBlob = new Blob(this.recordedChunks, {
            type: this.supportedMimeType
        });

        // Calculate recording statistics
        const duration = this.getCurrentRecordingDuration();
        const sizeInMB = (this.recordedBlob.size / (1024 * 1024)).toFixed(2);
        const format = this.supportedMimeType.includes('webm') ? 'WebM' : 'MP4';

        // Update export section
        document.getElementById('recordedDuration').textContent = this.formatDuration(duration);
        document.getElementById('recordedSize').textContent = `${sizeInMB} MB`;
        document.getElementById('recordedFormat').textContent = format;

        // Show export section
        document.getElementById('exportSection').style.display = 'block';

        // Create preview URL
        this.recordedUrl = URL.createObjectURL(this.recordedBlob);

        console.log(`✅ Aufnahme abgeschlossen: ${sizeInMB} MB, ${this.formatDuration(duration)}`);
    }

    downloadRecording() {
        if (!this.recordedBlob) return;

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const extension = this.supportedMimeType.includes('webm') ? 'webm' : 'mp4';
        const filename = `StreamRec_Aufnahme_${timestamp}.${extension}`;

        const a = document.createElement('a');
        a.href = this.recordedUrl;
        a.download = filename;
        a.click();

        console.log(`📥 Video heruntergeladen: ${filename}`);
    }

    previewRecording() {
        if (!this.recordedUrl) return;

        // Create modal for preview
        const previewModal = `
            <div class="modal fade" id="previewModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-play me-2"></i>Aufnahme Vorschau
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <video controls style="max-width: 100%; max-height: 400px;">
                                <source src="${this.recordedUrl}" type="${this.supportedMimeType}">
                                Ihr Browser unterstützt das Video-Element nicht.
                            </video>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Schließen</button>
                            <button type="button" class="btn btn-success" onclick="window.streamRecorder.recordingEngine.downloadRecording()">
                                <i class="fas fa-download me-2"></i>Herunterladen
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal and add new one
        document.querySelector('#previewModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', previewModal);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('previewModal'));
        modal.show();

        console.log('🎥 Vorschau angezeigt');
    }

    resetRecording() {
        // Clean up previous recording
        if (this.recordedUrl) {
            URL.revokeObjectURL(this.recordedUrl);
        }

        this.recordedBlob = null;
        this.recordedUrl = null;
        this.recordedChunks = [];

        // Reset UI
        document.getElementById('exportSection').style.display = 'none';
        document.getElementById('durationTimer').textContent = '00:00';
        document.getElementById('durationProgress').style.width = '0%';
        
        this.updateStatus('Bereit', 'secondary');
        this.updateRecordingButtons(false, false, false);

        console.log('🔄 Aufnahme zurückgesetzt');
    }

    startDurationTimer() {
        this.timer = setInterval(() => {
            this.updateDurationDisplay();
        }, 1000);
    }

    pauseDurationTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    resumeDurationTimer() {
        this.startDurationTimer();
    }

    stopDurationTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    updateDurationDisplay() {
        const currentDuration = this.getCurrentRecordingDuration();
        const progress = Math.min((currentDuration / this.maxDuration) * 100, 100);

        document.getElementById('durationTimer').textContent = this.formatDuration(currentDuration);
        document.getElementById('durationProgress').style.width = `${progress}%`;

        // Warning when approaching limit
        if (progress > 90) {
            document.getElementById('durationProgress').className = 'progress-bar bg-warning';
        } else if (progress > 95) {
            document.getElementById('durationProgress').className = 'progress-bar bg-danger';
        }
    }

    getCurrentRecordingDuration() {
        if (!this.startTime) return 0;
        return Date.now() - this.startTime - this.pausedDuration;
    }

    formatDuration(milliseconds) {
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    updateStatus(message, variant) {
        const indicator = document.getElementById('recordingStatusIndicator');
        const text = document.getElementById('recordingStatusText');
        
        if (indicator && text) {
            indicator.className = `status-indicator`;
            indicator.innerHTML = `<i class="fas fa-circle text-${variant} me-2"></i>`;
            text.textContent = message;
        }
    }

    updateRecordingButtons(canStart, canPause, canStop) {
        document.getElementById('startRecordingBtn').disabled = !canStart;
        document.getElementById('pauseRecordingBtn').disabled = !canPause;
        document.getElementById('stopRecordingBtn').disabled = !canStop;
    }

    showRecordingError(title, message) {
        const errorAlert = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>${title}:</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        const container = document.querySelector('.recording-controls .card-body');
        if (container) {
            container.insertAdjacentHTML('afterbegin', errorAlert);
        }
    }

    showUnsupportedError() {
        const errorHtml = `
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle me-2"></i>Browser nicht unterstützt</h6>
                <p class="mb-0">
                    Ihr Browser unterstützt die MediaRecorder API nicht. 
                    Bitte verwenden Sie Chrome 90+, Firefox 88+ oder Safari 14+ für die Aufnahme-Funktionalität.
                </p>
            </div>
        `;

        const controlPanel = document.querySelector('.col-12.col-lg-4');
        if (controlPanel) {
            controlPanel.insertAdjacentHTML('beforeend', errorHtml);
        }
    }
}

// Export for use in main StreamRecorder
window.RecordingEngine = RecordingEngine;
