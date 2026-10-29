"""Plotly views with no external assets or network calls."""
import math

import networkx as nx
import plotly.graph_objects as go

COLORS = ["#0d9488", "#4878d0", "#c58a21", "#995ac6"]


def style(fig, height=340):
    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"family": "Arial", "color": "#172b42"}, margin={"l": 30, "r": 20, "t": 45, "b": 35},
                      height=height, legend={"orientation": "h", "y": 1.16})
    return fig


def interval(hits, shots):
    """95% Wilson interval, including meaningful bounds at zero and perfect success."""
    z, p = 1.96, hits / shots
    scale = 1 + z * z / shots
    center = (p + z * z / (2 * shots)) / scale
    half = z * math.sqrt(p * (1 - p) / shots + z * z / (4 * shots * shots)) / scale
    return max(0, center - half), min(1, center + half)


def network(kind="Two modules", modules=2, edges=None, capacity=1):
    if edges is not None:
        graph = nx.Graph()
        graph.add_nodes_from(range(modules))
        graph.add_edges_from(edges)
    elif kind == "Star":
        graph = nx.star_graph(modules - 1)
    elif kind == "Grid":
        graph = nx.convert_node_labels_to_integers(nx.grid_2d_graph(2, modules // 2))
    elif kind == "Caveman":
        if modules <= 4:
            graph = nx.caveman_graph(2, modules // 2)
            graph.add_edge(modules // 2 - 1, modules // 2)
        else:
            graph = nx.connected_caveman_graph(2, modules // 2)
    else:
        graph = nx.path_graph(2) if modules == 2 else nx.cycle_graph(modules)
    positions = nx.spring_layout(graph, seed=7)
    if modules == 2:
        positions = {0: (-1, 0), 1: (1, 0)}
    fig = go.Figure()
    for a, b in graph.edges():
        fig.add_trace(go.Scatter(x=[positions[a][0], positions[b][0]], y=[positions[a][1], positions[b][1]],
                                 mode="lines", line={"color": "#48748d", "width": 3}, hoverinfo="skip", showlegend=False))
    labels = ["Alice", "Bob"] if modules == 2 else [f"QPU {i + 1}" for i in graph.nodes()]
    fig.add_trace(go.Scatter(x=[positions[i][0] for i in graph.nodes()], y=[positions[i][1] for i in graph.nodes()],
                             mode="markers+text", text=labels, textposition="bottom center", showlegend=False,
                             customdata=[capacity] * modules,
                             hovertemplate="%{text}<br>Data capacity: %{customdata}<extra></extra>",
                             marker={"size": 44 if modules == 2 else 28, "color": COLORS[0], "line": {"color": "#a7fff2", "width": 2}}))
    if modules == 2:
        fig.add_annotation(x=0, y=0.12, text="Photonic link · heralded entanglement", showarrow=False)
    fig.update_xaxes(visible=False, range=[-1.5, 1.5])
    fig.update_yaxes(visible=False, range=[-1.4, 1.4])
    return style(fig, 290)


def circuit():
    fig = go.Figure()
    for y, name in ((1, "Alice · q₀"), (0, "Bob · q₁")):
        fig.add_trace(go.Scatter(x=[0, 7], y=[y, y], mode="lines", line={"color": "#48748d", "width": 2}, showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=-0.1, y=y, text=name, xanchor="right", showarrow=False)
        for x, gate in ((0.6, "H"), (3.2, "H · X"), (5.7, "X · H"), (6.8, "M")):
            fig.add_annotation(x=x, y=y, text=gate, showarrow=False, bgcolor="#e8eef6", borderpad=6)
    for x, label in ((1.9, "Oracle"), (4.5, "Diffusion")):
        fig.add_trace(go.Scatter(x=[x, x], y=[0, 1], mode="lines+markers", marker={"size": 12, "color": COLORS[0]}, line={"color": COLORS[0], "width": 3}, showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=x, y=1.65, text=f"{label}<br>teleported CZ", showarrow=False, font={"color": COLORS[0]} )
    fig.update_xaxes(visible=False, range=[-1.4, 7.3])
    fig.update_yaxes(visible=False, range=[-0.4, 2])
    return style(fig, 230)


def success_chart(series):
    fig = go.Figure()
    for i, (label, rows) in enumerate(series.items()):
        values = [r["success"] * 100 for r in rows]
        errors = {}
        if all("hits" in r for r in rows):
            bounds = [interval(r["hits"], r["shots"]) for r in rows]
            errors = {"type": "data", "symmetric": False,
                      "array": [high * 100 - value for (_, high), value in zip(bounds, values)],
                      "arrayminus": [value - low * 100 for (low, _), value in zip(bounds, values)]}
        fig.add_trace(go.Bar(name=label, x=[f"|{r['state']}〉" for r in rows], y=values,
                             marker_color=COLORS[i % len(COLORS)], error_y=errors,
                             hovertemplate="%{x}<br>%{y:.1f}% success<extra>%{fullData.name}</extra>"))
    fig.add_hrect(y0=70, y1=72, fillcolor="#c58a21", opacity=0.12, line_width=0)
    fig.add_hline(y=71, line_dash="dash", line_color="#a66b0c", annotation_text="Nature · 71% average")
    fig.update_layout(barmode="group", yaxis_title="Success probability (%)", yaxis_range=[0, 110], xaxis_title="Marked state")
    return style(fig, 390)


def comparison(rows, metric, title, key="label"):
    fig = go.Figure(go.Bar(x=[r[key].replace("\n", " ") for r in rows], y=[r[metric] for r in rows],
                           marker_color=[COLORS[i % len(COLORS)] for i in range(len(rows))]))
    fig.update_layout(yaxis_title=title)
    return style(fig, 350)
