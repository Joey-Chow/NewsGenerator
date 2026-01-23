from typing import TypedDict, List, Optional, Annotated, Dict, Any
import operator
from pydantic import BaseModel, Field

class Scene(BaseModel):
    id: int = Field(..., description="Scene ID (分镜序号)")
    subtitle_text: str = Field(..., description="Spoken text (中文台词)")
    visual_instruction: str = Field(..., description="Visual instructions for the human editor (e.g. 'Capture chart from original page').")
    
    # New image search field
    image_search_query: Optional[str] = Field(None, description="English search query for Google Images (e.g. 'Elon Musk speaking at conference').")

    # Filled later
    final_asset_path: Optional[str] = None # The actual file path used (image/video)
    audio_path: Optional[str] = None
    duration: Optional[float] = None

class Storyboard(BaseModel):
    scenes: List[Scene]
    title: str
    background_music_mood: str
    feedback: Optional[str] = None
    is_approved: bool = False
    sentences: Optional[List[str]] = None

class AgentState(TypedDict):
    news_url: str
    raw_text: Optional[str]
    headlines: Optional[List[str]]
    storyboard: Optional[Storyboard] 
    
    # --- Batch Processing ("GlobalState") ---
    news_urls: Optional[List[str]] # Queue of URLs to process
    current_video_index: Optional[int] # To track which video we are on (1, 2, 3...)
    
    # Store approved storyboards here until batch render time
    ready_to_render_storyboards: Annotated[List[Storyboard], operator.add] 
    
    generated_segments: Annotated[List[str], operator.add] # Accumulate paths
    final_video_path: Optional[str]
    # ----------------------------------------

    # Intermediate outputs for parallel execution
    # images_map not needed if we use asset_scraper -> human ingest flow which updates storyboard directly?
    # BUT reporter uses audios_map to avoid parallel overwrite issues with storyboard object.
    audios_map: Annotated[Dict[int, Dict[str, Any]], lambda x, y: {**x, **y}]
    
    # We might keep images_map just in case photographer is re-enabled or for compat
    images_map: Annotated[Dict[int, str], lambda x, y: {**x, **y}]

    # Legacy fields
    script_draft: Optional[str] 
    script_path: Optional[str]
    audio_path: Optional[str] 
    captions_path: Optional[str]
    video_path: Optional[str]
    screenshot_paths: Annotated[List[str], operator.add]
    user_feedback: Optional[str]
    is_approved: bool
    sentences: Optional[List[str]]
