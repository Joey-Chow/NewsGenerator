import { AbsoluteFill, Composition, Sequence, Img, Audio, Video, staticFile, useVideoConfig, getInputProps } from 'remotion';
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
}

const NewsScene: React.FC<SceneProp> = ({ text, image, audio }) => {
    // Determine if asset is video or image based on extension
    const isVideo = image && (image.endsWith('.mp4') || image.endsWith('.mov') || image.endsWith('.webm'));

    return (
        <AbsoluteFill style={{ backgroundColor: 'black' }}>
            {/* Visual Layer (Image or Video) */}
            <div style={{ position: 'absolute', top: 0, width: '100%', height: '80%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                {image && (
                    isVideo ? (
                        // @ts-ignore
                        <Video src={staticFile(image)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    ) : (
                        // @ts-ignore
                        <Img src={staticFile(image)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    )
                )}
            </div>

            {/* Text Layer (Subtitle) */}
            <div style={{
                position: 'absolute',
                bottom: 0,
                width: '100%',
                height: '20%',
                backgroundColor: 'rgba(0,0,0,0.9)',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                padding: '0 40px'
            }}>
                <h1 style={{
                    color: 'white',
                    fontFamily: 'Helvetica, Arial, sans-serif',
                    fontSize: 40,
                    lineHeight: 1.2,
                    textAlign: 'center',
                    margin: 0
                }}>
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

    return (
        <AbsoluteFill>
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
