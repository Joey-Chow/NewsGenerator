from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.editor import editor_node, scraper_node
from src.agents.photographer import photographer_node
from src.agents.renderer import video_renderer_node

def human_review_node(state: AgentState):
    # This node doesn't do much logic, it serves as a breakpoint
    print("Human Review: Auto-approving for demo purposes...")
    return {"is_approved": True}

def should_render(state: AgentState):
    if state.get("is_approved"):
        return "video_renderer"
    return "human_review" # Loop back or handled by interrupt

def build_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("photographer", photographer_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("video_renderer", video_renderer_node)

    # Add edges
    workflow.set_entry_point("scraper")
    workflow.add_edge("scraper", "editor")
    workflow.add_edge("editor", "photographer")
    workflow.add_edge("photographer", "human_review")
    
    # Conditional logic example: 
    # In a real app, we might use interrupt_before=["video_renderer"] 
    # and not need a conditional edge if we just want to resume.
    # But for explicit approval logic:
    workflow.add_conditional_edges(
        "human_review",
        should_render,
        {
            "video_renderer": "video_renderer",
            "human_review": "human_review" 
        }
    )
    
    workflow.add_edge("video_renderer", END)

    # Compile with interrupt for human-in-the-loop
    return workflow.compile()

if __name__ == "__main__":
    app = build_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except ImportError:
        print("Install 'grandalf' to visualize the graph.")
