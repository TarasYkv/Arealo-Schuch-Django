/**
 * MyCut Timeline - Canvas-basierte Timeline-Komponente
 */
class MyCutTimeline {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        this.options = {
            trackHeight: 50,
            headerHeight: 30,
            rulerHeight: 25,
            minZoom: 0.1,
            maxZoom: 10,
            colors: {
                background: '#1a1a2e',
                track: '#16213e',
                trackAlt: '#1e2a4a',
                ruler: '#0f3460',
                rulerText: '#888',
                playhead: '#e94560',
                videoClip: '#e94560',
                audioClip: '#4a90d9',
                subtitleClip: '#9b59b6',
                textOverlay: '#2ecc71',
                selection: 'rgba(233, 69, 96, 0.3)',
                waveform: '#e94560',
                grid: '#2a2a4e'
            },
            ...options
        };

        this.tracks = [
            { id: 'video', name: 'Video', icon: 'fa-video', type: 'video' },
            { id: 'audio', name: 'Audio', icon: 'fa-volume-up', type: 'audio' },
            { id: 'subtitle', name: 'Untertitel', icon: 'fa-closed-captioning', type: 'subtitle' },
            { id: 'overlay', name: 'Text-Overlay', icon: 'fa-font', type: 'text_overlay' }
        ];

        this.clips = [];
        this.duration = 0;
        this.currentTime = 0;
        this.zoom = 1;
        this.scrollX = 0;
        this.selectedClip = null;
        this.dragging = null;
        this.trimming = null;
        this.waveformData = [];

        this.init();
    }

    init() {
        this.createCanvas();
        this.bindEvents();
        this.render();
    }

    createCanvas() {
        // Main canvas for timeline
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'timeline-canvas';
        this.ctx = this.canvas.getContext('2d');

        // Waveform canvas (offscreen for caching)
        this.waveformCanvas = document.createElement('canvas');
        this.waveformCtx = this.waveformCanvas.getContext('2d');

        // Clear container and add canvas
        this.container.innerHTML = '';
        this.container.appendChild(this.canvas);

        // Resize observer
        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(this.container);

        this.resize();
    }

    resize() {
        const rect = this.container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        this.width = rect.width;
        this.height = this.options.rulerHeight + (this.tracks.length * this.options.trackHeight);

        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.canvas.style.width = this.width + 'px';
        this.canvas.style.height = this.height + 'px';

        this.ctx.scale(dpr, dpr);

        // Resize waveform canvas
        this.waveformCanvas.width = this.width * dpr;
        this.waveformCanvas.height = this.options.trackHeight * dpr;

        this.renderWaveform();
        this.render();
    }

    bindEvents() {
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('mouseleave', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));
    }

    // Time <-> Pixel conversion
    timeToPixel(time) {
        const pixelsPerMs = (this.width - 100) / (this.duration / this.zoom);
        return 100 + (time * pixelsPerMs) - this.scrollX;
    }

    pixelToTime(pixel) {
        const pixelsPerMs = (this.width - 100) / (this.duration / this.zoom);
        return (pixel - 100 + this.scrollX) / pixelsPerMs;
    }

    // Data setters
    setDuration(duration) {
        this.duration = duration;
        this.render();
    }

    setCurrentTime(time) {
        this.currentTime = time;
        this.render();
    }

    setClips(clips) {
        this.clips = clips;
        this.render();
    }

    setWaveform(data) {
        this.waveformData = data;
        this.renderWaveform();
        this.render();
    }

    // Zoom controls
    zoomIn() {
        this.zoom = Math.min(this.options.maxZoom, this.zoom * 1.5);
        this.render();
    }

    zoomOut() {
        this.zoom = Math.max(this.options.minZoom, this.zoom / 1.5);
        this.render();
    }

    zoomToFit() {
        this.zoom = 1;
        this.scrollX = 0;
        this.render();
    }

    // Rendering
    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.width, this.height);

        this.renderBackground();
        this.renderRuler();
        this.renderTracks();
        this.renderClips();
        this.renderPlayhead();
    }

    renderBackground() {
        this.ctx.fillStyle = this.options.colors.background;
        this.ctx.fillRect(0, 0, this.width, this.height);
    }

    renderRuler() {
        const ctx = this.ctx;
        const h = this.options.rulerHeight;

        // Ruler background
        ctx.fillStyle = this.options.colors.ruler;
        ctx.fillRect(0, 0, this.width, h);

        // Track labels area
        ctx.fillStyle = this.options.colors.track;
        ctx.fillRect(0, 0, 100, this.height);

        if (this.duration === 0) return;

        // Calculate tick interval based on zoom
        const pixelsPerMs = (this.width - 100) / (this.duration / this.zoom);
        let tickInterval = 1000; // 1 second

        if (pixelsPerMs < 0.01) tickInterval = 60000; // 1 minute
        else if (pixelsPerMs < 0.05) tickInterval = 10000; // 10 seconds
        else if (pixelsPerMs < 0.1) tickInterval = 5000; // 5 seconds
        else if (pixelsPerMs > 0.5) tickInterval = 100; // 100ms

        // Draw ticks
        ctx.strokeStyle = this.options.colors.grid;
        ctx.fillStyle = this.options.colors.rulerText;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';

        const startTime = Math.floor(this.pixelToTime(100) / tickInterval) * tickInterval;
        const endTime = this.pixelToTime(this.width);

        for (let t = startTime; t <= endTime; t += tickInterval) {
            if (t < 0) continue;
            const x = this.timeToPixel(t);
            if (x < 100 || x > this.width) continue;

            // Tick line
            ctx.beginPath();
            ctx.moveTo(x, h - 10);
            ctx.lineTo(x, h);
            ctx.stroke();

            // Time label
            ctx.fillText(this.formatTime(t), x, h - 12);

            // Grid line
            ctx.globalAlpha = 0.1;
            ctx.beginPath();
            ctx.moveTo(x, h);
            ctx.lineTo(x, this.height);
            ctx.stroke();
            ctx.globalAlpha = 1;
        }
    }

    renderTracks() {
        const ctx = this.ctx;
        const startY = this.options.rulerHeight;

        this.tracks.forEach((track, i) => {
            const y = startY + (i * this.options.trackHeight);
            const isAlt = i % 2 === 1;

            // Track background
            ctx.fillStyle = isAlt ? this.options.colors.trackAlt : this.options.colors.track;
            ctx.fillRect(100, y, this.width - 100, this.options.trackHeight);

            // Track label
            ctx.fillStyle = this.options.colors.track;
            ctx.fillRect(0, y, 100, this.options.trackHeight);

            ctx.fillStyle = this.options.colors.rulerText;
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(track.name, 10, y + this.options.trackHeight / 2 + 4);

            // Track separator
            ctx.strokeStyle = this.options.colors.grid;
            ctx.beginPath();
            ctx.moveTo(0, y + this.options.trackHeight);
            ctx.lineTo(this.width, y + this.options.trackHeight);
            ctx.stroke();
        });

        // Render waveform on audio track
        const audioTrackIndex = this.tracks.findIndex(t => t.type === 'audio');
        if (audioTrackIndex >= 0 && this.waveformData.length > 0) {
            const y = startY + (audioTrackIndex * this.options.trackHeight);
            ctx.drawImage(this.waveformCanvas, 100, y, this.width - 100, this.options.trackHeight);
        }
    }

    renderWaveform() {
        const ctx = this.waveformCtx;
        const data = this.waveformData;
        const width = this.waveformCanvas.width;
        const height = this.waveformCanvas.height;
        const dpr = window.devicePixelRatio || 1;

        ctx.clearRect(0, 0, width, height);

        if (data.length === 0) return;

        ctx.fillStyle = this.options.colors.waveform;
        const barWidth = (width / dpr) / data.length;
        const centerY = (height / dpr) / 2;

        data.forEach((value, i) => {
            const barHeight = value * (height / dpr) * 0.8;
            ctx.fillRect(
                i * barWidth,
                centerY - barHeight / 2,
                Math.max(1, barWidth - 1),
                barHeight
            );
        });
    }

    renderClips() {
        const ctx = this.ctx;
        const startY = this.options.rulerHeight;

        this.clips.forEach(clip => {
            const trackIndex = this.tracks.findIndex(t => t.type === clip.clip_type);
            if (trackIndex < 0) return;

            const y = startY + (trackIndex * this.options.trackHeight) + 5;
            const x = this.timeToPixel(clip.start_time);
            const w = (clip.duration / this.duration) * (this.width - 100) * this.zoom;
            const h = this.options.trackHeight - 10;

            if (x + w < 100 || x > this.width) return; // Off screen

            // Clip color based on type
            let color = this.options.colors.videoClip;
            if (clip.clip_type === 'audio') color = this.options.colors.audioClip;
            else if (clip.clip_type === 'subtitle') color = this.options.colors.subtitleClip;
            else if (clip.clip_type === 'text_overlay') color = this.options.colors.textOverlay;

            // Selected state
            if (this.selectedClip && this.selectedClip.id === clip.id) {
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                ctx.strokeRect(Math.max(100, x), y, w, h);
            }

            // Clip body
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.roundRect(Math.max(100, x), y, w, h, 4);
            ctx.fill();

            // Trim handles
            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            ctx.fillRect(Math.max(100, x), y, 5, h);
            ctx.fillRect(Math.max(100, x) + w - 5, y, 5, h);

            // Clip label
            if (w > 50) {
                ctx.fillStyle = '#fff';
                ctx.font = '11px sans-serif';
                ctx.textAlign = 'left';
                const label = clip.text || clip.clip_type;
                ctx.fillText(label.substring(0, Math.floor(w / 8)), Math.max(105, x + 8), y + h / 2 + 4);
            }
        });
    }

    renderPlayhead() {
        if (this.duration === 0) return;

        const ctx = this.ctx;
        const x = this.timeToPixel(this.currentTime);

        if (x < 100 || x > this.width) return;

        // Playhead line
        ctx.strokeStyle = this.options.colors.playhead;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, this.height);
        ctx.stroke();

        // Playhead handle
        ctx.fillStyle = this.options.colors.playhead;
        ctx.beginPath();
        ctx.moveTo(x - 8, 0);
        ctx.lineTo(x + 8, 0);
        ctx.lineTo(x + 8, 10);
        ctx.lineTo(x, 18);
        ctx.lineTo(x - 8, 10);
        ctx.closePath();
        ctx.fill();

        ctx.lineWidth = 1;
    }

    // Event handlers
    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Check if clicking on ruler (seek)
        if (y < this.options.rulerHeight && x > 100) {
            const time = this.pixelToTime(x);
            this.onSeek && this.onSeek(Math.max(0, Math.min(time, this.duration)));
            this.dragging = { type: 'seek' };
            return;
        }

        // Check if clicking on a clip
        const clip = this.getClipAt(x, y);
        if (clip) {
            this.selectedClip = clip;
            this.onClipSelected && this.onClipSelected(clip);

            // Check for trim handles
            const clipX = this.timeToPixel(clip.start_time);
            const clipW = (clip.duration / this.duration) * (this.width - 100) * this.zoom;

            if (x < clipX + 10) {
                this.trimming = { clip, side: 'start', startX: x, originalStart: clip.start_time, originalDuration: clip.duration };
            } else if (x > clipX + clipW - 10) {
                this.trimming = { clip, side: 'end', startX: x, originalDuration: clip.duration };
            } else {
                this.dragging = { type: 'clip', clip, startX: x, originalStart: clip.start_time };
            }

            this.render();
            return;
        }

        this.selectedClip = null;
        this.onClipSelected && this.onClipSelected(null);
        this.render();
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Seek dragging
        if (this.dragging && this.dragging.type === 'seek') {
            const time = this.pixelToTime(x);
            this.onSeek && this.onSeek(Math.max(0, Math.min(time, this.duration)));
            return;
        }

        // Clip dragging
        if (this.dragging && this.dragging.type === 'clip') {
            const delta = x - this.dragging.startX;
            const timeDelta = this.pixelToTime(delta + 100) - this.pixelToTime(100);
            this.dragging.clip.start_time = Math.max(0, this.dragging.originalStart + timeDelta);
            this.render();
            return;
        }

        // Trimming
        if (this.trimming) {
            const delta = x - this.trimming.startX;
            const timeDelta = this.pixelToTime(delta + 100) - this.pixelToTime(100);

            if (this.trimming.side === 'start') {
                const newStart = Math.max(0, this.trimming.originalStart + timeDelta);
                const maxStart = this.trimming.originalStart + this.trimming.originalDuration - 100;
                this.trimming.clip.start_time = Math.min(newStart, maxStart);
                this.trimming.clip.duration = this.trimming.originalDuration - (this.trimming.clip.start_time - this.trimming.originalStart);
            } else {
                const newDuration = Math.max(100, this.trimming.originalDuration + timeDelta);
                this.trimming.clip.duration = newDuration;
            }

            this.render();
            return;
        }

        // Cursor style
        const clip = this.getClipAt(x, y);
        if (clip) {
            const clipX = this.timeToPixel(clip.start_time);
            const clipW = (clip.duration / this.duration) * (this.width - 100) * this.zoom;

            if (x < clipX + 10 || x > clipX + clipW - 10) {
                this.canvas.style.cursor = 'ew-resize';
            } else {
                this.canvas.style.cursor = 'grab';
            }
        } else if (y < this.options.rulerHeight && x > 100) {
            this.canvas.style.cursor = 'pointer';
        } else {
            this.canvas.style.cursor = 'default';
        }
    }

    onMouseUp(e) {
        if (this.dragging && this.dragging.type === 'clip') {
            this.onClipMoved && this.onClipMoved(this.dragging.clip);
        }
        if (this.trimming) {
            this.onClipTrimmed && this.onClipTrimmed(this.trimming.clip);
        }

        this.dragging = null;
        this.trimming = null;
    }

    onWheel(e) {
        e.preventDefault();

        if (e.ctrlKey || e.metaKey) {
            // Zoom
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            this.zoom = Math.max(this.options.minZoom, Math.min(this.options.maxZoom, this.zoom * delta));
        } else {
            // Scroll
            this.scrollX = Math.max(0, this.scrollX + e.deltaX + e.deltaY);
        }

        this.render();
    }

    onDoubleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const clip = this.getClipAt(x, y);
        if (clip) {
            this.onClipDoubleClick && this.onClipDoubleClick(clip);
        }
    }

    getClipAt(x, y) {
        const startY = this.options.rulerHeight;

        for (const clip of this.clips) {
            const trackIndex = this.tracks.findIndex(t => t.type === clip.clip_type);
            if (trackIndex < 0) continue;

            const clipY = startY + (trackIndex * this.options.trackHeight) + 5;
            const clipX = this.timeToPixel(clip.start_time);
            const clipW = (clip.duration / this.duration) * (this.width - 100) * this.zoom;
            const clipH = this.options.trackHeight - 10;

            if (x >= Math.max(100, clipX) && x <= clipX + clipW && y >= clipY && y <= clipY + clipH) {
                return clip;
            }
        }

        return null;
    }

    formatTime(ms) {
        const hours = Math.floor(ms / 3600000);
        const minutes = Math.floor((ms % 3600000) / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        const millis = Math.floor((ms % 1000) / 10);

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${seconds.toString().padStart(2, '0')}.${millis.toString().padStart(2, '0')}`;
    }

    // Public methods for clip manipulation
    splitClipAtPlayhead() {
        if (!this.selectedClip) return null;

        const clip = this.selectedClip;
        if (this.currentTime <= clip.start_time || this.currentTime >= clip.start_time + clip.duration) {
            return null;
        }

        const splitPoint = this.currentTime - clip.start_time;
        const newClip = {
            ...clip,
            id: Date.now(),
            start_time: this.currentTime,
            duration: clip.duration - splitPoint,
            source_start: clip.source_start + splitPoint
        };

        clip.duration = splitPoint;

        this.clips.push(newClip);
        this.render();

        this.onClipSplit && this.onClipSplit(clip, newClip);
        return newClip;
    }

    deleteSelectedClip() {
        if (!this.selectedClip) return;

        const index = this.clips.findIndex(c => c.id === this.selectedClip.id);
        if (index >= 0) {
            const deleted = this.clips.splice(index, 1)[0];
            this.selectedClip = null;
            this.render();
            this.onClipDeleted && this.onClipDeleted(deleted);
        }
    }

    destroy() {
        this.resizeObserver.disconnect();
        this.canvas.remove();
    }
}

// Export for use
window.MyCutTimeline = MyCutTimeline;
