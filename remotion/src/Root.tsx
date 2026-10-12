import { Composition } from "remotion";
import { DoodleVideo, VideoProps, defaultProps } from "./DoodleVideo";

// Props do `vidflow quick render` sinh (tmp/render-props.json). Độ dài = max(giọng đọc, mốc cuối) — tính sẵn ở Python.
export const RemotionRoot: React.FC = () => (
  <Composition
    id="DoodleVideo"
    component={DoodleVideo}
    defaultProps={defaultProps}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
    calculateMetadata={({ props }: { props: VideoProps }) => ({
      durationInFrames: Math.max(1, Math.ceil(props.duration * props.fps)),
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
