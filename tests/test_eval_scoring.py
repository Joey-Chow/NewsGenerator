# tests/test_eval_scoring.py
import pytest
import json
from unittest.mock import patch, MagicMock
from src.state import Storyboard, Scene


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


def _make_storyboard():
    return Storyboard(
        title="Test News",
        scenes=[
            Scene(id=1, subtitle_text="Breaking news about the economy", image_search_query="economy graph"),
            Scene(id=2, subtitle_text="Experts warn of recession", image_search_query="recession warning"),
        ]
    )


@pytest.mark.asyncio
async def test_score_script_returns_three_dimensions():
    """score_script should return accuracy, coherence, engagement scores (1-5)."""
    from eval.score_outputs import score_script

    mock_response = FakeLLMResponse(json.dumps({
        "accuracy": 4,
        "coherence": 5,
        "engagement": 3,
        "reasoning": "Good factual basis but dry language"
    }))

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("eval.score_outputs._get_llm", return_value=mock_llm):
        result = score_script(_make_storyboard(), source_article="The economy is slowing down...")
        assert "accuracy" in result
        assert "coherence" in result
        assert "engagement" in result
        assert all(1 <= result[k] <= 5 for k in ["accuracy", "coherence", "engagement"])
        assert "reasoning" in result


@pytest.mark.asyncio
async def test_score_script_with_source_grounding():
    """score_script should include the source article for fact-checking."""
    from eval.score_outputs import score_script

    mock_response = FakeLLMResponse(json.dumps({
        "accuracy": 2,
        "coherence": 4,
        "engagement": 4,
        "reasoning": "Script claims GDP grew 5% but source says 2%"
    }))

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("eval.score_outputs._get_llm", return_value=mock_llm):
        result = score_script(
            _make_storyboard(),
            source_article="GDP grew by 2% this quarter, below expectations."
        )
        # The function should pass the source article to the LLM
        call_args = mock_llm.invoke.call_args[0][0]
        # Check that source article appears in the messages
        messages_text = " ".join([m.content for m in call_args])
        assert "GDP grew by 2%" in messages_text


def test_score_image_returns_relevance():
    """score_image should return a relevance score (1-5) for an image+text pair."""
    from eval.score_outputs import score_image

    mock_response = FakeLLMResponse(json.dumps({
        "relevance": 4,
        "reasoning": "Image shows economic chart matching narration"
    }))

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    with patch("eval.score_outputs._get_llm", return_value=mock_llm), \
         patch("eval.score_outputs._encode_image", return_value="fake_base64"):
        result = score_image(
            scene_text="Experts warn of recession",
            image_path="/tmp/fake_image.jpg"
        )
        assert "relevance" in result
        assert 1 <= result["relevance"] <= 5
