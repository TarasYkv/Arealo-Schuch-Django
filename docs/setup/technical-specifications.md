# Technical Specifications - Multi-Stream Video Recording Application

## 🏗️ Detailed Architecture

### **Component Architecture**

```typescript
// Core Application Structure
src/
├── components/
│   ├── StreamCapture/
│   │   ├── CameraStream.tsx
│   │   ├── ScreenStream.tsx
│   │   ├── MonitorStream.tsx
│   │   └── StreamSelector.tsx
│   ├── Composition/
│   │   ├── CanvasComposer.tsx
│   │   ├── LayoutManager.tsx
│   │   ├── StreamPositioner.tsx
│   │   └── PreviewCanvas.tsx
│   ├── Recording/
│   │   ├── RecordingControls.tsx
│   │   ├── DurationTimer.tsx
│   │   └── RecordingStatus.tsx
│   └── Export/
│       ├── VideoExporter.tsx
│       └── DownloadManager.tsx
├── hooks/
│   ├── useStreamCapture.ts
│   ├── useCanvasComposition.ts
│   ├── useMediaRecorder.ts
│   └── useStreamSynchronization.ts
├── services/
│   ├── StreamService.ts
│   ├── CompositionService.ts
│   ├── RecordingService.ts
│   └── ExportService.ts
├── utils/
│   ├── streamUtils.ts
│   ├── canvasUtils.ts
│   └── fileUtils.ts
└── types/
    ├── stream.types.ts
    ├── composition.types.ts
    └── recording.types.ts
```

### **Core Interfaces**

```typescript
interface StreamConfiguration {
  id: string;
  type: 'camera' | 'screen' | 'monitor';
  constraints: MediaStreamConstraints;
  position: { x: number; y: number; width: number; height: number };
  zIndex: number;
  enabled: boolean;
}

interface CompositionLayout {
  id: string;
  name: string;
  aspectRatio: '9:16' | '16:9' | '1:1';
  streams: StreamConfiguration[];
  canvas: {
    width: number;
    height: number;
    backgroundColor: string;
  };
}

interface RecordingState {
  status: 'idle' | 'recording' | 'paused' | 'processing' | 'completed';
  duration: number;
  maxDuration: number;
  startTime?: number;
  mediaRecorder?: MediaRecorder;
  chunks: Blob[];
}
```

## 🎯 Implementation Details

### **1. Stream Capture Service**

```typescript
class StreamService {
  private streams = new Map<string, MediaStream>();
  
  async captureCamera(constraints?: MediaStreamConstraints): Promise<MediaStream> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1920, height: 1080, frameRate: 30 },
        audio: true,
        ...constraints
      });
      
      this.streams.set('camera', stream);
      return stream;
    } catch (error) {
      throw new Error(`Kamera-Zugriff fehlgeschlagen: ${error.message}`);
    }
  }
  
  async captureScreen(constraints?: DisplayMediaStreamConstraints): Promise<MediaStream> {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { 
          width: 1920, 
          height: 1080, 
          frameRate: 30,
          cursor: 'always'
        },
        audio: true,
        ...constraints
      });
      
      this.streams.set('screen', stream);
      return stream;
    } catch (error) {
      throw new Error(`Bildschirm-Aufnahme fehlgeschlagen: ${error.message}`);
    }
  }
  
  async getAvailableDevices(): Promise<MediaDeviceInfo[]> {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(device => 
      device.kind === 'videoinput' || device.kind === 'audiooutput'
    );
  }
  
  stopAllStreams(): void {
    this.streams.forEach(stream => {
      stream.getTracks().forEach(track => track.stop());
    });
    this.streams.clear();
  }
}
```

### **2. Canvas Composition Engine**

```typescript
class CompositionService {
  private canvas: HTMLCanvasElement;
  private context: CanvasRenderingContext2D;
  private animationFrame?: number;
  
  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.context = canvas.getContext('2d', { 
      alpha: false,
      desynchronized: true 
    })!;
    
    // Optimize canvas for performance
    this.context.imageSmoothingEnabled = true;
    this.context.imageSmoothingQuality = 'high';
  }
  
  startComposition(streams: Map<string, MediaStream>, layout: CompositionLayout): void {
    const videoElements = this.createVideoElements(streams);
    
    const render = () => {
      this.clearCanvas();
      
      layout.streams.forEach(streamConfig => {
        const video = videoElements.get(streamConfig.id);
        if (video && video.readyState >= 2) {
          this.drawStream(video, streamConfig);
        }
      });
      
      this.animationFrame = requestAnimationFrame(render);
    };
    
    render();
  }
  
  private createVideoElements(streams: Map<string, MediaStream>): Map<string, HTMLVideoElement> {
    const videoElements = new Map<string, HTMLVideoElement>();
    
    streams.forEach((stream, id) => {
      const video = document.createElement('video');
      video.srcObject = stream;
      video.autoplay = true;
      video.muted = true;
      video.playsInline = true;
      
      videoElements.set(id, video);
    });
    
    return videoElements;
  }
  
  private drawStream(video: HTMLVideoElement, config: StreamConfiguration): void {
    this.context.save();
    
    // Apply transformations
    this.context.globalAlpha = config.enabled ? 1.0 : 0.5;
    
    // Draw video frame
    this.context.drawImage(
      video,
      config.position.x,
      config.position.y,
      config.position.width,
      config.position.height
    );
    
    // Draw border if selected
    if (config.enabled) {
      this.context.strokeStyle = '#00ff00';
      this.context.lineWidth = 2;
      this.context.strokeRect(
        config.position.x,
        config.position.y,
        config.position.width,
        config.position.height
      );
    }
    
    this.context.restore();
  }
  
  private clearCanvas(): void {
    this.context.fillStyle = '#000000';
    this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }
  
  stopComposition(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }
  }
  
  captureStream(frameRate: number = 30): MediaStream {
    return this.canvas.captureStream(frameRate);
  }
}
```

### **3. Recording Service**

```typescript
class RecordingService {
  private mediaRecorder?: MediaRecorder;
  private recordedChunks: Blob[] = [];
  private state: RecordingState = {
    status: 'idle',
    duration: 0,
    maxDuration: 180000, // 3 minutes in ms
    chunks: []
  };
  
  async startRecording(compositionStream: MediaStream): Promise<void> {
    try {
      // Configure MediaRecorder
      const options: MediaRecorderOptions = {
        mimeType: this.getSupportedMimeType(),
        videoBitsPerSecond: 8000000, // 8 Mbps
        audioBitsPerSecond: 128000   // 128 kbps
      };
      
      this.mediaRecorder = new MediaRecorder(compositionStream, options);
      
      // Event handlers
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.recordedChunks.push(event.data);
        }
      };
      
      this.mediaRecorder.onstop = () => {
        this.state.status = 'completed';
      };
      
      this.mediaRecorder.onerror = (event) => {
        console.error('Aufnahme-Fehler:', event);
        this.state.status = 'idle';
      };
      
      // Start recording
      this.mediaRecorder.start(1000); // Collect data every second
      this.state.status = 'recording';
      this.state.startTime = Date.now();
      
      // Set maximum duration timer
      setTimeout(() => {
        if (this.state.status === 'recording') {
          this.stopRecording();
        }
      }, this.state.maxDuration);
      
    } catch (error) {
      throw new Error(`Aufnahme konnte nicht gestartet werden: ${error.message}`);
    }
  }
  
  stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        reject(new Error('Keine aktive Aufnahme gefunden'));
        return;
      }
      
      this.mediaRecorder.onstop = () => {
        const videoBlob = new Blob(this.recordedChunks, {
          type: this.getSupportedMimeType()
        });
        
        this.state.status = 'completed';
        resolve(videoBlob);
      };
      
      this.mediaRecorder.stop();
    });
  }
  
  pauseRecording(): void {
    if (this.mediaRecorder && this.state.status === 'recording') {
      this.mediaRecorder.pause();
      this.state.status = 'paused';
    }
  }
  
  resumeRecording(): void {
    if (this.mediaRecorder && this.state.status === 'paused') {
      this.mediaRecorder.resume();
      this.state.status = 'recording';
    }
  }
  
  private getSupportedMimeType(): string {
    const types = [
      'video/webm;codecs=vp9,opus',
      'video/webm;codecs=vp8,opus',
      'video/webm',
      'video/mp4'
    ];
    
    return types.find(type => MediaRecorder.isTypeSupported(type)) || 'video/webm';
  }
  
  getDuration(): number {
    if (this.state.startTime) {
      return Date.now() - this.state.startTime;
    }
    return 0;
  }
  
  getState(): RecordingState {
    return { ...this.state };
  }
}
```

### **4. React Hook Integration**

```typescript
// useMultiStreamRecorder.ts
export const useMultiStreamRecorder = () => {
  const [streams, setStreams] = useState<Map<string, MediaStream>>(new Map());
  const [layout, setLayout] = useState<CompositionLayout | null>(null);
  const [recordingState, setRecordingState] = useState<RecordingState>({
    status: 'idle',
    duration: 0,
    maxDuration: 180000,
    chunks: []
  });
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamService = useRef(new StreamService());
  const compositionService = useRef<CompositionService | null>(null);
  const recordingService = useRef(new RecordingService());
  
  useEffect(() => {
    if (canvasRef.current) {
      compositionService.current = new CompositionService(canvasRef.current);
    }
  }, []);
  
  const addCameraStream = useCallback(async () => {
    try {
      const stream = await streamService.current.captureCamera();
      setStreams(prev => new Map(prev.set('camera', stream)));
    } catch (error) {
      console.error('Kamera-Stream Fehler:', error);
    }
  }, []);
  
  const addScreenStream = useCallback(async () => {
    try {
      const stream = await streamService.current.captureScreen();
      setStreams(prev => new Map(prev.set('screen', stream)));
    } catch (error) {
      console.error('Bildschirm-Stream Fehler:', error);
    }
  }, []);
  
  const startRecording = useCallback(async () => {
    if (!compositionService.current || streams.size === 0) return;
    
    try {
      const compositionStream = compositionService.current.captureStream(30);
      await recordingService.current.startRecording(compositionStream);
      
      setRecordingState(prev => ({
        ...prev,
        status: 'recording',
        startTime: Date.now()
      }));
    } catch (error) {
      console.error('Aufnahme-Start Fehler:', error);
    }
  }, [streams]);
  
  const stopRecording = useCallback(async () => {
    try {
      const videoBlob = await recordingService.current.stopRecording();
      
      // Trigger download
      const url = URL.createObjectURL(videoBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aufnahme-${new Date().toISOString()}.webm`;
      a.click();
      URL.revokeObjectURL(url);
      
      setRecordingState(prev => ({
        ...prev,
        status: 'completed'
      }));
    } catch (error) {
      console.error('Aufnahme-Stop Fehler:', error);
    }
  }, []);
  
  return {
    streams,
    layout,
    recordingState,
    canvasRef,
    addCameraStream,
    addScreenStream,
    startRecording,
    stopRecording,
    setLayout
  };
};
```

## 🔧 Performance Optimizations

### **1. Canvas Rendering Optimization**

```typescript
class OptimizedCanvasRenderer {
  private offscreenCanvas: OffscreenCanvas;
  private worker: Worker;
  
  constructor(width: number, height: number) {
    this.offscreenCanvas = new OffscreenCanvas(width, height);
    this.worker = new Worker('/workers/canvas-worker.js');
    
    // Transfer canvas to worker
    this.worker.postMessage({
      type: 'init',
      canvas: this.offscreenCanvas
    }, [this.offscreenCanvas]);
  }
  
  render(streams: VideoStreamData[]): void {
    this.worker.postMessage({
      type: 'render',
      streams
    });
  }
}
```

### **2. Memory Management**

```typescript
class StreamMemoryManager {
  private streamPool = new Map<string, HTMLVideoElement[]>();
  private maxPoolSize = 5;
  
  getVideoElement(streamId: string): HTMLVideoElement {
    const pool = this.streamPool.get(streamId) || [];
    
    if (pool.length > 0) {
      return pool.pop()!;
    }
    
    return this.createVideoElement();
  }
  
  releaseVideoElement(streamId: string, element: HTMLVideoElement): void {
    const pool = this.streamPool.get(streamId) || [];
    
    if (pool.length < this.maxPoolSize) {
      element.srcObject = null;
      pool.push(element);
      this.streamPool.set(streamId, pool);
    } else {
      element.remove();
    }
  }
  
  private createVideoElement(): HTMLVideoElement {
    const video = document.createElement('video');
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    return video;
  }
  
  cleanup(): void {
    this.streamPool.forEach((pool, streamId) => {
      pool.forEach(video => {
        video.srcObject = null;
        video.remove();
      });
    });
    this.streamPool.clear();
  }
}
```

## 🌍 German Localization

```typescript
// locales/de.json
{
  "recording": {
    "start": "Aufnahme starten",
    "stop": "Aufnahme beenden",
    "pause": "Pausieren",
    "resume": "Fortsetzen",
    "duration": "Dauer",
    "maxDuration": "Max. Dauer",
    "status": {
      "idle": "Bereit",
      "recording": "Aufnahme läuft",
      "paused": "Pausiert",
      "processing": "Verarbeitung",
      "completed": "Abgeschlossen"
    }
  },
  "streams": {
    "camera": "Kamera",
    "screen": "Bildschirm",
    "monitor": "Monitor",
    "add": "Stream hinzufügen",
    "remove": "Stream entfernen",
    "configure": "Konfigurieren"
  },
  "layout": {
    "title": "Layout",
    "preset": "Vorlage",
    "custom": "Benutzerdefiniert",
    "position": "Position",
    "size": "Größe",
    "zindex": "Ebene"
  },
  "export": {
    "download": "Video herunterladen",
    "format": "Format",
    "quality": "Qualität",
    "processing": "Video wird verarbeitet..."
  },
  "errors": {
    "cameraAccess": "Kamera-Zugriff verweigert",
    "screenCapture": "Bildschirm-Aufnahme fehlgeschlagen",
    "recordingFailed": "Aufnahme fehlgeschlagen",
    "exportFailed": "Export fehlgeschlagen",
    "browserNotSupported": "Browser nicht unterstützt"
  }
}
```

## 🧪 Testing Framework

```typescript
// __tests__/StreamService.test.ts
describe('StreamService', () => {
  let streamService: StreamService;
  
  beforeEach(() => {
    streamService = new StreamService();
    
    // Mock navigator.mediaDevices
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {
        getUserMedia: jest.fn(),
        getDisplayMedia: jest.fn(),
        enumerateDevices: jest.fn()
      }
    });
  });
  
  describe('captureCamera', () => {
    it('should capture camera stream successfully', async () => {
      const mockStream = new MediaStream();
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockResolvedValue(mockStream);
      
      const stream = await streamService.captureCamera();
      
      expect(stream).toBe(mockStream);
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
        video: { width: 1920, height: 1080, frameRate: 30 },
        audio: true
      });
    });
    
    it('should handle camera access errors', async () => {
      (navigator.mediaDevices.getUserMedia as jest.Mock).mockRejectedValue(
        new Error('Permission denied')
      );
      
      await expect(streamService.captureCamera()).rejects.toThrow(
        'Kamera-Zugriff fehlgeschlagen: Permission denied'
      );
    });
  });
});
```

This technical specification provides comprehensive implementation details for building the multi-stream video recording application with all required features and German localization.