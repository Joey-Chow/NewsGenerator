import os
import json
import base64
import uuid
import requests

async def reporter_node(state: dict):
    print("Reporter: Generating Audio using Volcano Engine...")
    script = state.get("script_draft", "")
    
    if not script:
        print("Reporter: No script found.")
        return {}

    # Load credentials
    APPID = os.getenv("VOLC_APPID")
    TOKEN = os.getenv("VOLC_ACCESS_TOKEN")
    # Default voice: BV700_streaming (Chinese Female) or similar. 
    # Valid options depend on the account. BV001_streaming is common generic.
    VOICE_TYPE = os.getenv("VOLC_VOICE_TYPE", "BV001_streaming") 
    CLUSTER = "volcano_tts"

    if not APPID or not TOKEN:
        print("Reporter: Error - Missing VOLC_APPID or VOLC_ACCESS_TOKEN environment variables.")
        return {}

    # Prepare API Request
    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    header = {"Authorization": f"Bearer;{TOKEN}"}
    request_json = {
        "app": {
            "appid": APPID,
            "token": "access_token",
            "cluster": CLUSTER
        },
        "user": {
            "uid": "news_generator_user"
        },
        "audio": {
            "voice_type": VOICE_TYPE,
            "encoding": "mp3",
            "speed_ratio": 1.15,
            "volume_ratio": 1.0,
            "pitch_ratio": 1.0,
        },
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": script,
            "text_type": "plain",
            "operation": "query",
            "with_timestamp": 1
        },
    }

    print(f"Reporter: Calling Volcano TTS API for voice {VOICE_TYPE}...")
    
    try:
        # Note: requests is synchronous. In a high-perf async app, use aiohttp.
        # For this agent flow, it's acceptable.
        resp = requests.post(api_url, json=request_json, headers=header)
        
        if resp.status_code != 200:
             print(f"Reporter: HTTP Error {resp.status_code} - {resp.text}")
             return {}

        resp_data = resp.json()
        
        if "data" in resp_data and resp_data.get("message") == "Success":
            audio_data = base64.b64decode(resp_data["data"])
            
            # Ensure output directory exists
            output_dir = "output/audio"
            os.makedirs(output_dir, exist_ok=True)
            
            file_id = os.urandom(4).hex()
            output_audio_path = f"{output_dir}/audio_{file_id}.mp3"
            
            with open(output_audio_path, "wb") as f:
                f.write(audio_data)
            
            print(f"Reporter: Audio saved to {output_audio_path}")

            # Handle Captions/Timestamps
            captions_path = None
            if "additions" in resp_data and "duration" in resp_data["additions"]:
                 # Some versions return base64 encoded additions, others plain. 
                 # Usually 'additions' is a dict or a base64 string.
                 # Let's check format. For 'query' usually it returns base64 string in 'additions' if complex?
                 # Or it is a direct object.
                 pass

            # Try to grab timestamp information directly if available
            # Note: The exact field for timestamps in the HTTP response varies by version.
            # Often it is in 'additions' -> 'frontend' -> 'phonemes'/'duration' or similar.
            # For simplicity, we dump the entire 'additions' or relevant parts to a json file to inspect/use.
            if "additions" in resp_data:
                 captions_path = f"{output_dir}/captions_{file_id}.json"
                 with open(captions_path, "w") as f:
                     json.dump(resp_data["additions"], f)
                 print(f"Reporter: Captions debug data saved to {captions_path}")

            return {"audio_path": output_audio_path, "captions_path": captions_path}
        else:
            print(f"Reporter: API Error Response: {resp_data}")
            return {}
            
    except Exception as e:
        print(f"Reporter: Exception during TTS generation: {e}")
        return {}
