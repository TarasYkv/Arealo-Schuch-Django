/**
 * Responsive Calendar für Social Media Planer
 * Touch-optimiert für mobile Geräte
 */

class ResponsiveCalendar {
    constructor(containerId = 'calendar-container') {
        this.container = document.getElementById(containerId);
        this.currentDate = new Date();
        this.viewMode = 'month'; // 'month' oder 'week'
        this.posts = new Map(); // Gespeicherte Posts nach Datum
        this.draggedElement = null;
        this.touchStartPos = null;
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        if (!this.container) return;
        
        this.renderCalendar();
        this.attachEventListeners();
        this.loadPosts();
        
        // Touch-Gesten für mobile Geräte
        if (this.isMobile()) {
            this.initTouchGestures();
        }
    }
    
    isMobile() {
        return window.innerWidth <= 768;
    }
    
    renderCalendar() {
        const html = `
            <div class="calendar-header">
                <div class="calendar-navigation">
                    <button class="calendar-nav-btn" id="prev-month" aria-label="Vorheriger Monat">
                        <i class="fas fa-chevron-left"></i>
                    </button>
                    <h2 class="calendar-title" id="calendar-title">${this.formatMonth(this.currentDate)}</h2>
                    <button class="calendar-nav-btn" id="next-month" aria-label="Nächster Monat">
                        <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
                <div class="calendar-view-toggle">
                    <button class="view-toggle-btn ${this.viewMode === 'month' ? 'active' : ''}" 
                            data-view="month">Monat</button>
                    <button class="view-toggle-btn ${this.viewMode === 'week' ? 'active' : ''}" 
                            data-view="week">Woche</button>
                </div>
            </div>
            <div class="calendar-content" id="calendar-content">
                ${this.renderCalendarGrid()}
            </div>
            <div class="live-region" aria-live="polite" id="calendar-announcements"></div>
        `;
        
        this.container.innerHTML = html;
    }
    
    renderCalendarGrid() {
        if (this.isMobile() && this.viewMode === 'month') {
            return this.renderMobileCalendar();
        } else if (this.viewMode === 'week') {
            return this.renderWeekView();
        } else {
            return this.renderDesktopCalendar();
        }
    }
    
    renderDesktopCalendar() {
        const firstDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
        const lastDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0);
        const startDate = new Date(firstDay);
        startDate.setDate(startDate.getDate() - firstDay.getDay());
        
        let html = '<div class="calendar-grid">';
        
        // Wochentage-Header
        const weekdays = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
        weekdays.forEach(day => {
            html += `<div class="calendar-weekday">${day}</div>`;
        });
        
        // Kalender-Tage
        const currentDate = new Date(startDate);
        for (let week = 0; week < 6; week++) {
            for (let day = 0; day < 7; day++) {
                const isCurrentMonth = currentDate.getMonth() === this.currentDate.getMonth();
                const isToday = this.isToday(currentDate);
                const dateStr = this.formatDate(currentDate);
                const dayPosts = this.posts.get(dateStr) || [];
                
                html += `
                    <div class="calendar-day ${!isCurrentMonth ? 'other-month' : ''} 
                                ${isToday ? 'today' : ''} 
                                ${dayPosts.length > 0 ? 'has-posts' : ''}"
                         data-date="${dateStr}" 
                         tabindex="0"
                         role="gridcell"
                         aria-label="${this.formatDateAria(currentDate)}">
                        
                        <div class="calendar-day-number">${currentDate.getDate()}</div>
                        
                        <div class="calendar-posts-container">
                            ${this.renderDayPosts(dayPosts)}
                        </div>
                        
                        <button class="calendar-add-post" 
                                data-date="${dateStr}"
                                aria-label="Post für ${this.formatDateAria(currentDate)} hinzufügen">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                `;
                
                currentDate.setDate(currentDate.getDate() + 1);
            }
        }
        
        html += '</div>';
        return html;
    }
    
    renderMobileCalendar() {
        const firstDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
        const lastDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0);
        
        let html = '<div class="calendar-grid mobile-view">';
        
        const currentDate = new Date(firstDay);
        while (currentDate <= lastDay) {
            const isToday = this.isToday(currentDate);
            const dateStr = this.formatDate(currentDate);
            const dayPosts = this.posts.get(dateStr) || [];
            const weekdayName = this.formatWeekday(currentDate);
            
            html += `
                <div class="calendar-day mobile-card ${isToday ? 'today' : ''}" 
                     data-date="${dateStr}"
                     tabindex="0"
                     role="article"
                     aria-label="${this.formatDateAria(currentDate)}">
                    
                    <div class="mobile-day-header">
                        <div class="mobile-day-number">${currentDate.getDate()}</div>
                        <div class="mobile-day-weekday">${weekdayName}</div>
                    </div>
                    
                    <div class="mobile-day-posts">
                        ${this.renderMobileDayPosts(dayPosts, dateStr)}
                        <button class="mobile-add-post" data-date="${dateStr}">
                            <i class="fas fa-plus"></i>
                            <span>Post hinzufügen</span>
                        </button>
                    </div>
                </div>
            `;
            
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        html += '</div>';
        return html;
    }
    
    renderWeekView() {
        const startOfWeek = this.getStartOfWeek(this.currentDate);
        let html = '<div class="calendar-week-view">';
        
        for (let i = 0; i < 7; i++) {
            const currentDate = new Date(startOfWeek);
            currentDate.setDate(currentDate.getDate() + i);
            const dateStr = this.formatDate(currentDate);
            const dayPosts = this.posts.get(dateStr) || [];
            const weekdayName = this.formatWeekday(currentDate);
            
            html += `
                <div class="week-day-column" data-date="${dateStr}">
                    <div class="week-day-header">
                        ${weekdayName}, ${currentDate.getDate()}. ${this.formatMonthShort(currentDate)}
                    </div>
                    <div class="week-day-content">
                        ${this.renderMobileDayPosts(dayPosts, dateStr)}
                        <button class="mobile-add-post" data-date="${dateStr}">
                            <i class="fas fa-plus"></i>
                            <span>Post hinzufügen</span>
                        </button>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        return html;
    }
    
    renderDayPosts(posts) {
        return posts.map(post => `
            <div class="calendar-post-item ${post.status}" 
                 data-post-id="${post.id}"
                 draggable="true"
                 tabindex="0"
                 role="button"
                 aria-label="Post: ${post.title}">
                <div class="calendar-post-status ${post.status}"></div>
                <span class="sr-only">Status: ${this.getStatusText(post.status)}</span>
                ${this.truncateText(post.title, 25)}
            </div>
        `).join('');
    }
    
    renderMobileDayPosts(posts, dateStr) {
        return posts.map(post => `
            <div class="mobile-post-item draggable-post" 
                 data-post-id="${post.id}"
                 data-date="${dateStr}"
                 tabindex="0"
                 role="button"
                 aria-label="Post: ${post.title}">
                <div class="mobile-post-status ${post.status}"></div>
                <div class="mobile-post-content">
                    <div class="mobile-post-title">${post.title}</div>
                    <div class="mobile-post-time">${post.time || 'Keine Zeit festgelegt'}</div>
                </div>
                <span class="sr-only">Status: ${this.getStatusText(post.status)}</span>
            </div>
        `).join('');
    }
    
    attachEventListeners() {
        // Navigation
        document.getElementById('prev-month')?.addEventListener('click', () => this.previousMonth());
        document.getElementById('next-month')?.addEventListener('click', () => this.nextMonth());
        
        // View Toggle
        document.querySelectorAll('.view-toggle-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.changeView(e.target.dataset.view));
        });
        
        // Drag and Drop für Desktop
        if (!this.isMobile()) {
            this.container.addEventListener('dragstart', (e) => this.handleDragStart(e));
            this.container.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.container.addEventListener('drop', (e) => this.handleDrop(e));
        }
        
        // Post-Clicks
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('.calendar-add-post, .mobile-add-post')) {
                const date = e.target.closest('[data-date]').dataset.date;
                this.addPost(date);
            } else if (e.target.closest('.calendar-post-item, .mobile-post-item')) {
                const postId = e.target.closest('[data-post-id]').dataset.postId;
                this.editPost(postId);
            }
        });
        
        // Keyboard Navigation
        this.container.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Window Resize
        window.addEventListener('resize', () => {
            clearTimeout(this.resizeTimeout);
            this.resizeTimeout = setTimeout(() => this.handleResize(), 250);
        });
    }
    
    initTouchGestures() {
        let startX, startY, currentX, currentY;
        let isSwipe = false;
        
        this.container.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            isSwipe = false;
            
            // Touch-Drag für Posts
            if (e.target.closest('.draggable-post')) {
                this.touchStartPos = { x: startX, y: startY };
                this.draggedElement = e.target.closest('.draggable-post');
                this.draggedElement.classList.add('dragging-mobile');
            }
        }, { passive: true });
        
        this.container.addEventListener('touchmove', (e) => {
            if (!startX || !startY) return;
            
            const touch = e.touches[0];
            currentX = touch.clientX;
            currentY = touch.clientY;
            
            const deltaX = Math.abs(currentX - startX);
            const deltaY = Math.abs(currentY - startY);
            
            // Swipe-Geste erkennen
            if (deltaX > 50 && deltaY < 30) {
                isSwipe = true;
                e.preventDefault();
            }
            
            // Drag-Geste für Posts
            if (this.draggedElement && (deltaX > 10 || deltaY > 10)) {
                e.preventDefault();
                this.updateDragPosition(currentX, currentY);
                this.highlightDropZones();
            }
        }, { passive: false });
        
        this.container.addEventListener('touchend', (e) => {
            if (isSwipe && startX && currentX) {
                const deltaX = currentX - startX;
                if (deltaX > 50) {
                    this.previousMonth();
                } else if (deltaX < -50) {
                    this.nextMonth();
                }
            }
            
            // Drop-Geste für Posts
            if (this.draggedElement) {
                const dropTarget = this.findDropTarget(currentX, currentY);
                if (dropTarget) {
                    this.handleMobileDrop(this.draggedElement, dropTarget);
                }
                
                this.draggedElement.classList.remove('dragging-mobile');
                this.draggedElement = null;
                this.clearDropZones();
            }
            
            startX = startY = currentX = currentY = null;
            isSwipe = false;
        }, { passive: true });
    }
    
    updateDragPosition(x, y) {
        if (!this.draggedElement) return;
        
        this.draggedElement.style.position = 'fixed';
        this.draggedElement.style.left = `${x - 50}px`;
        this.draggedElement.style.top = `${y - 25}px`;
        this.draggedElement.style.zIndex = '9999';
    }
    
    highlightDropZones() {
        document.querySelectorAll('.calendar-day, .mobile-card').forEach(day => {
            if (day !== this.draggedElement.closest('.calendar-day, .mobile-card')) {
                day.classList.add('drop-zone-mobile');
            }
        });
    }
    
    clearDropZones() {
        document.querySelectorAll('.drop-zone-mobile').forEach(el => {
            el.classList.remove('drop-zone-mobile');
        });
    }
    
    findDropTarget(x, y) {
        const elements = document.elementsFromPoint(x, y);
        return elements.find(el => 
            el.classList.contains('calendar-day') || 
            el.classList.contains('mobile-card')
        );
    }
    
    handleMobileDrop(draggedPost, dropTarget) {
        const postId = draggedPost.dataset.postId;
        const newDate = dropTarget.dataset.date;
        const oldDate = draggedPost.dataset.date;
        
        if (newDate && newDate !== oldDate) {
            this.movePost(postId, oldDate, newDate);
            this.announceChange(`Post wurde zu ${this.formatDateAria(new Date(newDate))} verschoben`);
        }
    }
    
    // Utility Methods
    formatMonth(date) {
        const months = [
            'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
            'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
        ];
        return `${months[date.getMonth()]} ${date.getFullYear()}`;
    }
    
    formatMonthShort(date) {
        const months = [
            'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
            'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'
        ];
        return months[date.getMonth()];
    }
    
    formatWeekday(date) {
        const weekdays = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
        return weekdays[date.getDay()];
    }
    
    formatDate(date) {
        return date.toISOString().split('T')[0];
    }
    
    formatDateAria(date) {
        return date.toLocaleDateString('de-DE', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        });
    }
    
    isToday(date) {
        const today = new Date();
        return date.toDateString() === today.toDateString();
    }
    
    getStartOfWeek(date) {
        const result = new Date(date);
        const day = result.getDay();
        const diff = result.getDate() - day;
        result.setDate(diff);
        return result;
    }
    
    truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    getStatusText(status) {
        const statusTexts = {
            'draft': 'Entwurf',
            'scheduled': 'Geplant',
            'published': 'Veröffentlicht'
        };
        return statusTexts[status] || status;
    }
    
    // Navigation Methods
    previousMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() - 1);
        this.renderCalendar();
        this.announceChange(`Navigiert zu ${this.formatMonth(this.currentDate)}`);
    }
    
    nextMonth() {
        this.currentDate.setMonth(this.currentDate.getMonth() + 1);
        this.renderCalendar();
        this.announceChange(`Navigiert zu ${this.formatMonth(this.currentDate)}`);
    }
    
    changeView(view) {
        this.viewMode = view;
        
        // Update active button
        document.querySelectorAll('.view-toggle-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });
        
        // Re-render calendar
        document.getElementById('calendar-content').innerHTML = this.renderCalendarGrid();
        this.announceChange(`Ansicht geändert zu ${view === 'month' ? 'Monatsansicht' : 'Wochenansicht'}`);
    }
    
    // Data Methods
    async loadPosts() {
        this.showLoading();
        
        try {
            // API-Aufruf mit korrekter URL
            const response = await fetch('/somi_plan/api/posts/calendar/');
            const data = await response.json();
            
            this.posts.clear();
            data.posts.forEach(post => {
                const date = post.scheduled_date || post.created_date;
                if (!this.posts.has(date)) {
                    this.posts.set(date, []);
                }
                this.posts.get(date).push(post);
            });
            
            this.renderCalendar();
        } catch (error) {
            console.error('Fehler beim Laden der Posts:', error);
            this.showError('Fehler beim Laden der Kalender-Daten');
        } finally {
            this.hideLoading();
        }
    }
    
    async movePost(postId, oldDate, newDate) {
        try {
            const response = await fetch(`/somi_plan/api/posts/${postId}/move/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ scheduled_date: newDate })
            });
            
            if (response.ok) {
                // Update local data
                const oldPosts = this.posts.get(oldDate) || [];
                const postIndex = oldPosts.findIndex(p => p.id == postId);
                
                if (postIndex > -1) {
                    const post = oldPosts.splice(postIndex, 1)[0];
                    post.scheduled_date = newDate;
                    
                    if (!this.posts.has(newDate)) {
                        this.posts.set(newDate, []);
                    }
                    this.posts.get(newDate).push(post);
                    
                    this.renderCalendar();
                }
            } else {
                throw new Error('Fehler beim Verschieben des Posts');
            }
        } catch (error) {
            console.error('Fehler beim Verschieben:', error);
            this.showError('Post konnte nicht verschoben werden');
        }
    }
    
    addPost(date) {
        window.location.href = `/somi_plan/create/?date=${date}`;
    }
    
    editPost(postId) {
        window.location.href = `/somi_plan/edit/${postId}/`;
    }
    
    // UI Helper Methods
    showLoading() {
        this.isLoading = true;
        const content = document.getElementById('calendar-content');
        content.innerHTML = this.renderSkeleton();
    }
    
    hideLoading() {
        this.isLoading = false;
    }
    
    renderSkeleton() {
        let html = '<div class="calendar-skeleton">';
        for (let i = 0; i < 42; i++) { // 6 Wochen × 7 Tage
            html += `
                <div class="calendar-skeleton-day">
                    <div class="skeleton-date"></div>
                    <div class="skeleton-post"></div>
                    <div class="skeleton-post"></div>
                </div>
            `;
        }
        html += '</div>';
        return html;
    }
    
    showError(message) {
        const content = document.getElementById('calendar-content');
        content.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
                <button class="btn btn-outline-danger btn-sm ms-3" onclick="calendar.loadPosts()">
                    Erneut versuchen
                </button>
            </div>
        `;
    }
    
    announceChange(message) {
        const announcements = document.getElementById('calendar-announcements');
        if (announcements) {
            announcements.textContent = message;
        }
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
    
    handleResize() {
        // Re-render calendar if switching between mobile/desktop
        const wasMobile = this.container.classList.contains('mobile-mode');
        const isMobile = this.isMobile();
        
        if (wasMobile !== isMobile) {
            this.container.classList.toggle('mobile-mode', isMobile);
            this.renderCalendar();
            
            if (isMobile && !wasMobile) {
                this.initTouchGestures();
            }
        }
    }
    
    handleKeyDown(e) {
        const focusedElement = document.activeElement;
        
        switch (e.key) {
            case 'ArrowLeft':
                if (focusedElement.classList.contains('calendar-day')) {
                    e.preventDefault();
                    this.navigateDay(focusedElement, -1);
                }
                break;
            case 'ArrowRight':
                if (focusedElement.classList.contains('calendar-day')) {
                    e.preventDefault();
                    this.navigateDay(focusedElement, 1);
                }
                break;
            case 'ArrowUp':
                if (focusedElement.classList.contains('calendar-day')) {
                    e.preventDefault();
                    this.navigateDay(focusedElement, -7);
                }
                break;
            case 'ArrowDown':
                if (focusedElement.classList.contains('calendar-day')) {
                    e.preventDefault();
                    this.navigateDay(focusedElement, 7);
                }
                break;
            case 'Enter':
            case ' ':
                if (focusedElement.classList.contains('calendar-day')) {
                    e.preventDefault();
                    this.addPost(focusedElement.dataset.date);
                }
                break;
        }
    }
    
    navigateDay(currentDay, offset) {
        const allDays = Array.from(document.querySelectorAll('.calendar-day'));
        const currentIndex = allDays.indexOf(currentDay);
        const newIndex = currentIndex + offset;
        
        if (newIndex >= 0 && newIndex < allDays.length) {
            allDays[newIndex].focus();
        }
    }
    
    handleDragStart(e) {
        if (e.target.classList.contains('calendar-post-item')) {
            this.draggedElement = e.target;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', e.target.outerHTML);
        }
    }
    
    handleDragOver(e) {
        if (e.target.closest('.calendar-day')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }
    }
    
    handleDrop(e) {
        e.preventDefault();
        const dropTarget = e.target.closest('.calendar-day');
        
        if (dropTarget && this.draggedElement) {
            const postId = this.draggedElement.dataset.postId;
            const oldDate = this.draggedElement.closest('.calendar-day').dataset.date;
            const newDate = dropTarget.dataset.date;
            
            if (newDate !== oldDate) {
                this.movePost(postId, oldDate, newDate);
            }
        }
        
        this.draggedElement = null;
    }
}

// Initialize calendar when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('calendar-container')) {
        window.calendar = new ResponsiveCalendar();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ResponsiveCalendar;
}