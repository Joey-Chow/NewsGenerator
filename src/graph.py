from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.editor import editor_node, scraper_node
from src.agents.renderer import video_renderer_node
from src.agents.reporter import reporter_node
from src.agents.asset_scraper import asset_scraper_node
from src.agents.ingest import human_asset_ingest_node
from langgraph.checkpoint.memory import MemorySaver

def human_review_node(state: AgentState):
    # This node serves as a breakpoint or review step
    print("Human Review: Checking final storyboard...")
    return {"is_approved": True}

def should_render(state: AgentState):
    if state.get("is_approved"):
        return "video_renderer"
    return "human_review" 

def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("asset_scraper", asset_scraper_node)
    workflow.add_node("human_asset_ingest", human_asset_ingest_node)
    workflow.add_node("reporter", reporter_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("video_renderer", video_renderer_node)

    # Add edges - Sequential Flow
    workflow.set_entry_point("scraper")
    workflow.add_edge("scraper", "editor")
    workflow.add_edge("editor", "asset_scraper")
    workflow.add_edge("asset_scraper", "human_asset_ingest")
    workflow.add_edge("human_asset_ingest", "reporter")
    workflow.add_edge("reporter", "human_review")
    
    workflow.add_conditional_edges(
        "human_review",
        should_render,
        {
            "video_renderer": "video_renderer",
            "human_review": "human_review" 
        }
    )
    
    workflow.add_edge("video_renderer", END)

    # Compile with interrupt and checkpointer
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["human_asset_ingest"])

if __name__ == "__main__":
    app = build_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
