"""
Wiederverwendbares Streamlit-UI-Panel für eine einzelne Konsolidierungs-
Heuristik: Metriken, Karte, PDF-Export.
"""

import streamlit as st

from freight_evaluation import evaluate_assignment
from freight_pdf_export import generate_consolidation_plan_pdf
from freight_visualization import build_freight_map


def render_freight_panel(prefix, label, assignments, port_coords, region_coords, item_sizes, item_regions, road_cost, sea_freight):
    stats = evaluate_assignment(assignments, item_sizes, item_regions, road_cost, sea_freight)

    m1, m2, m3 = st.columns(3)
    m1.metric("Gesamtkosten", f"{stats['total_cost']:.0f} €")
    m2.metric("davon Seefracht", f"{stats['sea_cost_total']:.0f} €")
    m3.metric("Container genutzt", f"{stats['n_containers']}")

    fig = build_freight_map(port_coords, region_coords, assignments, item_regions, item_sizes)
    st.plotly_chart(fig, use_container_width=True, key=f"{prefix}_plot")

    pdf_bytes = generate_consolidation_plan_pdf(label, assignments, item_sizes, item_regions, road_cost, sea_freight)
    st.download_button(
        "📄 Konsolidierungsplan als PDF herunterladen", data=pdf_bytes,
        file_name=f"konsolidierung_{prefix}.pdf", mime="application/pdf", key=f"{prefix}_pdf_download",
    )

    return {"label": label, "assignments": assignments, **stats}
