// Global Messages Frontend JavaScript

class GlobalMessagesManager {
    constructor() {
        console.log('DEBUG: GlobalMessagesManager initialized');
        this.displayedMessages = new Set();
        this.messageQueue = [];
        this.isProcessingQueue = false;
        this.baseUrl = '/superconfig/messages/active/';

        // Initialize
        this.init();
    }

    init() {
        // Load messages on page load
        document.addEventListener('DOMContentLoaded', () => {
            this.loadActiveMessages();
        });

        // Periodically check for new messages (every 30 seconds)
        setInterval(() => {
            this.loadActiveMessages();
        }, 30000);
    }

    async loadActiveMessages() {
        try {
            console.log('DEBUG: Loading global messages from', this.baseUrl);
            const response = await fetch(this.baseUrl);
            const data = await response.json();
            console.log('DEBUG: API Response:', data);

            if (data.success && data.messages) {
                console.log('DEBUG: Processing', data.messages.length, 'messages');
                this.processMessages(data.messages);
            } else {
                console.log('DEBUG: No messages or API failed');
            }
        } catch (error) {
            console.error('Error loading global messages:', error);
        }
    }

    processMessages(messages) {
        console.log('DEBUG: processMessages called with', messages.length, 'messages');
        console.log('DEBUG: Current displayedMessages:', Array.from(this.displayedMessages));

        messages.forEach(message => {
            console.log('DEBUG: Processing message ID', message.id, 'title:', message.title);
            if (!this.displayedMessages.has(message.id)) {
                console.log('DEBUG: Adding message ID', message.id, 'to queue');
                this.messageQueue.push(message);
            } else {
                console.log('DEBUG: Message ID', message.id, 'already displayed, skipping');
            }
        });

        console.log('DEBUG: Current queue length:', this.messageQueue.length);
        if (!this.isProcessingQueue) {
            console.log('DEBUG: Starting queue processing');
            this.processMessageQueue();
        } else {
            console.log('DEBUG: Queue already being processed');
        }
    }

    async processMessageQueue() {
        console.log('DEBUG: processMessageQueue called, queue length:', this.messageQueue.length);
        if (this.messageQueue.length === 0) {
            this.isProcessingQueue = false;
            console.log('DEBUG: Queue empty, stopping processing');
            return;
        }

        this.isProcessingQueue = true;
        const message = this.messageQueue.shift();
        console.log('DEBUG: Processing message from queue:', message.id, 'title:', message.title);

        this.displayMessage(message);
        this.displayedMessages.add(message.id);

        // Add small delay between messages to avoid overwhelming user
        setTimeout(() => {
            this.processMessageQueue();
        }, 500);
    }

    displayMessage(message) {
        const messageElement = this.createMessageElement(message);
        document.body.appendChild(messageElement);

        // Trigger animation
        requestAnimationFrame(() => {
            messageElement.classList.add('show');
        });

        // Auto-remove after duration (only if duration is specified and > 0)
        if (message.duration_seconds && message.duration_seconds > 0) {
            setTimeout(() => {
                this.removeMessage(messageElement);
            }, message.duration_seconds * 1000);
        }
    }

    createMessageElement(message) {
        const element = document.createElement('div');
        element.className = `global-message ${this.getPositionClass(message.display_position)} ${message.display_type}`;
        element.setAttribute('data-message-id', message.id);
        element.setAttribute('role', 'alert');
        element.setAttribute('aria-live', 'polite');

        const icon = this.getMessageIcon(message.display_type);
        const closeButton = message.is_dismissible ?
            '<button class="global-message-close" aria-label="Nachricht schließen">&times;</button>' : '';

        element.innerHTML = `
            <div class="global-message-header">
                <h4 class="global-message-title">
                    ${icon}<span>${this.escapeHtml(message.title)}</span>
                </h4>
                ${closeButton}
            </div>
            <p class="global-message-content">${this.escapeHtml(message.content)}</p>
        `;

        // Add close functionality
        if (message.is_dismissible) {
            const closeBtn = element.querySelector('.global-message-close');
            closeBtn.addEventListener('click', () => {
                this.removeMessage(element);
            });
        }

        // Add click-to-close for popup types
        if (message.display_position.includes('popup')) {
            element.style.cursor = 'pointer';
            element.addEventListener('click', (e) => {
                if (e.target === element) {
                    this.removeMessage(element);
                }
            });
        }

        // Keyboard accessibility
        element.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && message.is_dismissible) {
                this.removeMessage(element);
            }
        });

        return element;
    }

    getPositionClass(position) {
        const positionMap = {
            'popup_center': 'popup-center',
            'popup_top': 'popup-top',
            'banner_top': 'banner-top',
            'banner_bottom': 'banner-bottom',
            'toast_top_right': 'toast-top-right',
            'toast_top_left': 'toast-top-left',
            'toast_bottom_right': 'toast-bottom-right',
            'toast_bottom_left': 'toast-bottom-left',
            'sidebar_right': 'sidebar-right',
            'sidebar_left': 'sidebar-left'
        };

        return positionMap[position] || 'toast-top-right';
    }

    getMessageIcon(type) {
        const iconMap = {
            'info': '<i class="global-message-icon fas fa-info-circle"></i>',
            'success': '<i class="global-message-icon fas fa-check-circle"></i>',
            'warning': '<i class="global-message-icon fas fa-exclamation-triangle"></i>',
            'error': '<i class="global-message-icon fas fa-times-circle"></i>',
            'announcement': '<i class="global-message-icon fas fa-bullhorn"></i>'
        };

        return iconMap[type] || iconMap['info'];
    }

    removeMessage(element) {
        element.style.animation = 'slideOut 0.3s ease-in forwards';

        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
        }, 300);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Method for SuperConfig preview functionality
    showPreviewMessage(messageData) {
        // Remove any existing preview messages
        document.querySelectorAll('.global-message[data-preview="true"]').forEach(el => {
            el.remove();
        });

        // Use the original messageData but add preview styling
        const element = this.createMessageElement(messageData);
        element.setAttribute('data-preview', 'true');
        element.style.opacity = '0.9';
        element.style.border = '2px dashed rgba(255, 255, 255, 0.5)';

        document.body.appendChild(element);

        // Add preview label
        const previewLabel = document.createElement('div');
        previewLabel.innerHTML = '<small style="position: absolute; top: -20px; left: 0; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;">VORSCHAU - ' + (messageData.duration_seconds ? messageData.duration_seconds + 's' : 'UNENDLICH') + '</small>';
        element.style.position = 'relative';
        element.appendChild(previewLabel);

        // Add safety timeout for previews (maximum 60 seconds)
        const maxPreviewTime = messageData.duration_seconds > 60 || !messageData.duration_seconds ? 60 : null;
        if (maxPreviewTime) {
            setTimeout(() => {
                if (element.parentNode) {
                    this.removeMessage(element);
                }
            }, maxPreviewTime * 1000);
        }
        return element;
    }

    // Method to manually trigger message check (for SuperConfig)
    forceRefresh() {
        this.loadActiveMessages();
    }

    // Method to clear all messages
    clearAllMessages() {
        document.querySelectorAll('.global-message').forEach(element => {
            this.removeMessage(element);
        });
        this.displayedMessages.clear();
        this.messageQueue = [];
    }
}

// Initialize global messages manager
console.log('DEBUG: Creating GlobalMessagesManager instance');
window.globalMessagesManager = new GlobalMessagesManager();

// Make preview function available globally for SuperConfig
window.showGlobalMessagePreview = function(messageData) {
    return window.globalMessagesManager.showPreviewMessage(messageData);
};

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GlobalMessagesManager;
}