import { AbsoluteFill, Composition, Img, Audio, staticFile, useVideoConfig } from 'remotion';
import React from 'react';
import './style.css';

// We will pass data via input props or read from a manifest file in public/
// For this MVP, let's assume we read props passed via CLI inputProps
// or we just hardcode/read a known file. Remotion has 'getInputProps()'.
import { getInputProps } from 'remotion';

const data = getInputProps();
console.log("Remotion Input Props:", data);

const NewsScene: React.FC = () => {
    const { width, height } = useVideoConfig();
    const { screenshotPath, audioPath, text } = data;

    // Use absolute paths or handle static files. 
    // Remotion handles absolute file paths if allowed, or we use standard img src.
    // NOTE: Remotion restricts file access. We might need to copy assets to public/ 
    // or use a local server. For local dev/render, absolute paths often work if unsafe features enabled.

    return (
        <AbsoluteFill style={{ flexDirection: 'row', backgroundColor: 'black' }}>
            {/* Left Side: Text */}
            <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 40,
                color: 'white',
                fontFamily: 'Helvetica, Arial, sans-serif'
            }}>
                <h1 style={{ fontSize: 20, lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
                    {text || 'News Update'}
                </h1>
            </div>

            {/* Right Side: Screenshot */}
            <div style={{ flex: 1, position: 'relative' }}>
                {/* @ts-ignore */}
                <Img src={staticFile(screenshotPath)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>

            {/* @ts-ignore */}
            {audioPath && <Audio src={staticFile(audioPath)} />}
        </AbsoluteFill>
    );
};

import { getAudioDurationInSeconds } from "@remotion/media-utils";

export const MyComposition = () => {
    return (
        <Composition
            id="NewsVideo"
            component={NewsScene}
            durationInFrames={150} // Fallback
            fps={30}
            width={1280}
            height={720}
            defaultProps={{
                screenshotPath: 'https://via.placeholder.com/1280x720',
                audioPath: '',
                text: 'Loading News...'
            }}
            calculateMetadata={async ({ props }) => {
                const { audioPath } = props as { audioPath: string };
                if (!audioPath) {
                    return { durationInFrames: 150 };
                }
                const audioUrl = staticFile(audioPath);
                try {
                    const durationInSeconds = await getAudioDurationInSeconds(audioUrl);
                    // Add 1 second buffer (30 frames)
                    return { durationInFrames: Math.ceil(durationInSeconds * 30) + 30 };
                } catch (e) {
                    console.error("Failed to get audio duration", e);
                    return { durationInFrames: 150 };
                }
            }}
        />
    );
};
