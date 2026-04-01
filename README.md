# NewsGenerator: Automated News-to-Video Pipeline

NewsGenerator is an AI-powered system that transforms news articles into professional news videos. It uses LangGraph for workflow orchestration, Google Gemini for script generation and critique, Azure TTS for voiceover, and Remotion for video rendering.

This repository contains the **advanced version** of the pipeline (`critic-agent` branch), which adds two critic agents and an LLM-as-judge evaluation framework on top of the baseline pipeline.

---

## Branch Structure

| Branch | Description |
|--------|-------------|
| `critic-agent` | **Advanced** — full pipeline with critic agents, HITL, and evaluation framework (this branch) |
| `main` (`baseline`) | Frozen baseline — simple pipeline, no critics, no HITL. Used as control group for evaluation |

---

## Key Features

- **Dual Critic Agents**: A Script Critic evaluates generated storyboards for accuracy, coherence, and engagement before human review. An Image Critic (multimodal) checks image-scene relevance after the photographer runs. Both loop back to their respective agents on failure (max 2 retries).
- **Weighted Scoring**: Accuracy is weighted 2×, coherence 1.5×, engagement 1× — reflecting that factual correctness is most critical for news content.
- **Human-in-the-Loop (HITL)**: Manual script review gate after the script critic approves. Human feedback loops back to the editor.
- **Parallel Execution**: After human script approval, the Photographer and Reporter (TTS) run in parallel and join at the Renderer.
- **LLM-as-Judge Evaluation**: Separate evaluation pipeline using Claude (via OpenRouter) for script scoring and GPT-4o for image relevance scoring — different providers than the generation model (Gemini) to avoid self-evaluation bias.
- **Benchmark Dataset**: 5 fixed articles in `eval/benchmark_articles.json` for reproducible baseline vs. advanced comparison.

---

## Pipeline Architecture

```
RSS Feed
   │
   ▼
Scheduler ──► Scraper ──► Editor ──► Script Critic
                                          │
                              ┌───────────┴───────────┐
                              │ FAIL (retry ≤ 2)      │ PASS
                              └──────► Editor         ▼
                                              Human Script Review
                                                      │
                                          ┌───────────┴─────────────┐
                                          │ Feedback                │ Approved
                                          └──────► Editor    ┌──────┴──────┐
                                                             ▼             ▼
                                                       Photographer    Reporter (TTS)
                                                             │
                                                       Image Critic
                                                             │
                                              ┌─────────────┴─────────────┐
                                              │ FAIL (retry ≤ 2)          │ PASS
                                              └──────► Photographer       ▼
                                                                    Join Assets
                                                                          │
                                                                          ▼
                                                                      Renderer
                                                                          │
                                                                          ▼
                                                                        Concat
                                                                          │
                                                                          ▼
                                                                       Youtuber
```

---

## Critic Agent Details

### Script Critic (`src/agents/script_critic.py`)
- **Model**: Gemini 2.0 Flash
- **Trigger**: Automatically after Editor generates storyboards
- **Evaluates**: Each storyboard against its source article
- **Dimensions**: Accuracy (weight ×2), Coherence (weight ×1.5), Engagement (weight ×1)
- **Pass threshold**: Weighted average ≥ 4.0
- **On fail**: Returns scene-level feedback with concrete rewrite suggestions → loops to Editor
- **Max retries**: 2 (force-passes after to prevent infinite loops)

### Image Critic (`src/agents/image_critic.py`)
- **Model**: Gemini 2.0 Flash (Vision)
- **Trigger**: Automatically after Photographer fetches images
- **Evaluates**: Each (scene narration, image) pair for visual relevance
- **Fallback**: Text-only query evaluation when images are unavailable
- **On fail**: Updates `image_search_query` on failed scenes → loops to Photographer
- **Max retries**: 2

---

## Evaluation Framework

Located in `eval/`. Runs both pipeline versions on the same 5 benchmark articles and scores outputs with independent LLM judges.

### Files

| File | Purpose |
|------|---------|
| `eval/benchmark_articles.json` | 5 fixed scraped articles for reproducible evaluation |
| `eval/fetch_benchmark.py` | Script to refresh benchmark articles from live RSS |
| `eval/run_eval.py` | Runs the pipeline on benchmark articles, saves outputs to `eval/results/` |
| `eval/score_outputs.py` | LLM-as-judge scoring — Claude for scripts, GPT-4o for images |

### Running Evaluation

```bash
# Score a completed pipeline run
python -m eval.score_outputs

# Full evaluation run (injects benchmark articles, runs pipeline, scores)
python -m eval.run_eval --version advanced   # or --version baseline
```

Results are saved to `eval/results/advanced/` or `eval/results/baseline/` as CSV.

### Evaluation Judges

| Dimension | Judge Model | Provider | Metrics |
|-----------|------------|---------|---------|
| Script quality | `claude-sonnet-4-5` | OpenRouter | accuracy, coherence, engagement (1–5) |
| Image relevance | `gpt-4o` | OpenRouter | relevance (1–5) |

Using different providers than the generation model (Gemini) avoids self-evaluation bias.

---

## Prerequisites

- Python 3.10+
- Node.js 18+ & npm
- FFmpeg
- Playwright

---

## Installation

```bash
# 1. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install

# 2. Remotion rendering engine
cd remotion_project
npm install
cd ..
```

---

## Configuration

Create a `.env` file in the project root:

```env
# Generation
GEMINI_API_KEY=your_key_here

# Image search
SERPAPI_KEY=your_key_here

# Text-to-speech
AZURE_SPEECH_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here

# Evaluation judges (via OpenRouter)
OPENROUTER_API_KEY=your_key_here

# YouTube upload (optional)
YOUTUBE_CLIENT_SECRET_PATH=client_secret.json
```

---

## Usage

### Gradio UI (Recommended)

```bash
python app.py
```

Open `http://127.0.0.1:7860`. The dashboard provides pipeline controls, storyboard inspection, and an evaluation results tab.

### Console

```bash
python run.py
```

The pipeline pauses at the human script review step. Edit storyboards in `output/` if needed, then press Enter to continue.

### LangGraph Studio (Visual Debugging)

```bash
pip install "langgraph-cli[all]"
langgraph dev
```

---

## Project Structure

```
.
├── app.py                     # Gradio UI entry point
├── run.py                     # Console entry point
├── src/
│   ├── graph.py               # LangGraph workflow (nodes, edges, critic routing)
│   ├── state.py               # AgentState, Storyboard, Scene models
│   └── agents/
│       ├── scraper.py         # RSS fetch + article scraping
│       ├── editor.py          # Storyboard generation (Gemini)
│       ├── script_critic.py   # Script quality critic with retry loop
│       ├── photographer.py    # Image search and download (SerpApi)
│       ├── image_critic.py    # Multimodal image relevance critic
│       ├── reporter.py        # TTS audio generation (Azure)
│       ├── batch_renderer.py  # Remotion video rendering
│       ├── concat.py          # FFmpeg video assembly
│       └── youtuber.py        # YouTube upload + metadata
├── eval/
│   ├── benchmark_articles.json  # 5 fixed articles for evaluation
│   ├── run_eval.py              # Evaluation runner
│   ├── score_outputs.py         # LLM-as-judge scoring
│   ├── fetch_benchmark.py       # Benchmark refresh utility
│   └── results/                 # Evaluation outputs (baseline/ and advanced/)
├── remotion_project/          # React/TypeScript video rendering engine
├── output/                    # Generated storyboards, audio, images, videos
└── assets/                    # Static assets (BGM, background video, logos)
```

---

## License

Internal Project / All Rights Reserved.
