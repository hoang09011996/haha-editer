import { AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

// Hợp đồng với src/vidflow/quick/render.py (projects/<tên>/tmp/render-props.json).
// Đường dẫn tương đối public dir (= cấu trúc project: images/…, clips/…, audio/…, logo/…).
export type Shot = {
  n: number;
  src: string | null;
  kind: "image" | "video" | "blank";
  start: number;          // giây
  end: number;            // giây — = start của mốc sau (liền mạch)
  cont: boolean;          // nối cảnh với mốc trước
  fade: number;           // giây mờ chéo khi vào mốc (0 = cắt thẳng)
  rate: number;           // tốc độ phát clip (1 = trim)
  clipLen: number | null; // độ dài clip nguồn (giây)
};
export type Caption = { start: number; end: number; text: string };
export type VideoProps = {
  fps: number; width: number; height: number; duration: number;
  beats: Shot[]; audio: string | null; subtitles: Caption[];
  zoom: boolean; clipVolume: number;
  logo: string | null; music: string | null; musicVolume: number;
};
export const defaultProps: VideoProps = {
  fps: 30, width: 1920, height: 1080, duration: 10, beats: [], audio: null, subtitles: [],
  zoom: true, clipVolume: 0, logo: null, music: null, musicVolume: 0.12,
};

const BG = "#f6f1e3";
const COVER = { width: "100%", height: "100%", objectFit: "cover" } as const;
const toFrames = (s: number, fps: number) => Math.round(s * fps);

// Ảnh: phủ kín khung, zoom vào/ra xen kẽ theo thứ tự mốc.
const StillView: React.FC<{ src: string; index: number; frames: number; zoom: boolean }> = ({ src, index, frames, zoom }) => {
  const f = useCurrentFrame();
  const t = Math.min(1, f / Math.max(1, frames));
  const [a, b] = index % 2 === 0 ? [1.0, 1.08] : [1.08, 1.0];
  const scale = zoom ? a + (b - a) * t : 1;
  return <Img src={staticFile(src)} style={{ ...COVER, transform: `scale(${scale})` }} />;
};

// Clip: phát `play` khung đầu với tốc độ `rate`; sau đó (clip ngắn hơn mốc, hoặc phần chồng lúc mốc sau mờ vào)
// giữ khung cuối đã phát.
const ClipView: React.FC<{ shot: Shot; frames: number; fps: number; volume: number }> = ({ shot, frames, fps, volume }) => {
  const src = staticFile(shot.src as string);
  const playable = shot.clipLen ? Math.floor((shot.clipLen / shot.rate) * fps) : frames;
  const play = Math.max(1, Math.min(frames, playable));
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={play} name="clip">
        <OffthreadVideo src={src} playbackRate={shot.rate} volume={volume} muted={volume <= 0} style={COVER} />
      </Sequence>
      <Sequence from={play} name="giữ khung cuối">
        <Freeze frame={play - 1}>
          <OffthreadVideo src={src} playbackRate={shot.rate} muted style={COVER} />
        </Freeze>
      </Sequence>
    </AbsoluteFill>
  );
};

const BeatView: React.FC<{ shot: Shot; index: number; frames: number; fps: number; zoom: boolean; clipVolume: number }> = (
  { shot, index, frames, fps, zoom, clipVolume },
) => {
  const f = useCurrentFrame();
  const fadeFrames = toFrames(shot.fade, fps);
  const opacity = fadeFrames > 0 ? interpolate(f, [0, fadeFrames], [0, 1], { extrapolateRight: "clamp" }) : 1;
  return (
    <AbsoluteFill style={{ opacity, backgroundColor: BG, overflow: "hidden" }}>
      {shot.kind === "image" && shot.src ? <StillView src={shot.src} index={index} frames={frames} zoom={zoom} /> : null}
      {shot.kind === "video" && shot.src ? <ClipView shot={shot} frames={frames} fps={fps} volume={clipVolume} /> : null}
    </AbsoluteFill>
  );
};

const CaptionView: React.FC<{ text: string; size: number }> = ({ text, size }) => {
  const f = useCurrentFrame();
  const y = interpolate(f, [0, 6], [20, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: Math.round(size * 1.35) }}>
      <div style={{ transform: `translateY(${y}px)`, background: "rgba(0,0,0,0.62)", color: "white", fontFamily: "Arial, Helvetica, sans-serif",
        fontSize: size, fontWeight: 700, padding: `${Math.round(size * 0.23)}px ${Math.round(size * 0.5)}px`, borderRadius: Math.round(size * 0.35),
        maxWidth: "80%", textAlign: "center", lineHeight: 1.25 }}>
        {text}
      </div>
    </AbsoluteFill>
  );
};

const LogoView: React.FC<{ src: string; short: number }> = ({ src, short }) => (
  <AbsoluteFill style={{ alignItems: "flex-end", justifyContent: "flex-start", padding: Math.round(short * 0.04) }}>
    <Img src={staticFile(src)} style={{ height: Math.round(short * 0.09), opacity: 0.9 }} />
  </AbsoluteFill>
);

export const DoodleVideo: React.FC<VideoProps> = ({ fps, width, height, duration, beats, audio, subtitles, zoom, clipVolume, logo, music, musicVolume }) => {
  const short = Math.min(width, height);
  const total = Math.max(1, Math.ceil(duration * fps)); // = durationInFrames của Composition (Root.tsx)
  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      {beats.map((shot, i) => {
        const from = toFrames(shot.start, fps);
        // mốc cuối chạy tới hết composition (ceil) — tránh 1–2 khung nền trống do làm tròn
        const frames = Math.max(1, (i === beats.length - 1 ? total : toFrames(shot.end, fps)) - from);
        const next = beats[i + 1];
        const overlap = next ? toFrames(next.fade, fps) : 0; // mốc sau mờ dần đè lên mốc này → không lộ nền
        return (
          <Sequence key={shot.n} from={from} durationInFrames={frames + overlap} name={`${shot.n} ${shot.kind}`}>
            <BeatView shot={shot} index={i} frames={frames} fps={fps} zoom={zoom} clipVolume={clipVolume} />
          </Sequence>
        );
      })}
      {subtitles.map((c, i) => (
        <Sequence key={`c${i}`} from={toFrames(c.start, fps)} durationInFrames={Math.max(1, toFrames(c.end - c.start, fps))}>
          <CaptionView text={c.text} size={Math.round(short * 0.048)} />
        </Sequence>
      ))}
      {logo ? <LogoView src={logo} short={short} /> : null}
      {audio ? <Audio src={staticFile(audio)} /> : null}
      {music ? <Audio src={staticFile(music)} volume={musicVolume} loop /> : null}
    </AbsoluteFill>
  );
};
