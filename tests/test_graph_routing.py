"""Tests that the graph routes correctly based on critic feedback state."""
from src.graph import build_graph


def test_graph_compiles():
    """Graph should compile without error."""
    graph = build_graph()
    assert graph is not None


def test_graph_has_critic_nodes():
    """Graph should contain both critic nodes."""
    graph = build_graph()
    node_names = {node for node in graph.get_graph().nodes}
    assert "script_critic" in node_names
    assert "image_critic" in node_names


def test_script_critic_routing_edges():
    """script_critic should have conditional edges to both editor and script_review."""
    graph = build_graph()
    graph_repr = graph.get_graph()
    edges_from_critic = [e for e in graph_repr.edges if e.source == "script_critic"]
    targets = {e.target for e in edges_from_critic}
    assert "editor" in targets
    assert "script_review" in targets


def test_image_critic_routing_edges():
    """image_critic should have conditional edges to photographer and join_assets."""
    graph = build_graph()
    graph_repr = graph.get_graph()
    edges_from_critic = [e for e in graph_repr.edges if e.source == "image_critic"]
    targets = {e.target for e in edges_from_critic}
    assert "photographer" in targets
    assert "join_assets" in targets
