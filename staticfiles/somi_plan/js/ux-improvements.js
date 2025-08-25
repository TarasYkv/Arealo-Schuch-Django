/**
 * UX Improvements JavaScript für Social Media Planer
 */

class SomiPlanUX {
    constructor() {
        this.initializeTooltips();
        this.initializeFormValidation();
        this.initializeCharacterCounters();
        this.initializeLoadingStates();
    }

    /**
     * Enhanced Loading States für AI-Operationen
     */
    showAIProgress(operation = 'generate', estimatedTime = 30) {
        const progressStages = {
            'strategy': [
                { text: '🎯 Analysiere deine Zielgruppe...', duration: 30 },
                { text: '📊 Erstelle optimale Posting-Strategie...', duration: 40 },
                { text: '⚡ Finalisiere Empfehlungen...', duration: 30 }
            ],
            'content': [
                { text: '🤖 Verstehe dein Thema...', duration: 25 },
                { text: '✍️ Generiere kreativen Content...', duration: 35 },
                { text: '🎨 Optimiere für Plattform...', duration: 25 },
                { text: '✨ Füge finale Details hinzu...', duration: 15 }
            ],
            'ideas': [
                { text: '💡 Sammle kreative Inspirationen...', duration: 30 },
                { text: '📝 Entwickle Post-Ideen...', duration: 40 },
                { text: '🎯 Personalisiere für dich...', duration: 30 }
            ]
        };

        const stages = progressStages[operation] || progressStages['content'];
        let currentStage = 0;
        let progress = 0;
        let totalDuration = stages.reduce((sum, stage) => sum + stage.duration, 0);
        let elapsedTime = 0;

        // Erstelle Progress Container
        const progressContainer = document.createElement('div');
        progressContainer.className = 'ai-progress-container active';
        progressContainer.innerHTML = `
            <div class="progress-bar">
                <div class="progress-fill" style="width: 0%"></div>
            </div>
            <p class="progress-text">
                <span class="ai-icon">🤖</span>
                <span class="stage-text">${stages[0].text}</span>
            </p>
            <small class="progress-eta">Geschätzte Zeit: ${Math.ceil(totalDuration / 10)} Sekunden</small>
        `;

        return {
            container: progressContainer,
            start: () => {
                const progressFill = progressContainer.querySelector('.progress-fill');
                const stageText = progressContainer.querySelector('.stage-text');
                const etaText = progressContainer.querySelector('.progress-eta');

                const updateProgress = () => {
                    if (currentStage < stages.length) {
                        const stage = stages[currentStage];
                        progress += (stage.duration / totalDuration) * 100;
                        elapsedTime += stage.duration;

                        progressFill.style.width = `${Math.min(progress, 100)}%`;
                        stageText.textContent = stage.text;
                        
                        const remainingTime = Math.ceil((totalDuration - elapsedTime) / 10);
                        etaText.textContent = remainingTime > 0 
                            ? `Noch ca. ${remainingTime} Sekunden`
                            : 'Fast fertig...';

                        currentStage++;
                        
                        if (currentStage < stages.length) {
                            setTimeout(updateProgress, (stage.duration / totalDuration) * estimatedTime * 1000);
                        }
                    }
                };

                updateProgress();
            },
            complete: () => {
                const progressFill = progressContainer.querySelector('.progress-fill');
                const stageText = progressContainer.querySelector('.stage-text');
                const etaText = progressContainer.querySelector('.progress-eta');

                progressFill.style.width = '100%';
                stageText.innerHTML = '✅ <span class="ai-icon">🎉</span> Fertig!';
                etaText.textContent = 'Abgeschlossen';

                setTimeout(() => {
                    progressContainer.classList.add('fade-out');
                    setTimeout(() => progressContainer.remove(), 500);
                }, 1500);
            }
        };
    }

    /**
     * Verbesserte Fehlerbehandlung
     */
    showError(title, message, options = {}) {
        const errorCard = document.createElement('div');
        errorCard.className = 'error-card';
        
        const actions = options.actions || [
            { text: 'Nochmal versuchen', class: 'btn-primary', action: options.retry },
            { text: 'Manual weitermachen', class: 'btn-outline-primary', action: options.fallback }
        ];

        errorCard.innerHTML = `
            <h4>⚠️ ${title}</h4>
            <p>${message}</p>
            <div class="error-actions">
                ${actions.filter(action => action.action).map(action => 
                    `<button class="btn ${action.class}" onclick="this.closest('.error-card').remove(); (${action.action})()">${action.text}</button>`
                ).join('')}
            </div>
        `;

        return errorCard;
    }

    /**
     * Success Confirmations
     */
    showSuccess(title, message, nextStep = null) {
        const successCard = document.createElement('div');
        successCard.className = 'success-card';
        
        successCard.innerHTML = `
            <h4><span class="success-icon">✅</span> ${title}</h4>
            <p>${message}</p>
            ${nextStep ? `<p><strong>Nächster Schritt:</strong> ${nextStep}</p>` : ''}
        `;

        // Auto-remove after 5 seconds
        setTimeout(() => {
            successCard.classList.add('fade-out');
            setTimeout(() => successCard.remove(), 500);
        }, 5000);

        return successCard;
    }

    /**
     * Tooltips initialisieren
     */
    initializeTooltips() {
        document.addEventListener('DOMContentLoaded', () => {
            // Füge Tooltips zu bestehenden Help-Icons hinzu
            const helpIcons = document.querySelectorAll('.help-icon, [data-tooltip]');
            
            helpIcons.forEach(icon => {
                const tooltipText = icon.getAttribute('data-tooltip');
                if (tooltipText) {
                    icon.classList.add('tooltip-trigger');
                    
                    const tooltipContent = document.createElement('div');
                    tooltipContent.className = 'tooltip-content';
                    tooltipContent.textContent = tooltipText;
                    
                    icon.appendChild(tooltipContent);
                }
            });
        });
    }

    /**
     * Form Validation
     */
    initializeFormValidation() {
        document.addEventListener('DOMContentLoaded', () => {
            const forms = document.querySelectorAll('form');
            
            forms.forEach(form => {
                const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
                
                inputs.forEach(input => {
                    input.addEventListener('blur', () => this.validateField(input));
                    input.addEventListener('input', () => this.clearValidation(input));
                });
            });
        });
    }

    validateField(field) {
        const value = field.value.trim();
        const isValid = value.length > 0;
        
        // Remove existing validation
        this.clearValidation(field);
        
        // Add validation message
        const validation = document.createElement('div');
        validation.className = `form-validation ${isValid ? 'success' : 'error'}`;
        validation.textContent = isValid 
            ? '✓ Gültig'
            : '⚠ Dieses Feld ist erforderlich';
        
        field.parentNode.appendChild(validation);
        
        return isValid;
    }

    clearValidation(field) {
        const existingValidation = field.parentNode.querySelector('.form-validation');
        if (existingValidation) {
            existingValidation.remove();
        }
    }

    /**
     * Character Counter
     */
    initializeCharacterCounters() {
        document.addEventListener('DOMContentLoaded', () => {
            const textareas = document.querySelectorAll('textarea[data-max-length]');
            
            textareas.forEach(textarea => {
                const maxLength = parseInt(textarea.getAttribute('data-max-length'));
                
                // Erstelle Counter
                const counter = document.createElement('div');
                counter.className = 'character-counter';
                textarea.parentNode.appendChild(counter);
                
                const updateCounter = () => {
                    const remaining = maxLength - textarea.value.length;
                    counter.textContent = `${textarea.value.length}/${maxLength} Zeichen`;
                    
                    // Färbe basierend auf verbleibendem Platz
                    counter.className = 'character-counter';
                    if (remaining < maxLength * 0.1) {
                        counter.classList.add('danger');
                    } else if (remaining < maxLength * 0.2) {
                        counter.classList.add('warning');
                    }
                };
                
                textarea.addEventListener('input', updateCounter);
                updateCounter(); // Initial call
            });
        });
    }

    /**
     * Loading States initialisieren
     */
    initializeLoadingStates() {
        // Override für AJAX Calls
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const url = args[0];
            
            // Zeige Loading State für AI-Operationen
            let progressHandler = null;
            if (url.includes('create_post') || url.includes('generate_strategy')) {
                const operation = url.includes('strategy') ? 'strategy' : 'content';
                progressHandler = this.showAIProgress(operation);
                
                // Finde Container und füge Progress hinzu
                const container = document.querySelector('.ai-content-container') || document.body;
                container.appendChild(progressHandler.container);
                progressHandler.start();
            }
            
            try {
                const response = await originalFetch(...args);
                
                if (progressHandler) {
                    progressHandler.complete();
                }
                
                return response;
            } catch (error) {
                if (progressHandler) {
                    progressHandler.container.remove();
                }
                throw error;
            }
        };
    }

    /**
     * Skeleton Loading für Content
     */
    showSkeletonLoading(container, type = 'card') {
        const skeleton = document.createElement('div');
        skeleton.className = `skeleton skeleton-${type}`;
        
        if (type === 'text') {
            skeleton.innerHTML = `
                <div class="skeleton-text long"></div>
                <div class="skeleton-text medium"></div>
                <div class="skeleton-text short"></div>
            `;
        }
        
        container.appendChild(skeleton);
        return skeleton;
    }

    /**
     * Auto-save Funktionalität
     */
    enableAutoSave(form, saveEndpoint, interval = 30000) {
        let saveTimeout;
        
        const inputs = form.querySelectorAll('input, textarea, select');
        
        const autoSave = async () => {
            const formData = new FormData(form);
            
            try {
                await fetch(saveEndpoint, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                });
                
                // Zeige kurz Speicher-Indikator
                this.showSaveIndicator();
            } catch (error) {
                console.warn('Auto-save failed:', error);
            }
        };
        
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(autoSave, interval);
            });
        });
    }

    showSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.8rem;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        indicator.textContent = '💾 Automatisch gespeichert';
        
        document.body.appendChild(indicator);
        
        setTimeout(() => indicator.style.opacity = '1', 100);
        setTimeout(() => {
            indicator.style.opacity = '0';
            setTimeout(() => indicator.remove(), 300);
        }, 2000);
    }
}

// Initialize UX improvements when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.somiPlanUX = new SomiPlanUX();
});

// CSS für fade-out Animation
const style = document.createElement('style');
style.textContent = `
    .fade-out {
        opacity: 0 !important;
        transform: translateY(-10px) !important;
        transition: all 0.5s ease !important;
    }
`;
document.head.appendChild(style);