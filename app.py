"""
Seefracht-Konsolidierung (LCL) – interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Vierte Demo im Portfolio. Entscheidung: welche Packstücke teilen sich einen
Container, und über welchen Hafen wird jeder Container verschifft, um See-
und Straßenfrachtkosten gemeinsam zu minimieren.

WICHTIG: Welche der beiden Methoden die "bessere" ist, wird bei jedem Lauf
NEU berechnet, nicht angenommen - je nach Verhältnis von Seefracht zu
Straßenkosten kann die hafen-bewusste Gruppierung (mehr, aber gezieltere
Container) oder die blinde Packung (weniger Container) günstiger sein. Siehe
README für den empirisch gefundenen Kipppunkt.

Lauffähig mit: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

from freight_data import generate_freight_scenario
from freight_evaluation import evaluate_assignment
from freight_feedback import log_feedback
from freight_heuristics import blind_packing_construction, flexible_beam_search_construction, port_aware_construction
from freight_pdf_export import generate_consolidation_plan_pdf
from freight_presets import apply_preset, bounds, init_session_state_defaults, load_permalink_settings, sync_query_params
from freight_ui_panel import render_freight_panel
from freight_visualization import build_freight_map

st.set_page_config(page_title="Seefracht-Konsolidierung – Sebastian Hanisch", layout="wide")

st.title("🚢 Seefracht-Konsolidierung (LCL)")
st.markdown(
    """
Interaktive Demo zur Konsolidierung von Sammelgut-Sendungen (LCL - Less than Container
Load): Welche Packstücke teilen sich einen Container, und über welchen Hafen wird jeder
Container verschifft, um See- und Straßenfrachtkosten **gemeinsam** zu minimieren? Zwei
selbst implementierte Ansätze - **blind gepackt** (nach Größe, ohne Rücksicht auf
Zielregion) und **hafen-bewusst gruppiert** (Packstücke mit ähnlicher Hafen-Präferenz
werden gezielt zusammen verladen) - nutzen denselben Packmechanismus und unterscheiden
sich nur in der Gruppierung davor.
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3 = st.columns(3)
with preset_col1:
    st.button(
        "📦 Standard-Konsolidierung", use_container_width=True,
        on_click=apply_preset, args=(40, 6, 3, 100.0, 800.0, 0.3, 5),
        help="Übliches Kostenverhältnis - hafen-bewusste Gruppierung sollte hier klar vorne liegen.",
    )
with preset_col2:
    st.button(
        "⚓ Teure Seefracht", use_container_width=True,
        on_click=apply_preset, args=(40, 6, 3, 100.0, 3000.0, 0.3, 6),
        help="Seefracht dominiert die Kosten - hier ist blindes Packen (weniger, volle Container) tatsächlich günstiger.",
    )
with preset_col3:
    st.button(
        "🗺️ Starke regionale Streuung", use_container_width=True,
        on_click=apply_preset, args=(50, 8, 4, 100.0, 800.0, 0.15, 9),
        help="Viele Regionen mit klar unterschiedlicher Hafen-Präferenz - der Vorteil hafen-bewusster Gruppierung sollte hier besonders deutlich sein.",
    )

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_items = st.slider("Anzahl Packstücke", *bounds("n_items_slider"), key="n_items_slider")
    n_regions = st.slider("Anzahl Zielregionen", *bounds("n_regions_slider"), key="n_regions_slider")
    n_ports = st.slider("Anzahl Häfen", *bounds("n_ports_slider"), key="n_ports_slider")
    capacity = st.slider("Container-Kapazität", *bounds("capacity_slider"), key="capacity_slider")

    st.markdown("**Kostenverhältnis (der entscheidende Hebel)**")
    sea_freight = st.slider(
        "Seefracht je Container (€)", *bounds("sea_freight_slider"), step=50.0, key="sea_freight_slider",
        help="Je höher relativ zu den Straßenkosten, desto eher lohnt sich weniger, dafür voller gepackte Container statt hafen-bewusster Gruppierung. Bei ca. 1.200-2.000 € kippt es in den Testszenarien.",
    )
    sea_spread = st.slider(
        "Preisunterschied zwischen Häfen", *bounds("sea_spread_slider"), step=0.05, key="sea_spread_slider",
        help="0 = alle Häfen gleich teuer, höhere Werte = größere Schwankung.",
    )
    beam_width = st.slider(
        "Beam-Breite", *bounds("beam_width_slider"), key="beam_width_slider",
        help="Anzahl parallel verfolgter Verbesserungsvarianten, während Beam Search gezielt nach lohnenden Hafen-Wechseln sucht (nicht nur Packreihenfolgen). Kann das Ergebnis nachweislich nie verschlechtern (siehe README). Bei diesem Suchtyp bringt mehr Breite kaum zusätzliche Qualität, aber deutlich mehr Rechenzeit - deshalb bewusst eng begrenzt.",
    )
    seed = st.number_input("Zufalls-Seed", step=1, key="seed_input")

    regenerate = st.button("🔄 Neues Szenario generieren", use_container_width=True)

sync_query_params(n_items, n_regions, n_ports, capacity, sea_freight, sea_spread, seed, beam_width)

if "force_regen" not in st.session_state:
    st.session_state.force_regen = False

gen_key = (n_items, n_regions, n_ports, capacity, sea_freight, sea_spread, int(seed))
needs_init = (
    "gen_key_cache" not in st.session_state or regenerate or st.session_state.force_regen
    or st.session_state.get("gen_key_cache") != gen_key
)
if needs_init:
    port_coords, region_coords, road_cost, sea_freight_arr, item_sizes, item_regions = generate_freight_scenario(
        n_items, n_regions, n_ports, int(seed), sea_freight_base=sea_freight, sea_freight_spread=sea_spread,
    )
    st.session_state.port_coords = port_coords
    st.session_state.region_coords = region_coords
    st.session_state.road_cost = road_cost
    st.session_state.sea_freight_arr = sea_freight_arr
    st.session_state.item_sizes = item_sizes
    st.session_state.item_regions = item_regions
    st.session_state.gen_key_cache = gen_key
    st.session_state.force_regen = False

port_coords = st.session_state.port_coords
region_coords = st.session_state.region_coords
road_cost = st.session_state.road_cost
sea_freight_arr = st.session_state.sea_freight_arr
item_sizes = st.session_state.item_sizes
item_regions = st.session_state.item_regions

with st.expander("📦 Packstücke (Zusammenfassung)"):
    summary_rows = []
    for r in range(n_regions):
        mask = item_regions == r
        summary_rows.append({
            "Region": f"R{r + 1}", "Anzahl Packstücke": int(mask.sum()),
            "Gesamtgröße": round(float(item_sizes[mask].sum()), 1),
            "Günstigster Hafen": f"Hafen {int(np.argmin(road_cost[r])) + 1}",
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

blind_assignments = blind_packing_construction(item_sizes, item_regions, capacity, road_cost, sea_freight_arr)
aware_assignments = port_aware_construction(item_sizes, item_regions, capacity, road_cost, sea_freight_arr)
beam_assignments = flexible_beam_search_construction(item_sizes, item_regions, capacity, road_cost, sea_freight_arr, beam_width=beam_width)

stats_blind = evaluate_assignment(blind_assignments, item_sizes, item_regions, road_cost, sea_freight_arr)
stats_aware = evaluate_assignment(aware_assignments, item_sizes, item_regions, road_cost, sea_freight_arr)
stats_beam = evaluate_assignment(beam_assignments, item_sizes, item_regions, road_cost, sea_freight_arr)

# Welche Methode tatsaechlich guenstiger ist, wird bei JEDEM Lauf neu anhand
# der Gesamtkosten bestimmt - NICHT angenommen. Je nach Kostenverhaeltnis
# (siehe Sidebar-Regler "Seefracht je Container") kann entweder Methode
# gewinnen (empirisch verifizierter Kipppunkt, siehe README).
candidates = [
    {"key": "blind", "label": "Blind gepackt", "assignments": blind_assignments, **stats_blind},
    {"key": "aware", "label": "Hafen-bewusst gruppiert", "assignments": aware_assignments, **stats_aware},
    {"key": "beam", "label": "Beam Search", "assignments": beam_assignments, **stats_beam},
]
best = min(candidates, key=lambda c: c["total_cost"])
baseline = max(candidates, key=lambda c: c["total_cost"])

st.markdown("## 🎯 Ihre kostenoptimierte Konsolidierung")

cost_saved = baseline["total_cost"] - best["total_cost"]
pct_saved = (cost_saved / baseline["total_cost"] * 100) if baseline["total_cost"] > 0 else 0.0

m1, m2, m3 = st.columns(3)
m1.metric("Gesamtkosten", f"{best['total_cost']:.0f} €", delta=f"-{cost_saved:.0f} € ggü. Alternative")
m2.metric("davon Seefracht", f"{best['sea_cost_total']:.0f} €")
m3.metric("Container genutzt", f"{best['n_containers']}")

if cost_saved > 1:
    st.success(
        f"💶 **{best['label']}** spart hier ca. **{cost_saved:.0f} €** ({pct_saved:.1f}%) gegenüber "
        f"'{baseline['label']}' - bei dieser einzelnen Sendung. Hochgerechnet auf regelmäßige "
        f"Konsolidierungen summiert sich das schnell."
    )

fig_best = build_freight_map(port_coords, region_coords, best["assignments"], item_regions, item_sizes)
st.plotly_chart(fig_best, use_container_width=True, key="primary_best_plot")

pdf_bytes_best = generate_consolidation_plan_pdf("Kostenoptimiert", best["assignments"], item_sizes, item_regions, road_cost, sea_freight_arr)
st.download_button(
    "📄 Konsolidierungsplan als PDF herunterladen", data=pdf_bytes_best,
    file_name="konsolidierungsplan_optimiert.pdf", mime="application/pdf", key="primary_pdf_download",
)

st.caption("Ermittelt mit der bei diesem Kostenverhältnis günstigeren von zwei eigenen Methoden. Details unten.")

st.markdown("---")

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", expanded=False):
    tabs = st.tabs(["📦 Blind gepackt", "🎯 Hafen-bewusst gruppiert", "📡 Beam Search", "📊 Vergleich"])

    with tabs[0]:
        st.caption("Packstücke werden nach Größe in Container gepackt (First-Fit-Decreasing), ohne Rücksicht auf Zielregion. Der Hafen wird erst danach je Container günstigst gewählt.")
        summary_blind = render_freight_panel("blind", "Blind gepackt", blind_assignments, port_coords, region_coords, item_sizes, item_regions, road_cost, sea_freight_arr)

    with tabs[1]:
        st.caption("Packstücke werden zuerst nach ihrem günstigsten Hafen gruppiert, erst danach je Gruppe gepackt - derselbe Packmechanismus wie links, nur mit vorheriger Gruppierung.")
        summary_aware = render_freight_panel("aware", "Hafen-bewusst gruppiert", aware_assignments, port_coords, region_coords, item_sizes, item_regions, road_cost, sea_freight_arr)

    with tabs[2]:
        st.caption(
            "Startet bei der Hafen-bewusst gruppierten Lösung (garantiert nie schlechter) und sucht "
            "gezielt nach Packstücken, die für eine kleine Straßenkosten-Erhöhung den Hafen wechseln "
            "könnten, um mit anderen Packstücken zusammen Container einzusparen - die starre Gruppierung "
            "links ist nicht immer optimal (siehe README für ein konkretes Beispiel)."
        )
        summary_beam = render_freight_panel("beam", "Beam Search", beam_assignments, port_coords, region_coords, item_sizes, item_regions, road_cost, sea_freight_arr)

    with tabs[3]:
        st.markdown("### Methodenvergleich")
        comp_rows = []
        for c in [summary_blind, summary_aware, summary_beam]:
            comp_rows.append({
                "Methode": c["label"],
                "Gesamtkosten": f"{c['total_cost']:.0f} €",
                "Seefracht": f"{c['sea_cost_total']:.0f} €",
                "Straßenfracht": f"{c['road_cost_total']:.0f} €",
                "Container": c["n_containers"],
            })
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Alle drei Methoden nutzen denselben Packmechanismus (First-Fit-Decreasing) und dieselbe "
            "Hafenwahl-Logik je Container - der Unterschied liegt in der Gruppierung vor dem Packen "
            "(Blind: keine, Hafen-bewusst/Beam Search: nach günstigstem Hafen) und darin, ob mehrere "
            "Packvarianten durchprobiert werden (nur Beam Search)."
        )

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Zwei Entscheidungsebenen gekoppelt:** Anders als bei den ersten drei Demos (jeweils eine
Entscheidungsebene: Reihenfolge, Positionierung, Liniennetz) müssen hier zwei Ebenen
gemeinsam optimiert werden - welche Packstücke teilen sich einen Container (Packproblem),
und über welchen Hafen wird jeder Container verschifft (Zuordnungsproblem). Beide
Entscheidungen hängen voneinander ab: die beste Hafenwahl für einen Container ergibt sich
erst aus seinem Inhalt.

**Blind gepackt:** Packstücke werden nach Größe absteigend sortiert und per
First-Fit-Decreasing in Container gepackt (das erste, dessen Restkapazität reicht) - ohne
jede Rücksicht auf die Zielregion. Erst danach wird je Container der günstigste Hafen
gewählt.

**Hafen-bewusst gruppiert:** Für jede Zielregion wird zunächst der günstigste Hafen anhand
der Straßenkosten bestimmt. Packstücke mit demselben günstigsten Hafen werden gemeinsam
gepackt (mit demselben First-Fit-Decreasing-Verfahren wie oben) - dadurch landen
Packstücke mit ähnlicher Hafen-Präferenz im selben Container, was die anschließende
Hafenwahl weniger kompromissbehaftet macht.

**Beam Search:** Die Gruppierung "Hafen-bewusst" trifft ihre Hafenwahl pro Packstück
starr anhand des individuell günstigsten Hafens - das ist nicht immer optimal. Ein
Packstück, das für eine kleine Straßenkosten-Erhöhung den Hafen wechselt, kann manchmal
mit einem andersartig bevorzugten Packstück zusammen einen ganzen Container einsparen.
Beam Search startet deshalb bei der Hafen-bewusst gruppierten Lösung (garantiert nie
schlechter) und sucht über mehrere Runden gezielt nach genau solchen lohnenden
Verschiebungen - direkte Bewertung des tatsächlichen Kosteneffekts statt blinder
Neukonstruktion. Bewusst so aufgebaut, dass eine höhere Beam-Breite das Ergebnis
**nachweislich nie verschlechtern** kann.

**Der Kipppunkt:** Hafen-bewusste Gruppierung (und Beam Search, das darauf aufbaut) führt
tendenziell zu mehr, dafür weniger voll ausgelasteten Containern (die Gruppierung zerteilt
den Packstück-Pool) als blindes Packen. Ob sich das lohnt, hängt vom Verhältnis zwischen
Seefracht (bestraft mehr Container) und Straßenkosten (belohnt zielgerichtete Gruppierung)
ab. Bei niedriger bis mittlerer Seefracht gewinnt die hafen-bewusste Gruppierung praktisch
immer; bei sehr hoher Seefracht kann blindes Packen trotz schlechterer Hafenwahl günstiger
sein, weil es mit weniger Containern auskommt. Probieren Sie den Regler "Seefracht je
Container" aus, um das selbst zu sehen - alle drei Methoden werden bei jeder Einstellung
neu gerechnet, welche gewinnt wird nicht angenommen.

**In echten Projekten** kämen meist weitere Nebenbedingungen dazu (Gewichtsgrenzen,
gefährliche Güter, feste Abfahrtstermine je Hafen, mehrstufige Transportketten) - das
Grundprinzip aus gekoppelter Gruppierung und Bewertung bleibt aber dasselbe.
"""
    )

st.markdown("---")

st.markdown("#### War diese Demo hilfreich für Sie?")
if st.session_state.get("feedback_given"):
    vote_text = "👍 positiv" if st.session_state["feedback_given"] == "up" else "👎 negativ"
    st.success(f"Danke für Ihr Feedback ({vote_text})! 🙏")
else:
    fb_col1, fb_col2 = st.columns(2)
    with fb_col1:
        if st.button("👍 Ja", key="feedback_up_btn", use_container_width=True):
            log_feedback("up")
            st.session_state["feedback_given"] = "up"
            st.rerun()
    with fb_col2:
        if st.button("👎 Nein", key="feedback_down_btn", use_container_width=True):
            log_feedback("down")
            st.session_state["feedback_given"] = "down"
            st.rerun()

st.caption(
    "Diese Demo ist Teil des Portfolios von Sebastian Hanisch – Operations Research "
    "und Machine Learning. Interesse an einer maßgeschneiderten Lösung für Ihr "
    "Unternehmen? [Kontakt aufnehmen](#)"
)
