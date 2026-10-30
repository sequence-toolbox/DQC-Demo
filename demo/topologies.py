"""Shared graph definitions for live simulation and visualization."""
import networkx as nx


def topology_graph(kind, nodes):
    if nodes not in (2, 4, 6, 8, 10):
        raise ValueError("Choose 2, 4, 6, 8, or 10 nodes")
    if kind == "Star":
        return nx.star_graph(nodes - 1)
    if kind == "Grid":
        return nx.convert_node_labels_to_integers(nx.grid_2d_graph(2, nodes // 2))
    if kind == "Caveman":
        graph = nx.caveman_graph(2, nodes // 2)
        graph.add_edge(nodes // 2 - 1, nodes // 2)
        return graph
    raise ValueError(f"Unknown topology: {kind}")
