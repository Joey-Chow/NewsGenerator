# NewsGenerator: Automated News-to-Video Pipeline

NewsGenerator is an AI-powered system that transforms news articles into professional news videos. It uses LangGraph for workflow orchestration, Google Gemini for script generation, Azure TTS for voiceover, and Remotion for video rendering.

This repository contains two pipeline variants for comparative evaluation:

---

## Branch Structure

| Branch | Description |
|--------|-------------|
| `main` | **Baseline** — simple pipeline with HITL script review, no critic agents. Used as control group for evaluation |
| `critic-agent` | **Advanced** — full pipeline with dual critic agents (Script Critic + Image Critic), HITL, and evaluation dashboard |

---

## Key Features

- **Multi-Source Scraping**: Automatically extracts content from RSS feeds (The Globe and Mail, etc.) via Playwright.
- **AI-Powered Editorial**: Uses Gemini 2.0 Flash to generate video storyboards (scripts + image search queries) from scraped articles.
- **Human-in-the-Loop (HITL)**: Manual script review gate — human feedback loops back to the editor for revision.
- **Parallel Execution**: After script approval, Photographer (image search) and Reporter (TTS) run in parallel.
- **Azure TTS**: English voiceover using Azure's `en-US-AndrewMultilingualNeural` voice.
- **Automated Photographer**: Searches and downloads images via SerpApi based on storyboard scene queries.
- **Remotion Rendering**: React-based programmatic video engine for compositing scenes into final video.
- **Interactive UI**: Gradio dashboard for one-click generation and step-by-step testing.
- **LLM-as-Judge Evaluation**: Benchmark framework using Claude (script scoring) and GPT-4o (image scoring) via OpenRouter — different providers than the generation model to avoid self-evaluation bias.

---

## Pipeline Architecture (Baseline)

```
RSS Feed
   |
   v
Scheduler --> Scraper --> Editor --> Human Script Review
                                          |
                              +-----------+-----------+
                              | Feedback              | Approved
                              +-----> Editor    +-----+------+
                                                v            v
                                          Photographer    Reporter (TTS)
                                                |            |
                                                +-----+------+
                                                      v
                                                  Join Assets
                                                      |
                                                      v
                                                   Renderer
                                                      |
                                                      v
                                                    Concat
                                                      |
                                                      v
                                                   Youtuber
```

> See the `critic-agent` branch for the advanced architecture, which adds Script Critic and Image Critic nodes with automatic retry loops before the HITL gate and after the Photographer, respectively.

---

## Evaluation Framework

Located in `eval/`. Runs both pipeline versions on the same benchmark articles and scores outputs with independent LLM judges.

| File | Purpose |
|------|---------|
| `eval/benchmark_articles.json` | Fixed scraped articles for reproducible evaluation |
| `eval/run_eval.py` | Runs the pipeline on benchmark articles, saves outputs to `eval/results/` |
| `eval/score_outputs.py` | LLM-as-judge scoring — Claude for scripts, GPT-4o for images |

### Running Evaluation

```bash
# Score a completed pipeline run
python -m eval.score_outputs

# Full evaluation run (injects benchmark articles, runs pipeline, scores)
python -m eval.run_eval --version baseline    # this branch
python -m eval.run_eval --version advanced    # critic-agent branch
```

Results are saved to `eval/results/baseline/` or `eval/results/advanced/` as CSV + metadata JSON.

### Evaluation Judges

| Dimension | Judge Model | Provider | Metrics |
|-----------|------------|---------|---------|
| Script quality | `claude-sonnet-4-5` | OpenRouter | accuracy, coherence, engagement (1-5) |
| Image relevance | `gpt-4o` | OpenRouter | relevance (1-5) |

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
# Generation (Gemini 2.0 Flash)
GEMINI_API_KEY=your_key_here

# Image search (SerpApi)
SERPAPI_API_KEY=your_key_here

# Text-to-speech (Azure Cognitive Services)
AZURE_TTS_KEY=your_key_here
AZURE_TTS_REGION=eastus
AZURE_TTS_VOICE=en-US-AndrewMultilingualNeural

# Evaluation judges (via OpenRouter)
OPENROUTER_API_KEY=your_key_here

# LangSmith tracing (optional)
LANGSMITH_API_KEY=your_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=NewsGenerator
```

---

## Usage

### Gradio UI (Recommended)

```bash
python app.py
```

Open `http://127.0.0.1:7860`. The dashboard provides pipeline controls and storyboard inspection.

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
│   ├── graph.py               # LangGraph workflow (nodes, edges, HITL routing)
│   ├── state.py               # AgentState, Storyboard, Scene models
│   └── agents/
│       ├── scraper.py         # RSS fetch + article scraping
│       ├── editor.py          # Storyboard generation (Gemini)
│       ├── photographer.py    # Image search and download (SerpApi)
│       ├── reporter.py        # TTS audio generation (Azure)
│       ├── batch_renderer.py  # Remotion video rendering
│       ├── concat.py          # FFmpeg video assembly
│       └── youtuber.py        # YouTube upload + metadata
├── eval/
│   ├── benchmark_articles.json  # Fixed articles for evaluation
│   ├── run_eval.py              # Evaluation runner
│   ├── score_outputs.py         # LLM-as-judge scoring
│   └── results/                 # Evaluation outputs (scores.csv + metadata.json per version)
├── remotion_project/          # React/TypeScript video rendering engine
├── output/                    # Generated storyboards, audio, images, videos
└── assets/                    # Static assets (BGM, background video, logos)
```

---

## License

Internal Project / All Rights Reserved.
