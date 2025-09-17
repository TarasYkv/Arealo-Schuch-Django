/**
 * Safe Global Chat Notification System
 * Checks for new messages with safety mechanisms to prevent browser crashes
 */

class SafeGlobalChatNotifications {
    constructor() {
        this.lastUnreadCount = 0;
        this.notificationPermission = false;
        this.isInChatApp = window.location.pathname.startsWith('/chat/');
        this.pollingInterval = null;
        this.isDestroyed = false;
        this.requestInProgress = false;
        this.errorCount = 0;
        this.maxErrors = 5;

        // Safety: Don't initialize if already exists or in chat app
        if (window.globalChatNotifications || this.isInChatApp) {
            return;
        }

        try {
            this.initNotifications();
            this.startPolling();
        } catch (error) {
            console.error('Failed to initialize chat notifications:', error);
            this.cleanup();
        }
    }

    initNotifications() {
        // Request permission for notifications safely
        if ('Notification' in window) {
            if (Notification.permission === 'granted') {
                this.notificationPermission = true;
            } else if (Notification.permission === 'default') {
                // Don't auto-request, let user decide
                this.notificationPermission = false;
            }
        }
    }

    startPolling() {
        if (this.isDestroyed || this.pollingInterval) return;

        // Initial check after 5 seconds to avoid immediate load
        setTimeout(() => {
            if (!this.isDestroyed) {
                this.checkForNewMessages();
            }
        }, 5000);

        // Poll every 60 seconds (safer interval)
        this.pollingInterval = setInterval(() => {
            if (!this.isDestroyed) {
                this.checkForNewMessages();
            }
        }, 60000);
    }

    async checkForNewMessages() {
        // Safety checks
        if (this.isDestroyed || this.requestInProgress || this.errorCount >= this.maxErrors) {
            return;
        }

        // Skip if page is hidden to save resources
        if (document.hidden) {
            return;
        }

        this.requestInProgress = true;

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

            const response = await fetch('/chat/unread-count/', {
                signal: controller.signal,
                method: 'GET',
                headers: {
                    'Cache-Control': 'no-cache'
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            const currentUnreadCount = parseInt(data.unread_count) || 0;

            // Update document title with unread count
            this.updateDocumentTitle(currentUnreadCount);

            // Show notification if there are new messages
            if (currentUnreadCount > this.lastUnreadCount && currentUnreadCount > 0) {
                this.showNewMessageNotification(currentUnreadCount - this.lastUnreadCount);
            }

            this.lastUnreadCount = currentUnreadCount;
            this.errorCount = 0; // Reset error count on success

        } catch (error) {
            this.errorCount++;
            console.warn(`Chat notification error (${this.errorCount}/${this.maxErrors}):`, error.message);

            if (this.errorCount >= this.maxErrors) {
                console.warn('Too many errors, stopping chat notifications');
                this.cleanup();
            }
        } finally {
            this.requestInProgress = false;
        }
    }

    updateDocumentTitle(unreadCount) {
        try {
            const baseTitle = document.title.replace(/^\(\d+\)\s*/, '');

            if (unreadCount > 0) {
                document.title = `(${unreadCount}) ${baseTitle}`;
            } else {
                document.title = baseTitle;
            }
        } catch (error) {
            console.warn('Error updating document title:', error);
        }
    }

    showNewMessageNotification(newMessageCount) {
        // Safety checks
        if (!this.notificationPermission || !('Notification' in window) || this.isDestroyed) {
            return;
        }

        try {
            const notification = new Notification('Neue Chat-Nachricht', {
                body: newMessageCount === 1
                    ? 'Sie haben eine neue Nachricht erhalten'
                    : `Sie haben ${newMessageCount} neue Nachrichten erhalten`,
                icon: '/static/images/favicon-32x32.png',
                tag: 'global-chat-safe',
                requireInteraction: false,
                silent: false
            });

            notification.onclick = () => {
                try {
                    window.focus();
                    window.location.href = '/chat/';
                    notification.close();
                } catch (e) {
                    console.warn('Error handling notification click:', e);
                }
            };

            // Auto-close after 8 seconds
            setTimeout(() => {
                try {
                    notification.close();
                } catch (e) {
                    // Ignore close errors
                }
            }, 8000);

        } catch (error) {
            console.warn('Error showing notification:', error);
        }
    }

    cleanup() {
        this.isDestroyed = true;

        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        // Clear any pending timeouts
        this.requestInProgress = false;
    }
}

// Safe initialization with multiple safeguards
document.addEventListener('DOMContentLoaded', function() {
    // Multiple safety checks
    if (window.globalChatNotifications) {
        return; // Already initialized
    }

    if (window.location.pathname.startsWith('/chat/')) {
        return; // Don't run in chat app
    }

    if (document.body.dataset.userAuthenticated !== 'true') {
        return; // User not authenticated
    }

    try {
        // Wait a bit before initializing to avoid conflicts
        setTimeout(() => {
            if (!window.globalChatNotifications) {
                window.globalChatNotifications = new SafeGlobalChatNotifications();
            }
        }, 2000);
    } catch (error) {
        console.error('Failed to initialize safe chat notifications:', error);
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.globalChatNotifications) {
        try {
            window.globalChatNotifications.cleanup();
        } catch (error) {
            // Ignore cleanup errors
        }
    }
});

// Cleanup on page hide (mobile browsers)
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.globalChatNotifications) {
        try {
            window.globalChatNotifications.cleanup();
        } catch (error) {
            // Ignore cleanup errors
        }
    }
});