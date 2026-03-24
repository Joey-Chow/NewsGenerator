
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def test_azure_tts():
    AZURE_KEY = os.getenv("AZURE_TTS_KEY")
    AZURE_REGION = os.getenv("AZURE_TTS_REGION")
    AZURE_VOICE = os.getenv("AZURE_TTS_VOICE", "en-US-AndrewMultilingualNeural")

    if not AZURE_KEY or not AZURE_REGION:
        print("Error: Missing AZURE_TTS_KEY or AZURE_TTS_REGION in .env")
        return

    print(f"Testing Azure TTS in {AZURE_REGION} with voice {AZURE_VOICE}...")

    api_url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "NewsGeneratorTest"
    }

    text = "This is a test of the News Generator's English voiceover using Microsoft Azure's multilingual neural voice. Audio generated successfully."
    
    # Escape XML special characters in text
    xml_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&apos;")
    
    ssml = f"""<speak version='1.0' xml:lang='en-US'>
        <voice xml:lang='en-US' xml:gender='Male' name='{AZURE_VOICE}'>
            {xml_text}
        </voice>
    </speak>"""

    try:
        os.makedirs("output/test", exist_ok=True)
        resp = requests.post(api_url, data=ssml.encode('utf-8'), headers=headers)
        if resp.status_code == 200:
            output_path = "output/test/test_azure_tts.mp3"
            with open(output_path, "wb") as f:
                f.write(resp.content)
            print(f"Success! Audio saved to {output_path}")
            print(f"File size: {os.path.getsize(output_path)} bytes")
        else:
            print(f"API Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error during TTS test: {e}")

if __name__ == "__main__":
    test_azure_tts()
