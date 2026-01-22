import { AbsoluteFill, Composition, Sequence, Img, Audio, Video, staticFile, useVideoConfig, getInputProps, OffthreadVideo } from 'remotion';
import React from 'react';
import './style.css';

// Define Prop Types
type SceneProp = {
    id: number;
    text: string;
    image: string; // This can be an image or a video filename in public/
    audio: string;
    duration: number; // in seconds
}

type NewsVideoProps = {
    scenes: SceneProp[];
    title?: string;
    musicMood?: string;
    backgroundVideo?: string;
}

const NewsScene: React.FC<SceneProp> = ({ text, image, audio }) => {
    // Determine if asset is video or image based on extension
    const isVideo = image && (image.endsWith('.mp4') || image.endsWith('.mov') || image.endsWith('.webm'));

    return (
        <AbsoluteFill className="bg-transparent">
            {/* Visual Layer (Image or Video) - Floating Frame */}
            <div className="visual-layer-wrapper">
                {/* Floating Frame Container */}
                <div className="floating-frame">
                    {/* Inset Stroke Overlay */}
                    <div className="inset-overlay" />

                    {image && (
                        isVideo ? (
                            // @ts-ignore
                            <Video src={staticFile(image)} className="visual-asset" />
                        ) : (
                            // @ts-ignore
                            <Img src={staticFile(image)} className="visual-asset" />
                        )
                    )}
                </div>
            </div>

            {/* Text Layer (Subtitle) - Frosted Glass Bar */}
            <div className="subtitle-bar">
                <h1 className="subtitle-text">
                    {text}
                </h1>
            </div>

            {/* Audio Layer */}
            {/* @ts-ignore */}
            {audio && <Audio src={staticFile(audio)} />}
        </AbsoluteFill>
    );
};

// @ts-ignore
const NewsSequence: React.FC<NewsVideoProps> = (props) => {
    const { fps } = useVideoConfig();

    // Fallback: Read from global input props if component props are empty
    // This handles cases where CLI props don't propagate automatically via Composition for some reason
    const inputProps = getInputProps() as NewsVideoProps;
    const scenes = (props.scenes && props.scenes.length > 0) ? props.scenes : inputProps.scenes;

    console.log(`NewsSequence: Resolved ${scenes ? scenes.length : 0} scenes.`);

    if (!scenes || scenes.length === 0) {
        return (
            <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', backgroundColor: 'black' }}>
                <h1 style={{ color: 'white' }}>No Scenes to Display</h1>
            </AbsoluteFill>
        );
    }

    let currentFrame = 0;

    const bgVideo = props.backgroundVideo || inputProps.backgroundVideo;

    return (
        <AbsoluteFill>
            {/* Dynamic Motion Background Layer */}
            {bgVideo && (
                <AbsoluteFill style={{ zIndex: 0 }}>
                    <OffthreadVideo
                        src={staticFile(bgVideo)}
                        style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                        }}
                        playbackRate={0.3}
                    // Note: If video is shorter than composition, we might need a Loop, 
                    // but sticking to base requirement first.
                    />
                </AbsoluteFill>
            )}

            {/* Content Layer */}
            <AbsoluteFill style={{ zIndex: 1 }}>
                {scenes.map((scene) => {
                    // Ensure duration is valid
                    const safeDuration = scene.duration > 0 ? scene.duration : 5;
                    const durationInFrames = Math.ceil(safeDuration * fps);
                    const from = currentFrame;
                    currentFrame += durationInFrames;

                    return (
                        <Sequence key={scene.id} from={from} durationInFrames={durationInFrames}>
                            <NewsScene {...scene} />
                        </Sequence>
                    );
                })}
            </AbsoluteFill>
        </AbsoluteFill>
    );
};

export const MyComposition = () => {
    return (
        <Composition
            id="NewsVideo"
            component={NewsSequence}
            durationInFrames={300}
            fps={30}
            width={1280}
            height={720}
            defaultProps={{
                scenes: []
            }}
            calculateMetadata={async ({ props }) => {
                const { scenes } = props as NewsVideoProps;
                console.log(`calculateMetadata: Received ${scenes ? scenes.length : 0} scenes.`);

                if (!scenes || scenes.length === 0) {
                    return { durationInFrames: 90 };
                }

                const totalDuration = scenes.reduce((acc, s) => acc + (s.duration || 5), 0);
                // Add a small buffer of 1 second (30 frames)
                return {
                    durationInFrames: Math.ceil(totalDuration * 30) + 30
                };
            }}
        />
    );
};
