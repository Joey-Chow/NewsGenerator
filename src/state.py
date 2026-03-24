from typing import TypedDict, List, Optional, Annotated, Dict, Any
import operator
from pydantic import BaseModel, Field

class Scene(BaseModel):
    id: int = Field(..., description="Scene ID (分镜序号)")
    subtitle_text: str = Field(..., description="Spoken text (中文台词)")
    
    # New image search field
    image_search_query: Optional[str] = Field(None, description="English search query for Google Images (e.g. 'Elon Musk speaking at conference').")

    # Filled later
    final_asset_path: Optional[str] = None # The actual file path used (image/video)
    audio_path: Optional[str] = None
    duration: Optional[float] = None

class Storyboard(BaseModel):
    title: str
    scenes: List[Scene]
    feedback: Optional[str] = None
    is_approved: bool = False
    sentences: Optional[List[str]] = None

class AgentState(TypedDict):
    # --- Batch Processing Fields ---
    news_urls: List[str] # Input list of URLs
    
    # Stage 1 Output: Scraped content
    scraped_articles: List[Dict] 
    
    # Stage 2 Output: Initial scripts
    draft_storyboards: List[Storyboard] 
    
    # Stage 4/5 Output: Finalized for rendering
    ready_to_render_storyboards: List[Storyboard] 
    
    # Stage 6 Output
    generated_segments: List[str]
    final_video_path: Optional[str]
    youtube_url: Optional[str]
    
    # --- Deprecated / Temporary / Loop Fields ---
    # These might be used inside nodes locally but shouldn't retain state across stages ideally
    news_url: Optional[str]
    raw_text: Optional[str]
    headlines: Optional[List[str]]
    storyboard: Optional[Storyboard] 
    current_video_index: Optional[int] 
    
    # Intermediate outputs for parallel execution (Legacy support)
    audios_map: Annotated[Dict[int, Dict[str, Any]], lambda x, y: {**x, **y}]
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
