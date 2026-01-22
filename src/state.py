from typing import TypedDict, List, Optional, Annotated
import operator

class AgentState(TypedDict):
    news_url: str
    raw_text: Optional[str]
    headlines: Optional[List[str]]
    script_draft: Optional[str]
    script_path: Optional[str]
    audio_path: Optional[str]
    captions_path: Optional[str]
    video_path: Optional[str]
    screenshot_paths: Annotated[List[str], operator.add]
    user_feedback: Optional[str]
    is_approved: bool
    sentences: Optional[List[str]]
