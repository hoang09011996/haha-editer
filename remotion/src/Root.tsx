import { Composition } from "remotion";
import { DoodleVideo, VideoProps, defaultProps } from "./DoodleVideo";

// Props do vidflow sinh ra (images/start/end, audio, subtitles). Độ dài video = ảnh cuối kết thúc.
export const RemotionRoot: React.FC = () => (
  <Composition
    id="DoodleVideo"
    component={DoodleVideo}
    defaultProps={defaultProps}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
    calculateMetadata={({ props }: { props: VideoProps }) => {
      const end = Math.max(1, ...props.images.map((i) => i.end));
      return { durationInFrames: Math.ceil(end * props.fps), fps: props.fps, width: props.width, height: props.height };
    }}
  />
);
