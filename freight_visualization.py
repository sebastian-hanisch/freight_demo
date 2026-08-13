"""
2D-Kartendarstellung mit Plotly: Häfen als schwarze Sterne, Zielregionen als
farbige Punkte, Linien zeigen, welche Regionen über welchen Hafen verschifft
werden (nach Anteil des Regionsvolumens je Hafen gewichtet dargestellt).
"""

import plotly.graph_objects as go

from freight_constants import REGION_COLORS


def build_freight_map(port_coords, region_coords, assignments, item_regions, item_sizes):
    fig = go.Figure()

    n_regions = len(region_coords)
    n_ports = len(port_coords)

    # Anteil der Region-Groesse je Hafen (fuer Liniendicke/Transparenz)
    region_port_volume = [[0.0] * n_ports for _ in range(n_regions)]
    for c in assignments:
        for idx in c["items"]:
            region_port_volume[item_regions[idx]][c["port"]] += item_sizes[idx]

    for r in range(n_regions):
        total = sum(region_port_volume[r])
        if total <= 0:
            continue
        for k in range(n_ports):
            vol = region_port_volume[r][k]
            if vol <= 0:
                continue
            share = vol / total
            fig.add_trace(
                go.Scatter(
                    x=[region_coords[r][0], port_coords[k][0]],
                    y=[region_coords[r][1], port_coords[k][1]],
                    mode="lines",
                    line=dict(color=REGION_COLORS[r % len(REGION_COLORS)], width=1 + 4 * share),
                    opacity=0.3 + 0.5 * share,
                    hoverinfo="skip", showlegend=False,
                )
            )

    fig.add_trace(
        go.Scatter(
            x=region_coords[:, 0], y=region_coords[:, 1], mode="markers+text",
            marker=dict(size=12, color=[REGION_COLORS[r % len(REGION_COLORS)] for r in range(n_regions)], line=dict(width=1, color="white")),
            text=[f"R{r + 1}" for r in range(n_regions)], textposition="top center",
            name="Zielregionen", hoverinfo="text",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=port_coords[:, 0], y=port_coords[:, 1], mode="markers+text",
            marker=dict(size=18, symbol="star", color="black", line=dict(width=1, color="white")),
            text=[f"Hafen {k + 1}" for k in range(n_ports)], textposition="bottom center",
            name="Häfen", hoverinfo="text",
        )
    )

    fig.update_layout(
        xaxis=dict(range=[-5, 105], title="x", zeroline=False),
        yaxis=dict(range=[-5, 105], title="y", zeroline=False, scaleanchor="x"),
        height=520, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
