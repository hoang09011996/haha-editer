import { AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

export type Shot = { src: string; start: number; end: number };
export type Caption = { start: number; end: number; text: string };
export type VideoProps = {
  fps: number; width: number; height: number;
  images: Shot[]; audio?: string | null; subtitles?: Caption[];
  zoom?: boolean; fadeFrames?: number;
};
export const defaultProps: VideoProps = { fps: 30, width: 1920, height: 1080, images: [], audio: null, subtitles: [], zoom: true, fadeFrames: 8 };

// Một ảnh: phủ kín khung (cover), zoom vào/ra xen kẽ, mờ dần khi xuất hiện.
const ShotView: React.FC<{ shot: Shot; index: number; frames: number; zoom: boolean; fade: number }> = ({ shot, index, frames, zoom, fade }) => {
  const f = useCurrentFrame();
  const t = Math.min(1, f / Math.max(1, frames));
  const [a, b] = index % 2 === 0 ? [1.0, 1.08] : [1.08, 1.0];
  const scale = zoom ? a + (b - a) * t : 1;
  const opacity = index === 0 ? 1 : interpolate(f, [0, fade], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity }}>
      <Img src={staticFile(shot.src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }} />
    </AbsoluteFill>
  );
};

const CaptionView: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  const y = interpolate(f, [0, 6], [20, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 70 }}>
      <div style={{ transform: `translateY(${y}px)`, background: "rgba(0,0,0,0.62)", color: "white", fontFamily: "Arial, Helvetica, sans-serif",
        fontSize: 52, fontWeight: 700, padding: "12px 26px", borderRadius: 18, maxWidth: "80%", textAlign: "center", lineHeight: 1.25 }}>
        {text}
      </div>
    </AbsoluteFill>
  );
};

export const DoodleVideo: React.FC<VideoProps> = ({ fps, images, audio, subtitles = [], zoom = true, fadeFrames = 8 }) => (
  <AbsoluteFill style={{ backgroundColor: "#f6f1e3" }}>
    {images.map((shot, i) => {
      const from = Math.round(shot.start * fps);
      const frames = Math.max(1, Math.round(shot.end * fps) - from);
      // ảnh sau phủ lên ảnh trước trong fadeFrames đầu → chuyển mờ dần, không có khung trống
      return (
        <Sequence key={i} from={from} durationInFrames={frames + (i < images.length - 1 ? fadeFrames : 0)} name={shot.src}>
          <ShotView shot={shot} index={i} frames={frames} zoom={zoom} fade={fadeFrames} />
        </Sequence>
      );
    })}
    {subtitles.map((c, i) => (
      <Sequence key={`c${i}`} from={Math.round(c.start * fps)} durationInFrames={Math.max(1, Math.round((c.end - c.start) * fps))}>
        <CaptionView text={c.text} />
      </Sequence>
    ))}
    {audio ? <Audio src={staticFile(audio)} /> : null}
  </AbsoluteFill>
);
