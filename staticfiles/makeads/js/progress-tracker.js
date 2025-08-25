/**
 * MakeAds Progress Tracker für Creative-Generierung
 * 
 * Überwacht den Fortschritt von Generierungsjobs und zeigt Live-Updates
 */

class MakeAdsProgressTracker {
    constructor() {
        this.jobId = null;
        this.interval = null;
        this.startTime = null;
        this.totalCreatives = 0;
        this.isActive = false;
        
        // UI-Elemente
        this.progressContainer = document.getElementById('generation-progress-container');
        this.progressBar = document.getElementById('progress-bar');
        this.progressStatus = document.getElementById('progress-status');
        this.progressCurrent = document.getElementById('progress-current');
        this.progressTotal = document.getElementById('progress-total');
        this.progressPercentage = document.getElementById('progress-percentage');
        this.progressEta = document.getElementById('progress-eta');
        this.currentAction = document.getElementById('current-action');
        this.cancelButton = document.getElementById('cancel-generation');
        this.successContainer = document.getElementById('generation-success');
        this.errorContainer = document.getElementById('generation-error');
        this.successCount = document.getElementById('success-count');
        this.viewResultsLink = document.getElementById('view-results-link');
        this.errorMessage = document.getElementById('error-message');
        
        this.bindEvents();
    }
    
    bindEvents() {
        // Cancel-Button
        if (this.cancelButton) {
            this.cancelButton.addEventListener('click', () => {
                this.cancelGeneration();
            });
        }
        
        // Form-Submit abfangen
        const forms = document.querySelectorAll('form[data-progress-tracking="true"]');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleFormSubmit(form);
            });
        });
    }
    
    /**
     * Startet das Progress-Tracking für einen neuen Job
     */
    startTracking(jobId, totalCreatives, campaignId = null) {
        console.log(`🚀 Starte Progress-Tracking für Job ${jobId}`);
        
        this.jobId = jobId;
        this.totalCreatives = totalCreatives;
        this.startTime = new Date();
        this.isActive = true;
        
        // UI initialisieren
        this.showProgressBar();
        this.updateProgress(0, totalCreatives, 'Starte Generierung...');
        
        // Polling starten
        this.startPolling();
        
        // View-Results Link setzen
        if (campaignId && this.viewResultsLink) {
            this.viewResultsLink.href = `/makeads/campaign/${campaignId}/`;
        }
    }
    
    /**
     * Startet das Polling für Job-Updates
     */
    startPolling() {
        if (this.interval) {
            clearInterval(this.interval);
        }
        
        this.interval = setInterval(() => {
            this.checkProgress();
        }, 1000); // Alle 1 Sekunde prüfen
    }
    
    /**
     * Prüft den aktuellen Fortschritt
     */
    async checkProgress() {
        if (!this.jobId || !this.isActive) return;
        
        try {
            const response = await fetch(`/makeads/job/${this.jobId}/status/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('📊 Progress Update:', data);
            
            this.handleProgressUpdate(data);
            
        } catch (error) {
            console.error('❌ Fehler beim Fortschritts-Check:', error);
            this.handleError(`Fehler beim Abrufen des Fortschritts: ${error.message}`);
        }
    }
    
    /**
     * Verarbeitet Progress-Updates
     */
    handleProgressUpdate(data) {
        const { status, progress, target, percentage, error_message } = data;
        
        // Status-Updates
        switch (status) {
            case 'processing':
                this.updateProgress(progress, target, this.getProgressMessage(progress, target));
                break;
                
            case 'completed':
                this.handleSuccess(progress);
                break;
                
            case 'failed':
                this.handleError(error_message || 'Die Generierung ist fehlgeschlagen.');
                break;
                
            default:
                this.updateProgress(progress, target, 'Verarbeitung...');
        }
    }
    
    /**
     * Aktualisiert die Progress-Bar
     */
    updateProgress(current, total, message = '') {
        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        
        // Progress-Bar aktualisieren
        if (this.progressBar) {
            this.progressBar.style.width = `${percentage}%`;
            this.progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        // Zahlen aktualisieren
        if (this.progressCurrent) this.progressCurrent.textContent = current;
        if (this.progressTotal) this.progressTotal.textContent = total;
        if (this.progressPercentage) this.progressPercentage.textContent = `${percentage}%`;
        
        // Status-Nachricht
        if (this.progressStatus && message) {
            this.progressStatus.textContent = message;
        }
        
        // ETA berechnen
        this.updateETA(current, total);
        
        // Aktuelle Aktion
        this.updateCurrentAction(current, total);
    }
    
    /**
     * Berechnet und zeigt die geschätzte verbleibende Zeit
     */
    updateETA(current, total) {
        if (!this.progressEta || !this.startTime || current === 0) return;
        
        const elapsed = (new Date() - this.startTime) / 1000; // Sekunden
        const avgTimePerItem = elapsed / current;
        const remaining = (total - current) * avgTimePerItem;
        
        if (remaining > 0) {
            const minutes = Math.floor(remaining / 60);
            const seconds = Math.floor(remaining % 60);
            this.progressEta.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        } else {
            this.progressEta.textContent = '00:00';
        }
    }
    
    /**
     * Aktualisiert die aktuelle Aktion
     */
    updateCurrentAction(current, total) {
        if (!this.currentAction) return;
        
        const actions = [
            'Bereite KI-Modell vor...',
            'Generiere Werbetext...',
            'Erstelle Bild mit DALL-E...',
            'Optimiere Creative...',
            'Speichere Ergebnis...'
        ];
        
        const actionIndex = current % actions.length;
        this.currentAction.textContent = actions[actionIndex];
    }
    
    /**
     * Erstellt Fortschritts-Nachrichten
     */
    getProgressMessage(current, total) {
        const messages = [
            `Creative ${current} von ${total} wird erstellt...`,
            `${current} von ${total} Creatives fertig`,
            `Fortschritt: ${current}/${total} Creatives`
        ];
        
        return messages[Math.floor(Math.random() * messages.length)];
    }
    
    /**
     * Behandelt erfolgreiche Generierung
     */
    handleSuccess(count) {
        console.log(`✅ Generierung erfolgreich abgeschlossen: ${count} Creatives`);
        
        this.isActive = false;
        this.stopPolling();
        
        // Progress-Bar verstecken
        this.hideProgressBar();
        
        // Erfolgs-Nachricht anzeigen
        if (this.successContainer && this.successCount) {
            this.successCount.textContent = count;
            this.successContainer.style.display = 'block';
            this.successContainer.classList.add('success-fade-in');
        }
        
        // Nach 5 Sekunden zur Kampagne weiterleiten
        setTimeout(() => {
            if (this.viewResultsLink && this.viewResultsLink.href) {
                window.location.href = this.viewResultsLink.href;
            }
        }, 5000);
    }
    
    /**
     * Behandelt Fehler
     */
    handleError(message) {
        console.error(`❌ Generierung fehlgeschlagen: ${message}`);
        
        this.isActive = false;
        this.stopPolling();
        
        // Progress-Bar verstecken
        this.hideProgressBar();
        
        // Fehler-Nachricht anzeigen
        if (this.errorContainer && this.errorMessage) {
            this.errorMessage.textContent = message;
            this.errorContainer.style.display = 'block';
        }
    }
    
    /**
     * Bricht die Generierung ab
     */
    async cancelGeneration() {
        if (!this.jobId) return;
        
        const confirmed = confirm('Möchten Sie die Generierung wirklich abbrechen?');
        if (!confirmed) return;
        
        try {
            // Match Django URL: path('ajax/cancel-generation/<uuid:job_id>/')
            const response = await fetch(`/makeads/ajax/cancel-generation/${this.jobId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });
            
            if (response.ok) {
                this.handleError('Generierung wurde abgebrochen.');
            }
            
        } catch (error) {
            console.error('❌ Fehler beim Abbrechen:', error);
        }
    }
    
    /**
     * Behandelt Form-Submits mit Progress-Tracking
     */
    async handleFormSubmit(form) {
        console.log('🚀 Form submission started');
        const formData = new FormData(form);
        
        // Debug: Log form data
        for (let pair of formData.entries()) {
            console.log(`📋 Form data: ${pair[0]} = ${pair[1]}`);
        }
        
        try {
            console.log(`📡 Sending AJAX to: ${form.action}`);
            
            // Add timeout to prevent hanging requests
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.getCSRFToken(),
                },
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            console.log(`📊 Response status: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`❌ Response error: ${errorText}`);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('📦 Response data:', data);
            
            if (data.success && data.job_id) {
                console.log(`✅ Job created: ${data.job_id}`);
                // Progress-Tracking starten
                this.startTracking(
                    data.job_id, 
                    data.total_creatives, 
                    data.campaign_id
                );
            } else {
                throw new Error(data.error || 'Keine Job-ID erhalten');
            }
            
        } catch (error) {
            console.error('❌ Form-Submit Fehler:', error);
            
            let errorMessage = `Fehler beim Starten der Generierung: ${error.message}`;
            
            if (error.name === 'AbortError') {
                errorMessage = 'Request-Timeout: Die Anfrage dauerte zu lange (30s). Bitte versuchen Sie es erneut.';
            }
            
            this.handleError(errorMessage);
        }
    }
    
    /**
     * Hilfsfunktionen
     */
    showProgressBar() {
        if (this.progressContainer) {
            this.progressContainer.style.display = 'block';
        }
        this.hideMessages();
    }
    
    hideProgressBar() {
        if (this.progressContainer) {
            this.progressContainer.style.display = 'none';
        }
    }
    
    hideMessages() {
        if (this.successContainer) this.successContainer.style.display = 'none';
        if (this.errorContainer) this.errorContainer.style.display = 'none';
    }
    
    stopPolling() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
}

// Globale Instanz erstellen
window.makeAdsProgressTracker = new MakeAdsProgressTracker();

// Auto-Start für bestehende Jobs beim Seitenladen
document.addEventListener('DOMContentLoaded', () => {
    // Prüfe ob es aktive Jobs gibt
    const activeJobElement = document.querySelector('[data-active-job-id]');
    if (activeJobElement) {
        const jobId = activeJobElement.dataset.activeJobId;
        const totalCreatives = parseInt(activeJobElement.dataset.totalCreatives) || 10;
        const campaignId = activeJobElement.dataset.campaignId;
        
        console.log('🔄 Aktiver Job gefunden, setze Tracking fort');
        window.makeAdsProgressTracker.startTracking(jobId, totalCreatives, campaignId);
    }
});
