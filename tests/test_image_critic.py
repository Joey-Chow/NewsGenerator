import pytest
import json
import os
from unittest.mock import patch, MagicMock
from src.state import Storyboard, Scene


def _make_scene(scene_id, text="Breaking news about economy", query=None, asset_path="/tmp/fake.jpg"):
    if query is None:
        query = f"query {scene_id}"
    return Scene(id=scene_id, subtitle_text=text, image_search_query=query, final_asset_path=asset_path)


def _make_storyboard(scenes=None):
    if scenes is None:
        scenes = [_make_scene(1), _make_scene(2)]
    return Storyboard(title="Test News", scenes=scenes)


def _make_state(storyboards=None, retry_count=0):
    return {
        "photographer_storyboards": storyboards or [_make_storyboard()],
        "image_critic_retry_count": retry_count,
        "image_critic_feedback": None,
    }


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
async def test_image_critic_passes_relevant_images():
    """All images score >= 3, critic passes."""
    from src.agents.image_critic import image_critic_node

    llm_response = json.dumps({
        "evaluations": [
            {"scene_id": 1, "relevance": 5, "reasoning": "Perfect match"},
            {"scene_id": 2, "relevance": 4, "reasoning": "Good match"},
        ],
        "passed": True,
    })

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch("src.agents.image_critic.ChatGoogleGenerativeAI") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = FakeLLMResponse(llm_response)
            MockLLM.return_value = mock_instance

            state = _make_state()
            result = await image_critic_node(state)

    assert result["image_critic_feedback"] is None


@pytest.mark.asyncio
async def test_image_critic_fails_irrelevant_images():
    """Some images score < 3, critic sets feedback with refined queries."""
    from src.agents.image_critic import image_critic_node

    llm_response = json.dumps({
        "evaluations": [
            {"scene_id": 1, "relevance": 1, "reasoning": "Image shows a cat, not economy", "refined_query": "US economy GDP growth chart press photo"},
            {"scene_id": 2, "relevance": 4, "reasoning": "Good match"},
        ],
        "passed": False,
    })

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch("src.agents.image_critic.ChatGoogleGenerativeAI") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.invoke.return_value = FakeLLMResponse(llm_response)
            MockLLM.return_value = mock_instance

            state = _make_state(retry_count=0)
            result = await image_critic_node(state)

    assert result["image_critic_feedback"] is not None
    assert result["image_critic_retry_count"] == 1
    # Check that the storyboard's scene 1 got its query updated
    updated_sbs = result["photographer_storyboards"]
    assert updated_sbs[0].scenes[0].image_search_query == "US economy GDP growth chart press photo"
    # Scene 2 should be unchanged
    assert updated_sbs[0].scenes[1].image_search_query == "query 2"


@pytest.mark.asyncio
async def test_image_critic_force_passes_at_max_retries():
    """At max retries, pass regardless."""
    from src.agents.image_critic import image_critic_node

    llm_response = json.dumps({
        "evaluations": [
            {"scene_id": 1, "relevance": 1, "reasoning": "Bad", "refined_query": "better query"},
        ],
        "passed": False,
    })

    with patch("src.agents.image_critic.ChatGoogleGenerativeAI") as MockLLM:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = FakeLLMResponse(llm_response)
        MockLLM.return_value = mock_instance

        state = _make_state(retry_count=2)
        result = await image_critic_node(state)

    assert result["image_critic_feedback"] is None
