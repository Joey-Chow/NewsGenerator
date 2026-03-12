# 🗞️ NewsGenerator: Automated News-to-Video Pipeline

NewsGenerator is a powerful automation system designed to transform news articles from various URLs into high-quality, professional-looking news videos. It leverages Large Language Models (LLMs) for script generation, LangGraph for workflow orchestration, and Remotion for programmatic video rendering.

## 🚀 Key Features

- **Multi-Source Scraping**: Automatically extracts content from a list of URLs (BBC, WSJ, etc.).
- **AI-Powered Editorial**: Uses LLMs to refine news content, write scripts (in Chinese), and generate visual instructions (storyboards).
- **Human-in-the-Loop (HITL)**: Provides three strategic manual review points to ensure quality:
  1.  **Scraper Review**: Verify and edit scraped news data.
  2.  **Script Review**: Polish the generated script and visual prompts.
  3.  **Asset Review**: Double-check or replace downloaded images/videos before rendering.
- **Automated Asset Sourcing**: Automatically searches and downloads images based on the generated storyboard.
- **High-Quality Rendering**: Uses **Remotion** (React/TypeScript) to render pixel-perfect video segments.
- **Smart Concatenation**: Merges individual news segments into a final full-length video, including background music and intro/outro management.

## 🏗️ Architecture & Workflow

The system is built as a **StateGraph** using LangGraph, ensuring a robust and resumable workflow.

```mermaid
graph TD
    S[Scheduler] --> B[Batch Scraper]
    B --> BS["⏸️ Scraper Review (Manual)"]
    BS --> E[Batch Editor]
    E --> SR["⏸️ Script Review (Manual)"]
    SR --> AS[Batch Asset Scraper]
    AS --> AR["⏸️ Asset Review (Manual)"]
    AR --> R[Batch Reporter]
    R --> BR[Batch Renderer]
    BR --> C[Concat]
    C --> Y[Youtuber]
    Y --> END((End))
```

### Core Components

- **`run.py`**: The main entry point. Configure your target URLs inside this file.
- **`src/graph.py`**: Defines the workflow logic and nodes.
- **`src/agents/`**: Contains specialized agents for each step (Editor, Scraper, Renderer, etc.).
- **`remotion_project/`**: The React-based video engine.

## 🛠️ Prerequisites

- **Python 3.10+**
- **Node.js 18+ & npm**
- **API Keys**: Required in a `.env` file (OpenAI, Google GenAI, etc.).
- **Playwright**: For web scraping.

## 📦 Installation

1.  **Clone the repository** (or navigate to the directory).
2.  **Setup Python Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install
    ```
3.  **Setup Rendering Engine**:
    ```bash
    cd remotion_project
    npm install
    ```
4.  **Configure Environment**:
    Create a `.env` file in the root directory and add your API keys:
    ```env
    OPENAI_API_KEY=your_key_here
    GOOGLE_API_KEY=your_key_here
    # ... other keys
    ```

## 🎮 Usage

1.  **Configure URLs**: Open `run.py` and paste your target news URLs into the `URLS_TEXT` block.
2.  **Start the System**:
    ```bash
    python run.py
    ```
3.  **Interact with the Workflow**: The terminal will pause at three points for your review. Follow the instructions to check files in `output/` and press **ENTER** to proceed.
4.  **Final Video**: Once finished, the concatenated video will be available as specified in the logs.

## 📁 Project Structure

```text
.
├── run.py                 # Main entry point
├── src/
│   ├── graph.py           # LangGraph workflow definition
│   ├── state.py           # State management (AgentState)
│   └── agents/            # Individual processing nodes
├── remotion_project/      # Remotion/React video rendering logic
├── output/                # All intermediate outputs and final videos
├── assets/                # Static assets (logos, BGM)
└── requirements.txt       # Python dependencies
```

## 📝 License

Internal Project / All Rights Reserved.
