"""Shared graph definitions for live simulation and visualization."""
import networkx as nx


def topology_graph(kind, nodes):
    if nodes not in range(2, 11):
        raise ValueError("Choose between 2 and 10 nodes")
    if kind == "Star":
        return nx.star_graph(nodes - 1)
    if kind == "Grid":
        rows, columns = (2, nodes // 2) if nodes % 2 == 0 else (1, nodes)
        return nx.convert_node_labels_to_integers(nx.grid_2d_graph(rows, columns))
    if kind == "Caveman":
        if nodes % 2:
            raise ValueError("Caveman requires an even node count for two equal cliques")
        graph = nx.caveman_graph(2, nodes // 2)
        graph.add_edge(nodes // 2 - 1, nodes // 2)
        return graph
    raise ValueError(f"Unknown topology: {kind}")
