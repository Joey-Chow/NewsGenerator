"""
Tests for src/agents/script_critic.py

Run with:
    python -m pytest tests/test_script_critic.py -v
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.state import AgentState, Scene, Storyboard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_storyboard(title="Test Story"):
    return Storyboard(
        title=title,
        scenes=[
            Scene(id=1, subtitle_text="Breaking news from the capital today"),
            Scene(id=2, subtitle_text="Officials confirmed the situation is under control"),
            Scene(id=3, subtitle_text="Experts say this will have lasting economic impact"),
        ],
    )


def _make_state(storyboards, retry_count=0):
    """Build a minimal AgentState dict for testing."""
    return {
        "draft_storyboards": storyboards,
        "script_critic_retry_count": retry_count,
        # Remaining required-ish keys — supply empty defaults so state.get() works
        "news_urls": [],
        "scraped_articles": [],
        "ready_to_render_storyboards": [],
        "generated_segments": [],
        "final_video_path": None,
        "youtube_url": None,
        "news_url": None,
        "raw_text": None,
        "headlines": None,
        "storyboard": None,
        "current_video_index": None,
        "audios_map": {},
        "images_map": {},
        "script_draft": None,
        "script_path": None,
        "audio_path": None,
        "captions_path": None,
        "video_path": None,
        "screenshot_paths": [],
        "user_feedback": None,
        "is_approved": False,
        "sentences": None,
        "image_critic_retry_count": 0,
        "script_critic_feedback": None,
        "image_critic_feedback": None,
    }


def _make_llm_response(accuracy, coherence, engagement, critique="Looks good."):
    """Return a mock LLM response object with JSON content."""
    payload = {
        "accuracy": accuracy,
        "coherence": coherence,
        "engagement": engagement,
        "critique": critique,
    }
    mock_response = MagicMock()
    mock_response.content = json.dumps(payload)
    return mock_response


# ---------------------------------------------------------------------------
# Test 1: Good storyboard — LLM scores all >= 4, feedback should be None
# ---------------------------------------------------------------------------

def test_script_critic_passes_good_storyboard():
    """When all scores are >= 4.0, the critic should clear feedback (return None)."""
    storyboard = _make_storyboard("Good Story")
    state = _make_state([storyboard], retry_count=0)

    mock_llm_instance = MagicMock()
    # avg = (5+4+4)/3 = 4.33 — above threshold
    mock_llm_instance.invoke.return_value = _make_llm_response(
        accuracy=5, coherence=4, engagement=4, critique="Well written."
    )

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch(
            "src.agents.script_critic.ChatGoogleGenerativeAI",
            return_value=mock_llm_instance,
        ):
            result = asyncio.run(
                __import__("src.agents.script_critic", fromlist=["script_critic_node"]).script_critic_node(state)
            )

    assert result["script_critic_feedback"] is None, (
        "Feedback should be None when scores pass the threshold."
    )
    # retry_count should NOT be incremented on pass
    assert result["script_critic_retry_count"] == 0


# ---------------------------------------------------------------------------
# Test 2: Bad storyboard — LLM scores < 4, feedback should be set and retry incremented
# ---------------------------------------------------------------------------

def test_script_critic_fails_bad_storyboard():
    """When scores are below 4.0, the critic should set feedback and increment retry_count."""
    storyboard = _make_storyboard("Bad Story")
    state = _make_state([storyboard], retry_count=0)

    mock_llm_instance = MagicMock()
    # avg = (2+2+2)/3 = 2.0 — below threshold
    mock_llm_instance.invoke.return_value = _make_llm_response(
        accuracy=2,
        coherence=2,
        engagement=2,
        critique="The script is incoherent and lacks factual grounding.",
    )

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch(
            "src.agents.script_critic.ChatGoogleGenerativeAI",
            return_value=mock_llm_instance,
        ):
            result = asyncio.run(
                __import__("src.agents.script_critic", fromlist=["script_critic_node"]).script_critic_node(state)
            )

    assert result["script_critic_feedback"] is not None, (
        "Feedback should be set when scores are below the threshold."
    )
    assert "incoherent" in result["script_critic_feedback"] or "below threshold" in result["script_critic_feedback"], (
        "Feedback should contain the LLM critique or a failure message."
    )
    assert result["script_critic_retry_count"] == 1, (
        "retry_count should be incremented from 0 to 1 on failure."
    )


# ---------------------------------------------------------------------------
# Test 3: Max retries reached — force-pass regardless of score
# ---------------------------------------------------------------------------

def test_script_critic_force_passes_at_max_retries():
    """When retry_count >= MAX_RETRIES (2), the critic must force-pass without calling the LLM."""
    storyboard = _make_storyboard("Any Story")
    state = _make_state([storyboard], retry_count=2)

    mock_llm_instance = MagicMock()
    # If the LLM were called it would return terrible scores, but it should NOT be called
    mock_llm_instance.invoke.return_value = _make_llm_response(
        accuracy=1, coherence=1, engagement=1, critique="Terrible."
    )

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch(
            "src.agents.script_critic.ChatGoogleGenerativeAI",
            return_value=mock_llm_instance,
        ):
            result = asyncio.run(
                __import__("src.agents.script_critic", fromlist=["script_critic_node"]).script_critic_node(state)
            )

    assert result["script_critic_feedback"] is None, (
        "Feedback should be None when max retries are reached (force-pass)."
    )
    # retry_count should remain 2, not be incremented further
    assert result["script_critic_retry_count"] == 2, (
        "retry_count should not be incremented beyond MAX_RETRIES."
    )
    # The LLM should not have been invoked at all
    mock_llm_instance.invoke.assert_not_called()
