import { Composition, staticFile } from "remotion";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import React from "react";

// Config wird zur Laufzeit geladen
interface VideoConfig {
  title: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  totalFrames: number;
  clips: number;
  titlePosition: string;
  watermark: boolean;
  // Overlay
  hasOverlay: boolean;
  overlayStart: number;
  overlayPosition: string;
  overlayWidth: number;
  overlayDuration: number;
  // Video Effekte
  introStyle: string;
  transitionStyle: string;
  lowerThirdText: string;
  lowerThirdStart: number;
  showProgressBar: boolean;
  progressBarColor: string;
  emojiAnimations: boolean;
  // Erweiterte Effekte
  kenBurnsEffect: boolean;
  colorGrading: string;
  quoteText: string;
  quoteAuthor: string;
  quoteTime: number;
  factBoxText: string;
  factBoxTime: number;
  // Audio
  backgroundMusic: string;
  hasMusicFile: boolean;
  musicVolume: number;
  soundEffects: boolean;
  audioDucking: boolean;
  // Diskussion
  isDiscussion: boolean;
  speaker1Name: string;
  speaker2Name: string;
}

interface Word {
  word: string;
  start: number;
  end: number;
}




// Helper function for overlay positioning
function getOverlayPosition(position: string): React.CSSProperties {
  const positions: Record<string, React.CSSProperties> = {
    "center": { top: "50%", left: "50%", transform: "translate(-50%, -50%)" },
    "top": { top: "5%", left: "50%", transform: "translateX(-50%)" },
    "bottom": { bottom: "15%", left: "50%", transform: "translateX(-50%)" },
    "left": { top: "50%", left: "5%", transform: "translateY(-50%)" },
    "right": { top: "50%", right: "5%", transform: "translateY(-50%)" },
    "top-left": { top: "5%", left: "5%" },
    "top-right": { top: "5%", right: "5%" },
    "bottom-left": { bottom: "15%", left: "5%" },
    "bottom-right": { bottom: "15%", right: "5%" },
  };
  return positions[position] || positions["center"];
}

// ============ ADVANCED EFFECT COMPONENTS ============

// Intro Effect Wrapper
const IntroEffect: React.FC<{ style: string; children: React.ReactNode }> = ({ style, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  if (style === 'none' || !style) return <>{children}</>;
  
  let transform = '';
  let opacity = 1;
  const introFrames = fps * 1.5; // 1.5 Sekunden Intro
  
  if (frame > introFrames) return <>{children}</>;
  
  switch (style) {
    case 'fade':
      opacity = interpolate(frame, [0, introFrames], [0, 1], { extrapolateRight: 'clamp' });
      break;
    case 'zoom':
      const scale = interpolate(frame, [0, introFrames], [1.5, 1], { extrapolateRight: 'clamp' });
      opacity = interpolate(frame, [0, introFrames * 0.5], [0, 1], { extrapolateRight: 'clamp' });
      transform = `scale(${scale})`;
      break;
    case 'slide_up':
      const slideY = interpolate(frame, [0, introFrames], [30, 0], { extrapolateRight: 'clamp' });
      opacity = interpolate(frame, [0, introFrames * 0.5], [0, 1], { extrapolateRight: 'clamp' });
      transform = `translateY(${slideY}%)`;
      break;
    case 'glitch':
      if (frame < introFrames * 0.7 && frame % 4 < 2) {
        const glitchX = (Math.sin(frame * 0.5) * 5);
        const glitchY = (Math.cos(frame * 0.3) * 3);
        transform = `translate(${glitchX}px, ${glitchY}px)`;
      }
      opacity = interpolate(frame, [0, introFrames * 0.5], [0.3, 1], { extrapolateRight: 'clamp' });
      break;
    case 'typewriter':
      opacity = frame < 5 ? 0 : 1;
      break;
  }
  
  return (
    <div style={{ opacity, transform, width: '100%', height: '100%' }}>
      {children}
    </div>
  );
};

// Ken Burns Effect for Video Clips
const KenBurnsVideo: React.FC<{ src: string; index: number }> = ({ src, index }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  
  const progress = frame / durationInFrames;
  const direction = index % 4;
  
  let scale, x, y;
  switch (direction) {
    case 0: // Zoom in, pan right
      scale = interpolate(progress, [0, 1], [1, 1.15]);
      x = interpolate(progress, [0, 1], [0, -3]);
      y = 0;
      break;
    case 1: // Zoom out, pan left
      scale = interpolate(progress, [0, 1], [1.15, 1]);
      x = interpolate(progress, [0, 1], [-3, 0]);
      y = 0;
      break;
    case 2: // Zoom in, pan up
      scale = interpolate(progress, [0, 1], [1, 1.12]);
      x = 0;
      y = interpolate(progress, [0, 1], [0, -2]);
      break;
    default: // Zoom out, pan down
      scale = interpolate(progress, [0, 1], [1.12, 1]);
      x = 0;
      y = interpolate(progress, [0, 1], [-2, 0]);
  }
  
  return (
    <div style={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      <OffthreadVideo
        src={src}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale}) translate(${x}%, ${y}%)`,
        }}
      />
    </div>
  );
};

// Transition Component
const TransitionOverlay: React.FC<{ 
  style: string; 
  clipIndex: number; 
  clipDuration: number;
}> = ({ style, clipIndex, clipDuration }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  if (style === 'cut' || !style) return null;
  
  const transitionFrames = fps * 0.5; // 0.5 Sekunden Transition
  const clipStartFrame = clipIndex * clipDuration;
  const localFrame = frame - clipStartFrame;
  
  // Nur am Anfang jedes Clips (außer dem ersten)
  if (clipIndex === 0 || localFrame < 0 || localFrame > transitionFrames) return null;
  
  let opacity = 0;
  let transform = '';
  
  switch (style) {
    case 'fade':
      opacity = interpolate(localFrame, [0, transitionFrames], [1, 0], { extrapolateRight: 'clamp' });
      return (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'black',
          opacity,
        }} />
      );
    case 'zoom':
      const scale = interpolate(localFrame, [0, transitionFrames], [1.5, 1], { extrapolateRight: 'clamp' });
      opacity = interpolate(localFrame, [0, transitionFrames], [0.5, 0], { extrapolateRight: 'clamp' });
      return (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'black',
          opacity,
          transform: `scale(${scale})`,
        }} />
      );
    case 'slide_left':
      const slideX = interpolate(localFrame, [0, transitionFrames], [100, 0], { extrapolateRight: 'clamp' });
      return (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'black',
          transform: `translateX(-${slideX}%)`,
        }} />
      );
    case 'slide_right':
      const slideXR = interpolate(localFrame, [0, transitionFrames], [100, 0], { extrapolateRight: 'clamp' });
      return (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'black',
          transform: `translateX(${slideXR}%)`,
        }} />
      );
  }
  
  return null;
};

// Emoji Animation Component
const EmojiPopup: React.FC<{ words: Word[]; emojiMap: Record<string, string> }> = ({ words, emojiMap }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;
  
  // Finde aktuelles Wort
  const currentWord = words.find(w => currentTime >= w.start && currentTime <= w.end);
  if (!currentWord) return null;
  
  // Prüfe ob Wort ein Emoji hat
  const wordLower = currentWord.word.toLowerCase().replace(/[^a-zäöü]/g, '');
  const emoji = emojiMap[wordLower];
  if (!emoji) return null;
  
  // Animation
  const wordProgress = (currentTime - currentWord.start) / (currentWord.end - currentWord.start);
  const scale = interpolate(wordProgress, [0, 0.3, 0.7, 1], [0, 1.2, 1, 0.8], { extrapolateRight: 'clamp' });
  const opacity = interpolate(wordProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const rotation = interpolate(wordProgress, [0, 0.5, 1], [-10, 10, 0], { extrapolateRight: 'clamp' });
  
  return (
    <div style={{
      position: 'absolute',
      top: '25%',
      right: 60,
      fontSize: 100,
      transform: `scale(${scale}) rotate(${rotation}deg)`,
      opacity,
    }}>
      {emoji}
    </div>
  );
};

// ============ VIDEO EFFECT COMPONENTS ============

// Progress Bar Component
const ProgressBar: React.FC<{ color: string }> = ({ color }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = (frame / durationInFrames) * 100;
  
  return (
    <div style={{
      position: 'absolute',
      bottom: 0,
      left: 0,
      width: '100%',
      height: 6,
      backgroundColor: 'rgba(255,255,255,0.3)',
    }}>
      <div style={{
        width: `${progress}%`,
        height: '100%',
        backgroundColor: color,
      }} />
    </div>
  );
};

// Lower Third Component
const LowerThird: React.FC<{ text: string; startFrame: number }> = ({ text, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const localFrame = frame - startFrame;
  if (localFrame < 0 || localFrame > fps * 5) return null;
  
  const slideIn = interpolate(localFrame, [0, 15], [100, 0], { extrapolateRight: 'clamp' });
  const fadeOut = interpolate(localFrame, [fps * 4, fps * 5], [1, 0], { extrapolateLeft: 'clamp' });
  
  return (
    <div style={{
      position: 'absolute',
      bottom: 100,
      left: 40,
      transform: `translateX(${slideIn}px)`,
      opacity: fadeOut,
    }}>
      <div style={{
        backgroundColor: 'rgba(0,0,0,0.8)',
        padding: '12px 24px',
        borderLeft: '4px solid #FFD700',
      }}>
        <span style={{
          color: 'white',
          fontSize: 28,
          fontWeight: 'bold',
        }}>
          {text}
        </span>
      </div>
    </div>
  );
};

// Color Grading Filter
const ColorGradingFilter: React.FC<{ type: string }> = ({ type }) => {
  const filters: Record<string, string> = {
    'none': 'none',
    'warm': 'sepia(20%) saturate(120%) brightness(105%)',
    'cold': 'saturate(90%) brightness(105%) hue-rotate(10deg)',
    'vintage': 'sepia(40%) contrast(90%) brightness(90%)',
    'neon': 'saturate(150%) contrast(110%) brightness(110%)',
    'bw': 'grayscale(100%) contrast(110%)',
    'cinematic': 'contrast(105%) saturate(85%) brightness(95%)',
  };
  
  if (type === 'none') return null;
  
  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      filter: filters[type] || 'none',
      pointerEvents: 'none',
    }} />
  );
};

// Quote Component
const AnimatedQuote: React.FC<{ text: string; author: string; startFrame: number }> = ({ text, author, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const localFrame = frame - startFrame;
  if (localFrame < 0 || localFrame > fps * 6) return null;
  
  const fadeIn = interpolate(localFrame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const fadeOut = interpolate(localFrame, [fps * 5, fps * 6], [1, 0], { extrapolateLeft: 'clamp' });
  const scale = interpolate(localFrame, [0, 30], [0.8, 1], { extrapolateRight: 'clamp' });
  
  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.7)',
      opacity: Math.min(fadeIn, fadeOut),
    }}>
      <div style={{
        transform: `scale(${scale})`,
        textAlign: 'center',
        padding: '0 60px',
      }}>
        <span style={{ fontSize: 80, color: '#FFD700' }}>&quot;</span>
        <p style={{
          fontSize: 42,
          color: 'white',
          fontStyle: 'italic',
          margin: '0 0 20px 0',
          lineHeight: 1.4,
        }}>
          {text}
        </p>
        {author && (
          <p style={{
            fontSize: 28,
            color: '#ccc',
            marginTop: 20,
          }}>
            — {author}
          </p>
        )}
      </div>
    </div>
  );
};

// Fact Box Component
const FactBox: React.FC<{ text: string; startFrame: number }> = ({ text, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const localFrame = frame - startFrame;
  if (localFrame < 0 || localFrame > fps * 5) return null;
  
  const slideIn = interpolate(localFrame, [0, 15], [-100, 0], { extrapolateRight: 'clamp' });
  const fadeOut = interpolate(localFrame, [fps * 4, fps * 5], [1, 0], { extrapolateLeft: 'clamp' });
  
  return (
    <div style={{
      position: 'absolute',
      top: 120,
      right: 40,
      transform: `translateX(${slideIn}%)`,
      opacity: fadeOut,
      maxWidth: '40%',
    }}>
      <div style={{
        backgroundColor: 'rgba(255, 215, 0, 0.95)',
        padding: '20px 25px',
        borderRadius: 12,
      }}>
        <div style={{ fontSize: 24, marginBottom: 8 }}>💡</div>
        <span style={{
          color: '#1a1a1a',
          fontSize: 26,
          fontWeight: 'bold',
          lineHeight: 1.3,
        }}>
          {text}
        </span>
      </div>
    </div>
  );
};

// Speaker Label for Discussion format
const SpeakerLabel: React.FC<{ name: string; side: 'left' | 'right'; isActive: boolean }> = ({ name, side, isActive }) => {
  const bgColor = side === 'left' ? '#2563eb' : '#dc2626';
  
  return (
    <div style={{
      position: 'absolute',
      bottom: 180,
      [side]: 40,
      opacity: isActive ? 1 : 0.5,
      transform: isActive ? 'scale(1.1)' : 'scale(1)',
    }}>
      <div style={{
        backgroundColor: bgColor,
        padding: '12px 24px',
        borderRadius: 8,
      }}>
        <span style={{
          color: 'white',
          fontSize: 24,
          fontWeight: 'bold',
        }}>
          {name}
        </span>
      </div>
    </div>
  );
};

// Emoji Map for keywords
const EMOJI_MAP: Record<string, string> = {
  'geld': '💰', 'euro': '💶', 'gehalt': '💵', 'verdienen': '🤑',
  'top': '🔥', 'beste': '🏆', 'wichtig': '⚡', 'achtung': '⚠️',
  'tipp': '💡', 'geheim': '🤫', 'neu': '✨', 'wow': '😮',
  'liebe': '❤️', 'gut': '👍', 'schlecht': '👎',
  'arbeit': '💼', 'job': '👔', 'chef': '👨‍💼', 'team': '👥',
};

// Subtitle Component
const Subtitle: React.FC<{ words: Word[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  const currentWord = words.find(
    (w) => currentTime >= w.start && currentTime <= w.end
  );

  if (!currentWord) return null;

  // Find context (3 words before and after)
  const currentIndex = words.indexOf(currentWord);
  const contextStart = Math.max(0, currentIndex - 2);
  const contextEnd = Math.min(words.length, currentIndex + 3);
  const contextWords = words.slice(contextStart, contextEnd);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 200,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        padding: "0 40px",
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.8)",
          padding: "15px 25px",
          borderRadius: 12,
          maxWidth: "90%",
        }}
      >
        <span
          style={{
            color: "white",
            fontSize: 42,
            fontWeight: "bold",
            fontFamily: "Arial, sans-serif",
            textAlign: "center",
            lineHeight: 1.3,
          }}
        >
          {contextWords.map((w, i) => (
            <span
              key={i}
              style={{
                color:
                  w.word === currentWord.word ? "#FFD700" : "white",
              }}
            >
              {w.word}{" "}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
};

// Title Component (immer sichtbar in ersten 5 Sekunden)
const Title: React.FC<{ title: string; position: string }> = ({ title, position }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(
    frame,
    [0, 10, fps * 4, fps * 5],
    [1, 1, 1, 0],
    { extrapolateRight: "clamp" }
  );

  // Position berechnen
  const positionStyle: React.CSSProperties = {
    top: position === 'top' ? 80 : position === 'center' ? '50%' : undefined,
    bottom: position === 'bottom' ? 200 : undefined,
    transform: position === 'center' ? 'translateY(-50%)' : undefined,
  };

  return (
    <div
      style={{
        position: "absolute",
        top: positionStyle.top,
        bottom: positionStyle.bottom,
        transform: positionStyle.transform,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity,
      }}
    >
      <div
        style={{
          backgroundColor: "#E53935",
          padding: "20px 40px",
          borderRadius: 16,
        }}
      >
        <span
          style={{
            color: "white",
            fontSize: 48,
            fontWeight: "bold",
            fontFamily: "Arial, sans-serif",
            textTransform: "uppercase",
          }}
        >
          {title}
        </span>
      </div>
    </div>
  );
};

// CTA Component (letzte 5 Sekunden)
const CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const ctaStart = durationInFrames - fps * 5;
  const localFrame = frame - ctaStart;

  if (frame < ctaStart) return null;

  const scale = spring({
    frame: localFrame,
    fps,
    config: { damping: 10, stiffness: 100 },
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 350,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          backgroundColor: "#4CAF50",
          padding: "25px 50px",
          borderRadius: 20,
          boxShadow: "0 8px 20px rgba(0,0,0,0.3)",
        }}
      >
        <span
          style={{
            color: "white",
            fontSize: 36,
            fontWeight: "bold",
            fontFamily: "Arial, sans-serif",
          }}
        >
          ✅ Folgen & Teilen!
        </span>
      </div>
    </div>
  );
};

// Watermark Component
const Watermark: React.FC = () => {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 30,
        right: 30,
        opacity: 0.6,
      }}
    >
      <span
        style={{
          color: "white",
          fontSize: 24,
          fontFamily: "Arial, sans-serif",
          textShadow: "2px 2px 4px rgba(0,0,0,0.5)",
        }}
      >
        workloom.de
      </span>
    </div>
  );
};

// Main Video Component
export const VidGenVideo: React.FC = () => {
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const frame = useCurrentFrame();

  // Load config and timestamps (in real implementation, these would be loaded from files)
  const [config, setConfig] = React.useState<VideoConfig | null>(null);
  const [words, setWords] = React.useState<Word[]>([]);

  React.useEffect(() => {
    // In production, load from staticFile
    fetch(staticFile("config.json"))
      .then((r) => r.json())
      .then(setConfig)
      .catch(() => {
        // Fallback config
        setConfig({
          title: "Video",
          duration: 48,
          width: 1080,
          height: 1920,
          fps: 30,
          totalFrames: 1440,
          clips: 3,
          watermark: false,
          hasOverlay: false,
          overlayStart: 5,
        });
      });

    fetch(staticFile("timestamps.json"))
      .then((r) => r.json())
      .then((data) => setWords(data.words || []))
      .catch(() => setWords([]));
  }, []);

  if (!config) {
    return <AbsoluteFill style={{ backgroundColor: "black" }} />;
  }

  // Calculate clip durations
  // Clip-Wechsel alle 3-5 Sekunden (4 Sek Durchschnitt)
  const clipDuration = fps * 4; // 4 Sekunden pro Clip

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* Intro Effect Wrapper */}
      <IntroEffect style={config.introStyle || 'none'}>
        {/* Background Videos with Ken Burns & Transitions */}
        {Array.from({ length: config.clips }).map((_, i) => (
          <Sequence
            key={i}
            from={i * clipDuration}
            durationInFrames={clipDuration}
          >
            {config.kenBurnsEffect ? (
              <KenBurnsVideo
                src={staticFile(`clip${i + 1}.mp4`)}
                index={i}
              />
            ) : (
              <OffthreadVideo
                src={staticFile(`clip${i + 1}.mp4`)}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            )}
            {/* Transition Overlay */}
            <TransitionOverlay 
              style={config.transitionStyle || 'cut'} 
              clipIndex={i} 
              clipDuration={clipDuration} 
            />
          </Sequence>
        ))}
      </IntroEffect>

      {/* Audio */}
      <Audio src={staticFile("voiceover.mp3")} />

      {/* Title (first 5 seconds) */}
      <Title title={config.title} position={config.titlePosition || 'top'} />

      {/* Subtitles */}
      {words.length > 0 && <Subtitle words={words} />}


      {/* Overlay (if exists) */}
      {config.hasOverlay && (
        <Sequence 
          from={config.overlayStart * fps}
          durationInFrames={config.overlayDuration > 0 ? config.overlayDuration * fps : undefined}
        >
          <div
            style={{
              position: "absolute",
              ...getOverlayPosition(config.overlayPosition || 'center'),
              width: `${config.overlayWidth || 60}%`,
            }}
          >
            <Img
              src={staticFile("overlay.png")}
              style={{ width: "100%", borderRadius: 16 }}
            />
          </div>
        </Sequence>
      )}


      {/* Progress Bar */}
      {config.showProgressBar && <ProgressBar color={config.progressBarColor || '#FFD700'} />}

      {/* Lower Third */}
      {config.lowerThirdText && config.lowerThirdStart > 0 && (
        <LowerThird text={config.lowerThirdText} startFrame={config.lowerThirdStart * fps} />
      )}

      {/* Color Grading Filter */}
      {config.colorGrading && config.colorGrading !== 'none' && (
        <ColorGradingFilter type={config.colorGrading} />
      )}

      {/* Quote */}
      {config.quoteText && config.quoteTime > 0 && (
        <AnimatedQuote text={config.quoteText} author={config.quoteAuthor || ''} startFrame={config.quoteTime * fps} />
      )}

      {/* Fact Box */}
      {config.factBoxText && config.factBoxTime > 0 && (
        <FactBox text={config.factBoxText} startFrame={config.factBoxTime * fps} />
      )}

      {/* Discussion Speaker Labels */}
      {config.isDiscussion && (
        <>
          <SpeakerLabel name={config.speaker1Name || 'Pro'} side="left" isActive={true} />
          <SpeakerLabel name={config.speaker2Name || 'Contra'} side="right" isActive={false} />
        </>
      )}

      {/* CTA (last 5 seconds) */}
      <CTA />

      {/* Watermark */}
      {config.watermark && <Watermark />}
    </AbsoluteFill>
  );
};

// Root Component
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VidGenVideo"
        component={VidGenVideo}
        durationInFrames={30 * 50}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
