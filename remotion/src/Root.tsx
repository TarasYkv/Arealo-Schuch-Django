import { Composition } from "remotion";
import { VidGenVideo } from "./VidGenVideo";

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
