import { AbsoluteFill, Composition, Sequence, Img, Audio, Video, staticFile, useVideoConfig, getInputProps, OffthreadVideo, useCurrentFrame, interpolate, Easing } from 'remotion';
import React from 'react';
import './style.css';

// Define Prop Types
type SceneProp = {
    id: number;
    text: string;
    image: string; // This can be an image or a video filename in public/
    audio: string;
    duration: number; // in seconds
    title?: string; // Passed from parent
    isFirst?: boolean;
    isLast?: boolean;
}

type NewsVideoProps = {
    scenes: SceneProp[];
    title?: string;
    musicMood?: string;
    backgroundVideo?: string;
}

const NewsScene: React.FC<SceneProp> = ({ text, image, audio, title, isFirst, isLast, duration }) => {
    // Determine if asset is video or image based on extension
    const isVideo = image && (image.endsWith('.mp4') || image.endsWith('.mov') || image.endsWith('.webm'));

    const frame = useCurrentFrame();
    const { width, fps } = useVideoConfig();

    // Animation Logic
    const durationInFrames = Math.ceil((duration || 5) * fps);

    let translateX = 0;

    if (isFirst) {
        // Slide In from Right
        translateX = interpolate(frame, [0, 25], [width, 0], {
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.exp),
        });
    } else if (isLast) {
        // Slide Out to Left
        translateX = interpolate(frame, [durationInFrames - 25, durationInFrames], [0, -width], {
            extrapolateLeft: "clamp",
            easing: Easing.in(Easing.exp),
        });
    }

    return (
        <AbsoluteFill className="bg-transparent">
            {/* Visual Layer - Wrapper for Layout */}
            <div className="visual-layer-wrapper">

                {/* 
                   Content Container:
                   - Applies Entrance/Exit Animation to the WHOLE group
                   - Handles Flex Layout (Snapshot | Floating Frame)
                */}
                <div
                    className="content-layout-container"
                    style={{
                        transform: `translateX(${translateX}px)`,
                    }}
                >

                    {/* Main Visual Asset (Floating Frame - 70% or 100% of container) */}
                    <div className="floating-frame">
                        {/* Inset Stroke Overlay */}
                        {/* <div className="inset-overlay" /> */}

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

                {/* Headline Bar (Below Floating Frame) */}
                {title && (
                    <div className="headline-container">
                        {/* Layer 1: Channel Brand */}
                        <div className="headline-brand">全球每日快讯</div>

                        {/* Layer 2: Content */}
                        <div className="headline-content">
                            <div className="headline-live">
                                {/* @ts-ignore */}
                                <Img src={staticFile("logo2.png")} className="headline-logo-img" />
                            </div>
                            <div className="headline-title">{title}</div>
                        </div>
                    </div>
                )}
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

            {/* Sound Effect for Entrance */}
            {isFirst && (
                // @ts-ignore
                <Audio src={staticFile("swoosh.mp3")} startFrom={0} volume={0.5} />
            )}
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
    const videoTitle = props.title || inputProps.title || "NEWS UPDATE";

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
                {scenes.map((scene, index) => {
                    // Ensure duration is valid
                    const safeDuration = scene.duration > 0 ? scene.duration : 5;
                    const durationInFrames = Math.ceil(safeDuration * fps);
                    const from = currentFrame;
                    currentFrame += durationInFrames;

                    return (
                        <Sequence key={scene.id} from={from} durationInFrames={durationInFrames}>
                            <NewsScene
                                {...scene}
                                title={videoTitle}
                                isFirst={index === 0}
                                isLast={index === scenes.length - 1}
                            />
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
            width={2560}
            height={1440}
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
