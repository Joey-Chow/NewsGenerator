import { AbsoluteFill, Composition, Img, Audio, staticFile, useVideoConfig, useCurrentFrame, getInputProps } from 'remotion';
import React, { useState, useEffect } from 'react';
import './style.css';

// We will pass data via input props or read from a manifest file in public/
// For this MVP, let's assume we read props passed via CLI inputProps
// or we just hardcode/read a known file. Remotion has 'getInputProps()'.


const data = getInputProps();
console.log("Remotion Input Props:", data);

const NewsScene: React.FC = () => {
    const { width, height, fps, durationInFrames } = useVideoConfig();
    const durationInSeconds = durationInFrames / fps;
    const frame = useCurrentFrame();
    const data = getInputProps();
    const { screenshotPath, audioPath, text, captionsPath, sentences } = data;

    const [captions, setCaptions] = useState<{ text: string; start: number; end: number }[]>([]);

    useEffect(() => {
        // Fallback or Primary Logic based on 'sentences' prop
        const generateCaptionsFromSentences = (sentenceList: string[]) => {
            const totalLength = sentenceList.reduce((acc, s) => acc + s.length, 0);
            let currentTime = 0;
            const generated = sentenceList.map(s => {
                const weight = s.length / totalLength;
                const duration = weight * durationInSeconds;
                const start = currentTime;
                const end = currentTime + duration;
                currentTime = end;
                return { text: s, start, end };
            });
            setCaptions(generated);
        };

        if (sentences && sentences.length > 0) {
            // Priority: Use the editor-provided sentences
            generateCaptionsFromSentences(sentences);
            return;
        }

        const generateFallbackCaptions = () => {
            if (!text) return;
            // Regex fallback if no 'sentences' prop
            // Remove period if requested (User said period should be deleted *after* splitting)
            // But here we just implementing lazy split.
            const rawSentences = text.split(/([。！？!?\n])/).filter(Boolean);
            const sentencesText: string[] = [];
            for (let i = 0; i < rawSentences.length; i += 2) {
                const s = rawSentences[i];
                // If user wants period removed, we don't append p. 
                // But this is the old valid fallback. I will keep it as is or try to serve request.
                // User said "Period should be deleted".
                // So we push s only.
                if (s.trim()) sentencesText.push(s.trim());
            }
            if (sentencesText.length > 0) {
                generateCaptionsFromSentences(sentencesText);
            }
        };

        if (!captionsPath) {
            generateFallbackCaptions();
            return;
        }

        const fetchCaptions = async () => {
            try {
                const res = await fetch(staticFile(captionsPath));
                if (!res.ok) throw new Error("Captions file not found");
                const data = await res.json();

                // If we have 'sentences' prop, we should ideally map these to timestamps.
                // But simplified logic: If explicit sentences exist, use them with proportional timing 
                // (ignoring detailed timestamp to ensure correct splitting).
                // Or try to align. Aligning is hard without advanced logic.
                // Given the User's strict parsing request ("Editor does the splitting"), 
                // we'll stick to 'generateCaptionsFromSentences' above if 'sentences' is present.
                // So this fetch is only if sentences prop is MISSING.

                // ... (Logic for reading Volcano words if needed)
                // But for now, if we returned early above, we don't reach here.

                // If we are here, it means NO sentences prop.
                // So we do the old logic with Volcano words.

                let words = [];
                if (Array.isArray(data)) words = data;
                else if (data.words) words = data.words;
                else if (data.payload && data.payload.words) words = data.payload.words;

                if (!words || words.length === 0) {
                    generateFallbackCaptions();
                    return;
                }

                // ... Old reconstruction logic ...
                // Group words into sentences based on punctuation in the words
                const reconstructedSentences: { text: string; start: number; end: number }[] = [];
                let currentSentence = "";
                let startTime = words[0].start_time !== undefined ? words[0].start_time : 0;
                if (startTime > 1000) startTime /= 1000;

                for (let i = 0; i < words.length; i++) {
                    const w = words[i];
                    const wordText = w.word || w.text || "";
                    currentSentence += wordText;

                    if (["。", "！", "？", "!", "?", "\n"].some(p => wordText.includes(p)) || i === words.length - 1) {
                        let endTime = w.end_time;
                        if (endTime > 1000) endTime /= 1000;

                        // Strip punctuation for display if possible? User asked for straight deletion.
                        const cleanText = currentSentence.replace(/[。！？!?\n]+$/, '');

                        reconstructedSentences.push({
                            text: cleanText,
                            start: startTime,
                            end: endTime
                        });
                        currentSentence = "";
                        if (i + 1 < words.length) {
                            startTime = words[i + 1].start_time;
                            if (startTime > 1000) startTime /= 1000;
                        }
                    }
                }
                setCaptions(reconstructedSentences);

            } catch (e) {
                console.warn("Failed to load captions, using fallback", e);
                generateFallbackCaptions();
            }
        };
        fetchCaptions();
    }, [captionsPath, text, durationInSeconds, sentences]);

    const currentTime = frame / fps;
    const currentCaption = captions.find(c => currentTime >= c.start && currentTime <= c.end);
    const displayText = currentCaption ? currentCaption.text : (text || "News Update");

    // Use absolute paths or handle static files. 
    // Remotion handles absolute file paths if allowed, or we use standard img src.
    // NOTE: Remotion restricts file access. We might need to copy assets to public/ 
    // or use a local server. For local dev/render, absolute paths often work if unsafe features enabled.

    return (
        <AbsoluteFill style={{ backgroundColor: 'black' }}>
            {/* Top: Screenshot Area (85%) */}
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '80%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}>
                {/* @ts-ignore */}
                <Img src={staticFile(screenshotPath)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>

            {/* Bottom: Subtitle/Caption Area (15%) */}
            <div style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                width: '100%',
                height: '20%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 40px',
                backgroundColor: 'rgba(0, 0, 0, 0.9)'
            }}>
                <h1 style={{
                    color: 'white',
                    fontFamily: 'Helvetica, Arial, sans-serif',
                    fontSize: 40,
                    lineHeight: 1.2,
                    textAlign: 'center',
                    margin: 0
                }}>
                    {displayText}
                </h1>
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
                captionsPath: '',
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
