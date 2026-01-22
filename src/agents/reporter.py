import os
import edge_tts

async def reporter_node(state: dict):
    print("Reporter: Generating Audio...")
    script = state.get("script_draft", "")
    
    if not script:
        print("Reporter: No script found.")
        return {}

    # Generate Audio (MP3)
    output_audio_path = f"output/audio/audio_{os.urandom(4).hex()}.mp3"
    os.makedirs("output/audio", exist_ok=True)
    
    voice = "zh-CN-YunxiNeural" 
    
    print(f"Reporter: Generating TTS to {output_audio_path}...")
    communicate = edge_tts.Communicate(script, voice, rate="+20%", pitch="-2Hz")
    await communicate.save(output_audio_path)
    
    return {"audio_path": output_audio_path}
