/**
 * MyCut Waveform - Audio-Waveform Generator und Renderer
 */
class MyCutWaveform {
    constructor(options = {}) {
        this.options = {
            sampleRate: 44100,
            fftSize: 2048,
            samplesPerPixel: 256,
            color: '#e94560',
            backgroundColor: 'transparent',
            ...options
        };

        this.audioContext = null;
        this.audioBuffer = null;
        this.waveformData = [];
    }

    /**
     * Extract waveform data from audio/video file
     */
    async extractFromUrl(url) {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            const response = await fetch(url);
            const arrayBuffer = await response.arrayBuffer();
            this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

            this.waveformData = this.generateWaveformData();
            return this.waveformData;
        } catch (error) {
            console.error('Error extracting waveform:', error);
            return [];
        }
    }

    /**
     * Extract waveform from video element
     */
    async extractFromVideo(videoElement) {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Create media element source
            const source = this.audioContext.createMediaElementSource(videoElement);
            const analyser = this.audioContext.createAnalyser();
            analyser.fftSize = this.options.fftSize;

            source.connect(analyser);
            analyser.connect(this.audioContext.destination);

            // Get frequency data
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            // Sample over time
            const duration = videoElement.duration;
            const sampleCount = Math.ceil(duration * 10); // 10 samples per second
            const waveform = [];

            for (let i = 0; i < sampleCount; i++) {
                const time = (i / sampleCount) * duration;
                videoElement.currentTime = time;
                await new Promise(resolve => videoElement.addEventListener('seeked', resolve, { once: true }));

                analyser.getByteFrequencyData(dataArray);
                const average = dataArray.reduce((a, b) => a + b, 0) / bufferLength;
                waveform.push(average / 255);
            }

            videoElement.currentTime = 0;
            this.waveformData = waveform;
            return waveform;
        } catch (error) {
            console.error('Error extracting waveform from video:', error);
            return [];
        }
    }

    /**
     * Generate waveform data from audio buffer
     */
    generateWaveformData() {
        if (!this.audioBuffer) return [];

        const channelData = this.audioBuffer.getChannelData(0);
        const samples = channelData.length;
        const samplesPerPixel = this.options.samplesPerPixel;
        const numPixels = Math.ceil(samples / samplesPerPixel);
        const waveform = new Float32Array(numPixels);

        for (let i = 0; i < numPixels; i++) {
            const start = i * samplesPerPixel;
            const end = Math.min(start + samplesPerPixel, samples);

            let min = 1;
            let max = -1;

            for (let j = start; j < end; j++) {
                const sample = channelData[j];
                if (sample < min) min = sample;
                if (sample > max) max = sample;
            }

            // RMS value for better visualization
            waveform[i] = Math.max(Math.abs(min), Math.abs(max));
        }

        // Normalize
        const maxVal = Math.max(...waveform);
        if (maxVal > 0) {
            for (let i = 0; i < waveform.length; i++) {
                waveform[i] /= maxVal;
            }
        }

        return Array.from(waveform);
    }

    /**
     * Render waveform to canvas
     */
    renderToCanvas(canvas, data = null) {
        const waveform = data || this.waveformData;
        if (waveform.length === 0) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.width / dpr;
        const height = canvas.height / dpr;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (this.options.backgroundColor !== 'transparent') {
            ctx.fillStyle = this.options.backgroundColor;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
        }

        ctx.fillStyle = this.options.color;
        const barWidth = width / waveform.length;
        const centerY = height / 2;

        waveform.forEach((value, i) => {
            const barHeight = value * height * 0.8;
            ctx.fillRect(
                i * barWidth,
                centerY - barHeight / 2,
                Math.max(1, barWidth - 1),
                barHeight
            );
        });
    }

    /**
     * Create waveform image as data URL
     */
    toDataUrl(width = 800, height = 100) {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        this.renderToCanvas(canvas);
        return canvas.toDataURL('image/png');
    }

    /**
     * Generate simplified waveform for storage
     */
    getSimplifiedData(targetLength = 200) {
        if (this.waveformData.length === 0) return [];
        if (this.waveformData.length <= targetLength) return this.waveformData;

        const simplified = [];
        const step = this.waveformData.length / targetLength;

        for (let i = 0; i < targetLength; i++) {
            const start = Math.floor(i * step);
            const end = Math.floor((i + 1) * step);

            let max = 0;
            for (let j = start; j < end; j++) {
                max = Math.max(max, this.waveformData[j]);
            }
            simplified.push(max);
        }

        return simplified;
    }

    /**
     * Detect silence regions in audio
     */
    detectSilence(threshold = 0.05, minDuration = 1000) {
        if (this.waveformData.length === 0 || !this.audioBuffer) return [];

        const silences = [];
        const duration = this.audioBuffer.duration * 1000; // in ms
        const msPerSample = duration / this.waveformData.length;

        let silenceStart = null;

        this.waveformData.forEach((value, i) => {
            const time = i * msPerSample;

            if (value < threshold) {
                if (silenceStart === null) {
                    silenceStart = time;
                }
            } else {
                if (silenceStart !== null) {
                    const silenceDuration = time - silenceStart;
                    if (silenceDuration >= minDuration) {
                        silences.push({
                            start: silenceStart,
                            end: time,
                            duration: silenceDuration
                        });
                    }
                    silenceStart = null;
                }
            }
        });

        // Handle silence at end
        if (silenceStart !== null) {
            const silenceDuration = duration - silenceStart;
            if (silenceDuration >= minDuration) {
                silences.push({
                    start: silenceStart,
                    end: duration,
                    duration: silenceDuration
                });
            }
        }

        return silences;
    }

    /**
     * Calculate speech speed variation
     */
    analyzeSpeechSpeed(windowSize = 5000) {
        if (this.waveformData.length === 0 || !this.audioBuffer) return [];

        const duration = this.audioBuffer.duration * 1000;
        const msPerSample = duration / this.waveformData.length;
        const windowSamples = Math.ceil(windowSize / msPerSample);

        const speeds = [];

        for (let i = 0; i < this.waveformData.length - windowSamples; i += windowSamples / 2) {
            const window = this.waveformData.slice(i, i + windowSamples);

            // Count "active" samples (above threshold)
            const activeCount = window.filter(v => v > 0.1).length;
            const activity = activeCount / window.length;

            speeds.push({
                time: i * msPerSample,
                activity: activity,
                suggested_speed: activity < 0.3 ? 1.5 : (activity > 0.7 ? 0.9 : 1.0)
            });
        }

        return speeds;
    }

    destroy() {
        if (this.audioContext) {
            this.audioContext.close();
        }
        this.audioBuffer = null;
        this.waveformData = [];
    }
}

// Export for use
window.MyCutWaveform = MyCutWaveform;
