/**
 * Calendar Integration für Social Media Planer
 * Integriert responsive calendar mit existing functionality
 */

class CalendarIntegration {
    constructor() {
        this.calendar = null;
        this.legacyElements = {};
        this.init();
    }
    
    init() {
        // Store references to legacy elements
        this.legacyElements = {
            prevButton: document.getElementById('prev-month'),
            nextButton: document.getElementById('next-month'),
            titleElement: document.getElementById('calendar-title'),
            viewButtons: document.querySelectorAll('.view-toggle-btn')
        };
        
        // Initialize responsive calendar
        this.initResponsiveCalendar();
        
        // Setup legacy button integration
        this.setupLegacyIntegration();
    }
    
    initResponsiveCalendar() {
        const container = document.getElementById('calendar-container');
        if (container) {
            this.calendar = new ResponsiveCalendar('calendar-container');
            
            // Override calendar methods to integrate with legacy buttons
            this.overrideCalendarMethods();
        }
    }
    
    overrideCalendarMethods() {
        if (!this.calendar) return;
        
        // Override navigation methods to update legacy UI
        const originalPrevMonth = this.calendar.previousMonth.bind(this.calendar);
        const originalNextMonth = this.calendar.nextMonth.bind(this.calendar);
        const originalChangeView = this.calendar.changeView.bind(this.calendar);
        
        this.calendar.previousMonth = () => {
            originalPrevMonth();
            this.updateLegacyUI();
        };
        
        this.calendar.nextMonth = () => {
            originalNextMonth();
            this.updateLegacyUI();
        };
        
        this.calendar.changeView = (view) => {
            originalChangeView(view);
            this.updateLegacyViewButtons(view);
        };
    }
    
    setupLegacyIntegration() {
        // Connect legacy navigation buttons
        if (this.legacyElements.prevButton) {
            this.legacyElements.prevButton.addEventListener('click', () => {
                if (this.calendar) {
                    this.calendar.previousMonth();
                }
            });
        }
        
        if (this.legacyElements.nextButton) {
            this.legacyElements.nextButton.addEventListener('click', () => {
                if (this.calendar) {
                    this.calendar.nextMonth();
                }
            });
        }
        
        // Connect legacy view buttons
        this.legacyElements.viewButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                if (this.calendar && view) {
                    this.calendar.changeView(view);
                }
            });
        });
        
        // Setup today button
        const todayButton = document.querySelector('[onclick="goToToday()"]');
        if (todayButton) {
            todayButton.removeAttribute('onclick');
            todayButton.addEventListener('click', () => {
                if (this.calendar) {
                    this.calendar.currentDate = new Date();
                    this.calendar.renderCalendar();
                    this.updateLegacyUI();
                }
            });
        }
    }
    
    updateLegacyUI() {
        if (!this.calendar) return;
        
        // Update title
        if (this.legacyElements.titleElement) {
            this.legacyElements.titleElement.textContent = 
                this.calendar.formatMonth(this.calendar.currentDate);
        }
        
        // Update period display
        const periodElement = document.getElementById('currentPeriod');
        if (periodElement) {
            periodElement.textContent = 
                this.calendar.formatMonth(this.calendar.currentDate);
        }
    }
    
    updateLegacyViewButtons(activeView) {
        // Update legacy view buttons
        document.querySelectorAll('.view-toggle .btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeButton = document.getElementById(activeView + 'View');
        if (activeButton) {
            activeButton.classList.add('active');
        }
        
        // Update view containers (if they exist)
        document.querySelectorAll('.calendar-view').forEach(container => {
            container.classList.remove('active');
        });
        
        const activeContainer = document.getElementById(activeView + 'ViewContainer');
        if (activeContainer) {
            activeContainer.classList.add('active');
        }
    }
    
    // Legacy function compatibility
    switchView(view) {
        if (this.calendar) {
            this.calendar.changeView(view);
        }
    }
    
    navigateCalendar(direction) {
        if (this.calendar) {
            if (direction > 0) {
                this.calendar.nextMonth();
            } else {
                this.calendar.previousMonth();
            }
        }
    }
    
    goToToday() {
        if (this.calendar) {
            this.calendar.currentDate = new Date();
            this.calendar.renderCalendar();
            this.updateLegacyUI();
        }
    }
    
    // API methods for external access
    loadPosts(postsData) {
        if (this.calendar && postsData) {
            this.calendar.posts.clear();
            postsData.forEach(post => {
                const date = post.scheduled_date || post.created_date;
                if (!this.calendar.posts.has(date)) {
                    this.calendar.posts.set(date, []);
                }
                this.calendar.posts.get(date).push(post);
            });
            this.calendar.renderCalendar();
        }
    }
    
    refreshCalendar() {
        if (this.calendar) {
            this.calendar.loadPosts();
        }
    }
    
    getCurrentDate() {
        return this.calendar ? this.calendar.currentDate : new Date();
    }
    
    getCurrentView() {
        return this.calendar ? this.calendar.viewMode : 'month';
    }
}

// Global functions for backward compatibility
function switchView(view) {
    if (window.calendarIntegration) {
        window.calendarIntegration.switchView(view);
    }
}

function navigateCalendar(direction) {
    if (window.calendarIntegration) {
        window.calendarIntegration.navigateCalendar(direction);
    }
}

function goToToday() {
    if (window.calendarIntegration) {
        window.calendarIntegration.goToToday();
    }
}

// Initialize integration when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for other scripts to load
    setTimeout(() => {
        if (document.getElementById('calendar-container')) {
            window.calendarIntegration = new CalendarIntegration();
            
            // Load posts data if available
            if (typeof posts !== 'undefined' && posts) {
                window.calendarIntegration.loadPosts(posts);
            }
        }
    }, 100);
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalendarIntegration;
}