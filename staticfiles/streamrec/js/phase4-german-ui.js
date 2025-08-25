/**
 * StreamRec Phase 4: Advanced German UI & Export Features
 * Complete German localization and enhanced user experience
 */

class GermanUI {
    constructor(streamRecorder) {
        this.streamRecorder = streamRecorder;
        this.notifications = new Map();
        this.helpSystem = null;
        this.accessibility = null;
        
        this.initializeGermanLocalization();
        this.setupNotificationSystem();
        this.initializeHelpSystem();
        this.setupAccessibilityFeatures();
        this.enhanceUserExperience();
    }

    initializeGermanLocalization() {
        // German text constants
        this.germanTexts = {
            // Status messages
            status: {
                ready: 'Bereit für Aufnahme',
                starting: 'Wird gestartet...',
                active: 'Aktiv',
                stopping: 'Wird gestoppt...',
                inactive: 'Nicht aktiv',
                error: 'Fehler aufgetreten',
                recording: 'Aufnahme läuft',
                paused: 'Pausiert',
                completed: 'Abgeschlossen'
            },

            // Error messages
            errors: {
                cameraAccess: 'Kamera-Zugriff wurde verweigert. Bitte erlauben Sie den Zugriff in den Browser-Einstellungen.',
                screenCapture: 'Bildschirm-Aufnahme fehlgeschlagen. Möglicherweise wurde der Zugriff verweigert.',
                noStreams: 'Keine aktiven Video-Streams gefunden. Bitte starten Sie mindestens eine Kamera oder Bildschirm-Aufnahme.',
                recordingFailed: 'Aufnahme konnte nicht gestartet werden. Bitte prüfen Sie Ihre Browser-Einstellungen.',
                exportFailed: 'Video-Export fehlgeschlagen. Bitte versuchen Sie es erneut.',
                browserNotSupported: 'Ihr Browser unterstützt diese Funktion nicht vollständig.',
                microphoneAccess: 'Mikrofon-Zugriff verweigert. Audio wird nicht aufgenommen.',
                networkError: 'Netzwerk-Fehler aufgetreten.',
                storageQuota: 'Nicht genügend Speicherplatz verfügbar.'
            },

            // Success messages  
            success: {
                streamStarted: 'Stream erfolgreich gestartet',
                recordingStarted: 'Aufnahme erfolgreich gestartet',
                recordingStopped: 'Aufnahme beendet',
                videoExported: 'Video erfolgreich exportiert',
                settingsSaved: 'Einstellungen gespeichert',
                layoutApplied: 'Layout angewendet'
            },

            // Instructions
            instructions: {
                firstUse: 'Willkommen bei StreamRec! Starten Sie zunächst Ihre Kamera oder Bildschirm-Aufnahme.',
                selectLayout: 'Wählen Sie ein Layout aus oder erstellen Sie Ihr eigenes.',
                startRecording: 'Klicken Sie auf "Aufnahme starten" um mit der Aufzeichnung zu beginnen.',
                downloadReady: 'Ihr Video ist bereit zum Herunterladen!',
                qualitySettings: 'Passen Sie die Qualitäts-Einstellungen vor der Aufnahme an.',
                durationLimit: 'Maximale Aufnahmedauer: 3 Minuten'
            },

            // Button labels
            buttons: {
                start: 'Starten',
                stop: 'Stoppen', 
                pause: 'Pausieren',
                resume: 'Fortsetzen',
                download: 'Herunterladen',
                preview: 'Vorschau',
                settings: 'Einstellungen',
                help: 'Hilfe',
                close: 'Schließen',
                save: 'Speichern',
                cancel: 'Abbrechen',
                retry: 'Wiederholen',
                reset: 'Zurücksetzen'
            },

            // Quality settings
            quality: {
                high: 'Hoch',
                medium: 'Mittel', 
                low: 'Niedrig',
                auto: 'Automatisch'
            },

            // Help topics
            help: {
                gettingStarted: 'Erste Schritte',
                streamSetup: 'Stream-Einrichtung',
                layoutCustomization: 'Layout-Anpassung',
                recording: 'Aufnahme',
                export: 'Video-Export',
                troubleshooting: 'Fehlerbehebung',
                shortcuts: 'Tastenkürzel',
                privacy: 'Datenschutz'
            }
        };

        // Apply localization to existing elements
        this.updateExistingTexts();
    }

    updateExistingTexts() {
        // Update button texts
        const buttonMappings = {
            'startCameraBtn': 'Kamera starten',
            'stopCameraBtn': 'Kamera stoppen',
            'startScreenBtn': 'Bildschirm teilen', 
            'stopScreenBtn': 'Bildschirm stoppen',
            'startCompositionBtn': 'Komposition starten',
            'stopCompositionBtn': 'Komposition stoppen',
            'startRecordingBtn': 'Aufnahme starten',
            'pauseRecordingBtn': 'Pausieren',
            'stopRecordingBtn': 'Stoppen',
            'downloadVideoBtn': 'Video herunterladen',
            'previewVideoBtn': 'Vorschau ansehen',
            'newRecordingBtn': 'Neue Aufnahme'
        };

        Object.entries(buttonMappings).forEach(([id, text]) => {
            const element = document.getElementById(id);
            if (element) {
                const icon = element.querySelector('i');
                const iconHtml = icon ? icon.outerHTML + ' ' : '';
                element.innerHTML = iconHtml + text;
            }
        });
    }

    setupNotificationSystem() {
        // Create notification container
        const notificationContainer = `
            <div id="notificationContainer" class="position-fixed top-0 end-0 p-3" style="z-index: 1060;">
                <!-- Dynamic notifications will be added here -->
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', notificationContainer);
    }

    showNotification(type, title, message, duration = 5000) {
        const notificationId = 'notification-' + Date.now();
        const iconMap = {
            success: 'check-circle',
            error: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };

        const colorMap = {
            success: 'success',
            error: 'danger', 
            warning: 'warning',
            info: 'primary'
        };

        const notificationHtml = `
            <div id="${notificationId}" class="toast show align-items-center text-bg-${colorMap[type]} border-0 mb-2" 
                 role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center">
                        <i class="fas fa-${iconMap[type]} me-2"></i>
                        <div>
                            <strong>${title}</strong>
                            ${message ? `<div class="small">${message}</div>` : ''}
                        </div>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                            onclick="this.parentElement.parentElement.remove()"></button>
                </div>
            </div>
        `;

        const container = document.getElementById('notificationContainer');
        container.insertAdjacentHTML('beforeend', notificationHtml);

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                document.getElementById(notificationId)?.remove();
            }, duration);
        }

        return notificationId;
    }

    initializeHelpSystem() {
        const helpButton = `
            <button id="helpBtn" class="btn btn-outline-info position-fixed" 
                    style="bottom: 20px; right: 20px; z-index: 1050; border-radius: 50%; width: 60px; height: 60px;"
                    title="Hilfe">
                <i class="fas fa-question fa-lg"></i>
            </button>
        `;

        document.body.insertAdjacentHTML('beforeend', helpButton);

        document.getElementById('helpBtn').addEventListener('click', () => {
            this.showHelpModal();
        });

        this.createHelpContent();
    }

    createHelpContent() {
        this.helpContent = {
            'getting-started': {
                title: 'Erste Schritte mit StreamRec',
                content: `
                    <div class="help-content">
                        <h6>📹 Willkommen bei StreamRec!</h6>
                        <p>Folgen Sie diesen einfachen Schritten für Ihre erste Aufnahme:</p>
                        <ol>
                            <li><strong>Stream starten:</strong> Klicken Sie auf "Kamera starten" oder "Bildschirm teilen"</li>
                            <li><strong>Layout wählen:</strong> Wählen Sie ein passendes Layout für Ihre Streams</li>
                            <li><strong>Komposition aktivieren:</strong> Starten Sie die Live-Vorschau</li>
                            <li><strong>Aufnahme beginnen:</strong> Klicken Sie auf "Aufnahme starten"</li>
                            <li><strong>Video herunterladen:</strong> Nach der Aufnahme können Sie Ihr Video speichern</li>
                        </ol>
                        <div class="alert alert-info">
                            <i class="fas fa-lightbulb me-2"></i>
                            <strong>Tipp:</strong> Stellen Sie sicher, dass Sie in einem ruhigen Umfeld aufnehmen und eine gute Internetverbindung haben.
                        </div>
                    </div>
                `
            },
            'stream-setup': {
                title: 'Stream-Einrichtung',
                content: `
                    <div class="help-content">
                        <h6>🎥 Kamera-Stream</h6>
                        <ul>
                            <li>Erlauben Sie den Kamera-Zugriff wenn Sie dazu aufgefordert werden</li>
                            <li>Wählen Sie die gewünschte Kamera aus (falls mehrere vorhanden)</li>
                            <li>Achten Sie auf gute Beleuchtung für beste Bildqualität</li>
                        </ul>
                        
                        <h6>🖥️ Bildschirm-Stream</h6>
                        <ul>
                            <li>Wählen Sie zwischen gesamtem Bildschirm oder einzelnem Anwendungsfenster</li>
                            <li>Entscheiden Sie, ob Audio mitaufgenommen werden soll</li>
                            <li>Schließen Sie unnötige Anwendungen für beste Performance</li>
                        </ul>

                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            <strong>Hinweis:</strong> Bei mehreren Monitoren können Sie jeden separat auswählen.
                        </div>
                    </div>
                `
            },
            'recording-tips': {
                title: 'Aufnahme-Tipps',
                content: `
                    <div class="help-content">
                        <h6>⚡ Performance-Tipps</h6>
                        <ul>
                            <li>Schließen Sie andere resource-intensive Anwendungen</li>
                            <li>Verwenden Sie "Mittel" Qualität für beste Balance zwischen Größe und Qualität</li>
                            <li>Starten Sie die Aufnahme erst nach dem Kompositions-Start</li>
                        </ul>
                        
                        <h6>🎬 Aufnahme-Qualität</h6>
                        <ul>
                            <li><strong>Hoch:</strong> Beste Qualität, große Dateigröße</li>
                            <li><strong>Mittel:</strong> Gute Balance (empfohlen)</li>
                            <li><strong>Niedrig:</strong> Kleinere Dateigröße, reduzierte Qualität</li>
                        </ul>

                        <div class="alert alert-success">
                            <i class="fas fa-check-circle me-2"></i>
                            <strong>Empfehlung:</strong> Testen Sie verschiedene Einstellungen um die beste Balance für Ihren Anwendungsfall zu finden.
                        </div>
                    </div>
                `
            },
            'troubleshooting': {
                title: 'Fehlerbehebung',
                content: `
                    <div class="help-content">
                        <h6>🚫 Häufige Probleme</h6>
                        
                        <div class="mb-3">
                            <strong>Kamera funktioniert nicht:</strong>
                            <ul>
                                <li>Prüfen Sie ob andere Anwendungen die Kamera verwenden</li>
                                <li>Erlauben Sie den Kamera-Zugriff in den Browser-Einstellungen</li>
                                <li>Starten Sie den Browser neu</li>
                            </ul>
                        </div>

                        <div class="mb-3">
                            <strong>Bildschirm-Aufnahme fehlgeschlagen:</strong>
                            <ul>
                                <li>Klicken Sie auf "Bildschirm teilen" und wählen Sie eine Option</li>
                                <li>Prüfen Sie Browser-Berechtigungen für Bildschirmfreigabe</li>
                                <li>Verwenden Sie einen unterstützten Browser</li>
                            </ul>
                        </div>

                        <div class="mb-3">
                            <strong>Aufnahme startet nicht:</strong>
                            <ul>
                                <li>Stellen Sie sicher, dass mindestens ein Stream aktiv ist</li>
                                <li>Starten Sie die Komposition vor der Aufnahme</li>
                                <li>Prüfen Sie verfügbaren Speicherplatz</li>
                            </ul>
                        </div>

                        <div class="alert alert-info">
                            <i class="fas fa-globe me-2"></i>
                            <strong>Browser-Kompatibilität:</strong> Chrome 90+, Firefox 88+, Safari 14+
                        </div>
                    </div>
                `
            }
        };
    }

    showHelpModal() {
        const helpModal = `
            <div class="modal fade" id="helpModal" tabindex="-1" aria-labelledby="helpModalLabel">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-info text-white">
                            <h5 class="modal-title" id="helpModalLabel">
                                <i class="fas fa-question-circle me-2"></i>StreamRec Hilfe
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-4">
                                    <div class="list-group" id="helpTopics">
                                        ${Object.entries(this.helpContent).map(([key, topic]) => `
                                            <a href="#" class="list-group-item list-group-item-action help-topic" data-topic="${key}">
                                                ${topic.title}
                                            </a>
                                        `).join('')}
                                    </div>
                                </div>
                                <div class="col-md-8">
                                    <div id="helpContentArea">
                                        <div class="text-center text-muted">
                                            <i class="fas fa-arrow-left fa-2x mb-3"></i>
                                            <p>Wählen Sie ein Thema aus der Liste</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Schließen</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal and add new one
        document.querySelector('#helpModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', helpModal);

        // Add event listeners
        document.querySelectorAll('.help-topic').forEach(topic => {
            topic.addEventListener('click', (e) => {
                e.preventDefault();
                const topicKey = e.target.dataset.topic;
                this.showHelpTopic(topicKey);
                
                // Update active state
                document.querySelectorAll('.help-topic').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
            });
        });

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('helpModal'));
        modal.show();

        // Auto-select first topic
        document.querySelector('.help-topic')?.click();
    }

    showHelpTopic(topicKey) {
        const topic = this.helpContent[topicKey];
        if (!topic) return;

        document.getElementById('helpContentArea').innerHTML = `
            <h5>${topic.title}</h5>
            ${topic.content}
        `;
    }

    setupAccessibilityFeatures() {
        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + combinations
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'r': // Start/Stop Recording
                        e.preventDefault();
                        this.toggleRecording();
                        break;
                    case 'p': // Pause/Resume
                        e.preventDefault();
                        this.togglePause();
                        break;
                    case 'h': // Help
                        e.preventDefault();
                        this.showHelpModal();
                        break;
                }
            }

            // Function keys
            switch(e.key) {
                case 'F1': // Help
                    e.preventDefault();
                    this.showHelpModal();
                    break;
                case 'F5': // Reset
                    e.preventDefault();
                    if (confirm('Möchten Sie wirklich alle Streams zurücksetzen?')) {
                        this.resetAllStreams();
                    }
                    break;
            }
        });

        // Add focus indicators
        this.enhanceFocusIndicators();

        // Add screen reader support
        this.addScreenReaderSupport();
    }

    enhanceFocusIndicators() {
        const style = document.createElement('style');
        style.textContent = `
            .streamrec-focus:focus {
                outline: 3px solid #667eea !important;
                outline-offset: 2px !important;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.25) !important;
            }
        `;
        document.head.appendChild(style);

        // Add focus class to interactive elements
        document.querySelectorAll('button, input, select, .stream-thumbnail').forEach(el => {
            el.classList.add('streamrec-focus');
        });
    }

    addScreenReaderSupport() {
        // Add ARIA labels and descriptions
        const ariaEnhancements = {
            'compositionCanvas': {
                role: 'img',
                label: 'Live-Komposition der Video-Streams',
                describedby: 'canvas-description'
            },
            'startCameraBtn': {
                describedby: 'Startet die Kamera-Aufnahme für die Live-Übertragung'
            },
            'startRecordingBtn': {
                describedby: 'Beginnt die Aufzeichnung der zusammengesetzten Video-Streams'
            }
        };

        Object.entries(ariaEnhancements).forEach(([id, attrs]) => {
            const element = document.getElementById(id);
            if (element) {
                Object.entries(attrs).forEach(([attr, value]) => {
                    element.setAttribute(`aria-${attr}`, value);
                });
            }
        });

        // Add canvas description
        if (!document.getElementById('canvas-description')) {
            const description = document.createElement('div');
            description.id = 'canvas-description';
            description.className = 'sr-only';
            description.textContent = 'Zeigt die Live-Zusammenstellung aller aktiven Video-Streams im 9:16 Format an';
            document.body.appendChild(description);
        }
    }

    enhanceUserExperience() {
        // Add loading states
        this.enhanceLoadingStates();

        // Add progress indicators
        this.addProgressIndicators();

        // Enhance error handling
        this.enhanceErrorHandling();

        // Add tooltips
        this.addTooltips();

        // Performance monitoring
        this.setupPerformanceMonitoring();
    }

    enhanceLoadingStates() {
        // Override original methods to add loading states
        const originalStartCamera = this.streamRecorder.startCamera;
        this.streamRecorder.startCamera = async function() {
            const btn = document.getElementById('startCameraBtn');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Lädt...';
            btn.disabled = true;

            try {
                await originalStartCamera.call(this);
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        };
    }

    addProgressIndicators() {
        // Add subtle progress indicators for operations
        const progressHtml = `
            <div id="operationProgress" class="position-fixed bottom-0 start-0 end-0" style="z-index: 1055; height: 3px;">
                <div class="progress" style="height: 3px; border-radius: 0;">
                    <div class="progress-bar bg-primary" id="globalProgressBar" style="width: 0%; transition: width 0.3s ease;"></div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', progressHtml);
    }

    updateGlobalProgress(percentage) {
        const progressBar = document.getElementById('globalProgressBar');
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            
            // Hide when complete
            if (percentage >= 100) {
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 1000);
            }
        }
    }

    addTooltips() {
        const tooltips = {
            'startCameraBtn': 'Startet die Kamera-Aufnahme (Strg+C)',
            'startScreenBtn': 'Startet die Bildschirm-Aufnahme (Strg+S)', 
            'startCompositionBtn': 'Beginnt die Live-Zusammenstellung',
            'startRecordingBtn': 'Startet die Video-Aufzeichnung (Strg+R)',
            'helpBtn': 'Öffnet das Hilfe-System (F1)'
        };

        Object.entries(tooltips).forEach(([id, text]) => {
            const element = document.getElementById(id);
            if (element) {
                element.setAttribute('title', text);
                element.setAttribute('data-bs-toggle', 'tooltip');
            }
        });

        // Initialize Bootstrap tooltips
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    setupPerformanceMonitoring() {
        this.performanceMetrics = {
            streamStartTime: 0,
            compositionFrameRate: 0,
            recordingBitrate: 0,
            memoryUsage: 0
        };

        // Monitor frame rate
        setInterval(() => {
            this.updatePerformanceMetrics();
        }, 5000);
    }

    updatePerformanceMetrics() {
        // Basic performance monitoring
        if (performance.memory) {
            this.performanceMetrics.memoryUsage = Math.round(performance.memory.usedJSHeapSize / 1048576); // MB
        }

        // Update performance display if visible
        const perfDisplay = document.getElementById('performanceMetrics');
        if (perfDisplay) {
            perfDisplay.innerHTML = `
                <small class="text-muted">
                    RAM: ${this.performanceMetrics.memoryUsage} MB
                    ${this.streamRecorder.isComposing ? '| Komposition: Aktiv' : ''}
                    ${this.streamRecorder.recordingEngine?.isRecording ? '| Aufnahme: Läuft' : ''}
                </small>
            `;
        }
    }

    // Utility methods
    toggleRecording() {
        const startBtn = document.getElementById('startRecordingBtn');
        const stopBtn = document.getElementById('stopRecordingBtn');
        
        if (!startBtn.disabled) {
            this.streamRecorder.recordingEngine?.startRecording();
        } else if (!stopBtn.disabled) {
            this.streamRecorder.recordingEngine?.stopRecording();
        }
    }

    togglePause() {
        const pauseBtn = document.getElementById('pauseRecordingBtn');
        if (!pauseBtn.disabled) {
            this.streamRecorder.recordingEngine?.pauseRecording();
        }
    }

    resetAllStreams() {
        this.streamRecorder.stopCamera();
        this.streamRecorder.stopScreen();
        this.streamRecorder.stopComposition();
        this.showNotification('info', 'Zurückgesetzt', 'Alle Streams wurden gestoppt');
    }

    enhanceErrorHandling() {
        // Global error handler with German messages
        window.addEventListener('error', (e) => {
            console.error('Globaler Fehler:', e.error);
            this.showNotification('error', 'Unerwarteter Fehler', 
                'Ein unerwarteter Fehler ist aufgetreten. Bitte laden Sie die Seite neu.');
        });

        // Unhandled promise rejection handler
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unbehandelte Promise-Ablehnung:', e.reason);
            this.showNotification('warning', 'Warnung', 
                'Ein Vorgang konnte nicht abgeschlossen werden.');
        });
    }
}

// Export for use in main StreamRecorder
window.GermanUI = GermanUI;