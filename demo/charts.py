"""Plotly views with no external assets or network calls."""
import math

import networkx as nx
import plotly.graph_objects as go
from demo.topologies import topology_graph

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


def network(kind="Two nodes", modules=2, edges=None, capacity=1, capacities=None):
    capacities = list(capacities) if capacities is not None else [capacity] * modules
    if len(capacities) != modules or any(not isinstance(value, int) or value < 1 for value in capacities):
        raise ValueError("Provide one positive integer data capacity per node")
    if edges is not None:
        graph = nx.Graph()
        graph.add_nodes_from(range(modules))
        graph.add_edges_from(edges)
    elif kind in ("Star", "Grid", "Caveman"):
        graph = topology_graph(kind, modules)
    elif kind == "Line":
        graph = nx.path_graph(modules)
    else:
        graph = nx.path_graph(2) if modules == 2 else nx.cycle_graph(modules)
    positions = nx.spring_layout(graph, seed=7)
    if modules == 2:
        positions = {0: (-1, 0), 1: (1, 0)}
    elif kind == "Line":
        positions = {i: (-1.2 + 2.4 * i / (modules - 1), 0.0) for i in graph.nodes()}
    elif kind == "Star":
        positions = {0: (0.0, 0.0)}
        positions.update({i: (math.cos(math.pi / 2 + 2 * math.pi * (i - 1) / (modules - 1)),
                              math.sin(math.pi / 2 + 2 * math.pi * (i - 1) / (modules - 1))) for i in range(1, modules)})
    elif kind == "Grid":
        columns = modules // 2 if modules % 2 == 0 else modules
        positions = {i: (-1 + 2 * (i % columns) / max(1, columns - 1),
                         0.4 - 0.8 * (i // columns) if modules % 2 == 0 else 0.0) for i in graph.nodes()}
    elif kind == "Caveman":
        size = modules // 2
        angles = {i: 2 * math.pi * (i - size + 1) / size if i < size else math.pi + 2 * math.pi * (i - size) / size for i in graph.nodes()}
        positions = {i: ((-0.8 if i < size else 0.8) + 0.45 * math.cos(angles[i]),
                         0.6 * math.sin(angles[i])) for i in graph.nodes()}
    fig = go.Figure()
    for a, b in graph.edges():
        fig.add_trace(go.Scatter(x=[positions[a][0], positions[b][0]], y=[positions[a][1], positions[b][1]],
                                 mode="lines", line={"color": "#48748d", "width": 3}, hoverinfo="skip", showlegend=False))
    labels = ["Alice", "Bob"] if modules == 2 else [f"QPU {i + 1}" for i in graph.nodes()]
    if kind == "Star":
        labels[0] += " · hub"
    node_size = 68 if modules == 2 else 58 if modules <= 6 else 44
    node_sizes = [max(node_size, 24 + 18 * math.ceil(math.sqrt(value))) if value > 3 else node_size for value in capacities]
    fig.add_trace(go.Scatter(x=[positions[i][0] for i in graph.nodes()], y=[positions[i][1] for i in graph.nodes()],
                             mode="markers", text=labels, showlegend=False, opacity=1.0,
                             customdata=capacities,
                             hovertemplate="%{text}<br>Data capacity: %{customdata}<extra></extra>",
                             marker={"size": node_sizes, "opacity": 1.0,
                                     "color": ["#e5edff" if kind == "Star" and i == 0 else "#e5f7f3" for i in graph.nodes()],
                                     "line": {"color": [COLORS[1] if kind == "Star" and i == 0 else COLORS[0] for i in graph.nodes()], "width": 2}}))
    for node in graph.nodes():
        dx, dy = 0.0, -1.0
        if kind == "Star" and modules > 2:
            if node == 0:
                angle = -math.pi / 2 if modules % 2 == 0 else math.pi / 2 + math.pi / (modules - 1)
                dx, dy = math.cos(angle), math.sin(angle)
            else:
                dx, dy = positions[node]
        elif kind == "Grid" and modules > 2 and modules % 2 == 0:
            dy = 1.0 if node < modules // 2 else -1.0
        fig.add_annotation(x=positions[node][0], y=positions[node][1],
                           xshift=(node_sizes[node] / 2 + 8) * dx, yshift=(node_sizes[node] / 2 + 8) * dy,
                           xanchor="left" if dx > .25 else "right" if dx < -.25 else "center",
                           yanchor="bottom" if dy > .25 else "top" if dy < -.25 else "middle",
                           text=labels[node], font={"color": "#172b42", "size": 12}, showarrow=False,
                           bgcolor="white", borderpad=2, name="node_label")
        count = capacities[node]
        radius = 0 if count == 1 else 12
        for slot in range(count):
            angle = math.pi / 2 + 2 * math.pi * slot / count
            xshift, yshift = radius * math.cos(angle), radius * math.sin(angle)
            if count > 3:
                columns = math.ceil(math.sqrt(count))
                rows = math.ceil(count / columns)
                xshift, yshift = 18 * (slot % columns - (columns - 1) / 2), 18 * ((rows - 1) / 2 - slot // columns)
            fig.add_annotation(x=positions[node][0], y=positions[node][1],
                               xshift=xshift, yshift=yshift,
                               text="●", font={"color": "#dc2626", "size": 22}, showarrow=False,
                               hovertext=f"{labels[node]} · data qubit slot {slot + 1}/{count}",
                               name="data_qubit")
    if modules == 2:
        fig.add_annotation(x=0, y=0.12, text="Photonic link · heralded entanglement", showarrow=False)
    fig.update_xaxes(visible=False, range=[-1.5, 1.5])
    fig.update_yaxes(visible=False, range=[-1.4, 1.4])
    if kind == "Star" and modules > 2:
        fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return style(fig, 380 if kind == "Star" and modules > 2 else 290)


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


def success_chart(series, height=390):
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
    return style(fig, height)


def comparison(rows, metric, title, key="label"):
    fig = go.Figure(go.Bar(x=[r[key].replace("\n", " ") for r in rows], y=[r[metric] for r in rows],
                           marker_color=[COLORS[i % len(COLORS)] for i in range(len(rows))]))
    fig.update_layout(yaxis_title=title)
    return style(fig, 350)
