import { AbsoluteFill, Composition, Img, Audio, staticFile, useVideoConfig } from 'remotion';
import React from 'react';
import './style.css';

// We will pass data via input props or read from a manifest file in public/
// For this MVP, let's assume we read props passed via CLI inputProps
// or we just hardcode/read a known file. Remotion has 'getInputProps()'.
import { getInputProps } from 'remotion';

const data = getInputProps();

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
                <h1 style={{ fontSize: 28, lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
                    {text ? text.substring(0, 150) + (text.length > 150 ? '...' : '') : 'News Update'}
                </h1>
            </div>

            {/* Right Side: Screenshot */}
            <div style={{ flex: 1, position: 'relative' }}>
                {/* @ts-ignore */}
                <Img src={screenshotPath} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>

            {/* @ts-ignore */}
            {audioPath && <Audio src={audioPath} />}
        </AbsoluteFill>
    );
};

export const MyComposition = () => {
    return (
        <Composition
            id="NewsVideo"
            component={NewsScene}
            durationInFrames={5 * 30} // 5 Seconds * 30fps
            fps={30}
            width={1280}
            height={720}
            defaultProps={{
                screenshotPath: 'https://via.placeholder.com/1280x720',
                audioPath: '',
                text: 'Loading News...'
            }}
        />
    );
};
