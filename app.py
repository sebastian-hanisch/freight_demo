"""
Seefracht-Konsolidierung (LCL) – interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Vierte Demo im Portfolio. Entscheidung: welche Packstücke teilen sich einen
Container, und über welchen Hafen wird jeder Container verschifft, um See-
und Straßenfrachtkosten gemeinsam zu minimieren.

WICHTIG: Welche der drei Methoden die "bessere" ist, wird bei jedem Lauf NEU
berechnet, nicht angenommen - je nach Verhältnis von Seefracht zu
Straßenkosten kann die hafen-bewusste Gruppierung (mehr, aber gezieltere
Container) oder die blinde Packung (weniger Container) günstiger sein, und
Beam Search kann durch gezielte Hafen-Wechsel zusätzlich Wert freilegen.
Siehe README für den empirisch gefundenen Kipppunkt sowie ein
handgerechnetes Beispiel, wann Beam Search hilft.

Lauffähig mit: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

from freight_data import generate_freight_scenario
from freight_evaluation import evaluate_assignment
from freight_feedback import log_feedback
from freight_heuristics import balance_containers, blind_packing_construction, flexible_beam_search_construction, port_aware_construction, port_consolidation_frontier
from freight_pdf_export import generate_consolidation_plan_pdf
from freight_presets import apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, sync_query_params
from freight_ui_panel import render_freight_panel
from freight_visualization import build_freight_map

st.set_page_config(page_title="Seefracht-Konsolidierung – Sebastian Hanisch", layout="wide")

st.title("🚢 Seefracht-Konsolidierung (LCL)")
st.markdown(
    """
Interaktive Demo zur Konsolidierung von Sammelgut-Sendungen (LCL - Less than Container
Load): Welche Packstücke teilen sich einen Container, und über welchen Hafen wird jeder
Container verschifft, um See- und Straßenfrachtkosten **gemeinsam** zu minimieren? Drei
selbst implementierte Ansätze - **blind gepackt** (nach Größe, ohne Rücksicht auf
Zielregion), **hafen-bewusst gruppiert** (Packstücke mit ähnlicher Hafen-Präferenz
werden gezielt zusammen verladen) und **Beam Search** (sucht zusätzlich gezielt nach
lohnenden Hafen-Wechseln, wenn die starre Gruppierung selbst nicht optimal ist) -
werden direkt verglichen.
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3 = st.columns(3)
with preset_col1:
    st.button(
        "🎯 Beam Search lohnt sich", use_container_width=True,
        on_click=apply_preset, args=(30, 8, 4, 100.0, 800.0, 0.1, 17),
        help="Viele Regionen bei wenigen Häfen und knappen Kostenunterschieden - Beam Search findet hier gezielte Hafen-Wechsel, die 14% gegenüber reiner Gruppierung sparen.",
    )
with preset_col2:
    st.button(
        "⚓ Teure Seefracht", use_container_width=True,
        on_click=apply_preset, args=(30, 5, 3, 100.0, 4000.0, 0.3, 4),
        help="Seefracht dominiert die Kosten - hier ist blindes Packen (weniger, volle Container) tatsächlich günstiger.",
    )
with preset_col3:
    st.button(
        "🗺️ Starke regionale Streuung", use_container_width=True,
        on_click=apply_preset, args=(80, 8, 5, 100.0, 800.0, 0.3, 1),
        help="Viele Regionen und Häfen bei vielen Packstücken - der Vorteil hafen-bewusster Gruppierung fällt hier deutlich stärker aus als im Normalfall (+26% statt der üblichen ~10%).",
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
    seed_lo, seed_hi = bounds("seed_input")
    seed = st.number_input("Zufalls-Seed", min_value=seed_lo, max_value=seed_hi, step=1, key="seed_input")

    st.button(
        "🎲 Neues Szenario generieren", use_container_width=True, on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed und erzeugt damit ein komplett neues Szenario - "
        "praktisch, ohne selbst eine neue Seed-Zahl eintippen zu müssen.",
    )

sync_query_params(n_items, n_regions, n_ports, capacity, sea_freight, sea_spread, seed)

if "force_regen" not in st.session_state:
    st.session_state.force_regen = False

gen_key = (n_items, n_regions, n_ports, capacity, sea_freight, sea_spread, int(seed))
needs_init = (
    "gen_key_cache" not in st.session_state or st.session_state.force_regen
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
beam_assignments = flexible_beam_search_construction(item_sizes, item_regions, capacity, road_cost, sea_freight_arr)

# Alternative Loesungen (auf Nutzerwunsch ergaenzt, siehe README): zwei
# geschaeftlich motivierte Alternativen zur reinen Kostenoptimierung,
# beide ausgehend von der bereits kostenoptimalen Loesung.
beam_containers_for_alt = [a["items"] for a in beam_assignments]
port_frontier = port_consolidation_frontier(beam_containers_for_alt, item_regions, item_sizes, road_cost, sea_freight_arr)
balanced_assignments = balance_containers(beam_containers_for_alt, item_sizes, item_regions, capacity, road_cost, sea_freight_arr)

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
m1.metric("Gesamtkosten", f"{best['total_cost']:.0f} €", delta=f"-{cost_saved:.0f} € ggü. Alternative", delta_color="inverse")
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

st.caption("Ermittelt mit der bei diesem Kostenverhältnis günstigsten von drei eigenen Methoden. Details unten.")

st.markdown("---")

st.markdown("## 🔀 Alternative Lösungen")
st.caption(
    "Die kostenoptimale Lösung ist nicht immer die praktikabelste - manchmal lohnt sich ein kleiner "
    "Kostenaufschlag für einfachere Abwicklung. Beide Alternativen gehen von der oben gezeigten "
    "kostenoptimalen Lösung aus."
)

alt_col1, alt_col2 = st.columns(2)

with alt_col1:
    st.markdown("#### 📉 Was kostet Konsolidierung auf wenige Häfen?")
    st.caption(
        "Weniger Häfen bedeutet oft weniger Spediteure/Ansprechpartner und mehr Verhandlungsmacht "
        "bei einem Anbieter - hier die Kosten, wenn nur die k günstigsten Häfen zusammen genutzt "
        "werden dürfen (bei sonst unveränderter Packung)."
    )
    frontier_rows = []
    unrestricted_cost = port_frontier[len(sea_freight_arr)][0]
    for k in sorted(port_frontier):
        cost, subset = port_frontier[k]
        extra_pct = (cost - unrestricted_cost) / unrestricted_cost * 100 if unrestricted_cost > 0 else 0.0
        frontier_rows.append({
            "Häfen erlaubt": k,
            "Kosten": f"{cost:.0f} €",
            "Aufschlag ggü. frei": f"+{extra_pct:.1f}%" if extra_pct > 0.05 else "optimal",
        })
    st.dataframe(pd.DataFrame(frontier_rows), use_container_width=True, hide_index=True)

with alt_col2:
    st.markdown("#### ⚖️ Ausgeglichenere Container")
    stats_balanced = evaluate_assignment(balanced_assignments, item_sizes, item_regions, road_cost, sea_freight_arr)
    fill_beam = [sum(item_sizes[i] for i in a["items"]) / capacity * 100 for a in beam_assignments if a["items"]]
    fill_balanced = [sum(item_sizes[i] for i in a["items"]) / capacity * 100 for a in balanced_assignments if a["items"]]
    extra_cost_balanced = stats_balanced["total_cost"] - stats_beam["total_cost"]
    extra_pct_balanced = (extra_cost_balanced / stats_beam["total_cost"] * 100) if stats_beam["total_cost"] > 0 else 0.0
    if fill_beam and fill_balanced:
        # Regler-Minimum ist aktuell 10 Packstuecke, dieser Fall ist ueber
        # die UI nicht erreichbar - Schutz trotzdem ergaenzt, falls sich
        # das Minimum je aendert oder die Funktionen direkt (nicht ueber
        # die App) mit 0 Packstuecken aufgerufen werden.
        st.caption(
            f"Gleichmäßigere Auslastung kann Handling planbarer machen und einzelne, fast randvolle "
            f"Container als Risiko vermeiden. Füllgrad-Spanne: {min(fill_beam):.0f}-{max(fill_beam):.0f}% → "
            f"{min(fill_balanced):.0f}-{max(fill_balanced):.0f}%, bei "
            f"{'+' if extra_cost_balanced >= 0 else ''}{extra_pct_balanced:.1f}% Kosten."
        )
    bc1, bc2 = st.columns(2)
    bc1.metric("Kostenoptimal", f"{stats_beam['total_cost']:.0f} €")
    bc2.metric("Ausgeglichen", f"{stats_balanced['total_cost']:.0f} €", delta=f"+{extra_cost_balanced:.0f} €", delta_color="inverse")

with st.expander("📍 Karte der ausgeglichenen Lösung", expanded=False):
    fig_balanced = build_freight_map(port_coords, region_coords, balanced_assignments, item_regions, item_sizes)
    st.plotly_chart(fig_balanced, use_container_width=True, key="balanced_plot")
    pdf_bytes_balanced = generate_consolidation_plan_pdf("Ausgeglichene Container", balanced_assignments, item_sizes, item_regions, road_cost, sea_freight_arr)
    st.download_button(
        "📄 Konsolidierungsplan (ausgeglichen) als PDF herunterladen", data=pdf_bytes_balanced,
        file_name="konsolidierungsplan_ausgeglichen.pdf", mime="application/pdf", key="balanced_pdf_download",
    )

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
            "Startet bei zwei Ausgangslösungen (Blind gepackt UND einer alternierend neu gruppierten "
            "Variante), sucht von beiden aus gezielt nach Packstücken, die für eine kleine "
            "Straßenkosten-Erhöhung den Hafen wechseln oder mit einem anderen Packstück tauschen könnten, "
            "und poliert das beste Ergebnis abschließend mit Large Neighborhood Search (mehrere Container "
            "gleichzeitig neu aufgebaut) - das günstigste Endergebnis gewinnt (siehe README für Details)."
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
            "Blind und Hafen-bewusst nutzen denselben Packmechanismus (First-Fit-Decreasing) und "
            "dieselbe Hafenwahl-Logik je Container - der Unterschied liegt allein in der Gruppierung "
            "vor dem Packen. Beam Search startet bei Blind gepackt und einer alternierend neu "
            "gruppierten Variante und sucht von beiden aus zusätzlich gezielt nach lohnenden "
            "Hafen-Wechseln und Packstück-Tauschen, poliert das Ergebnis abschließend mit Large "
            "Neighborhood Search - das beste Ergebnis gewinnt (siehe README)."
        )

        st.markdown("**Finale Hafen-Zuordnung im direkten Vergleich**")
        summaries_ordered = [summary_blind, summary_aware, summary_beam]
        cols = st.columns(len(summaries_ordered))
        for col, s in zip(cols, summaries_ordered):
            with col:
                st.caption(f"{s['label']} (final, {s['total_cost']:.0f} €)")
                fig_c = build_freight_map(port_coords, region_coords, s["assignments"], item_regions, item_sizes)
                st.plotly_chart(fig_c, use_container_width=True, key=f"compare_{s['label']}")

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
mit einem andersartig bevorzugten Packstück zusammen einen ganzen Container einsparen,
oder zwei Packstücke tauschen die Container. Beam Search sucht deshalb von zwei
Ausgangslösungen aus (Blind gepackt und einer alternierend neu gruppierten Variante, die
abwechselnd Hafenzuordnung und Packung verfeinert) über mehrere Runden gezielt nach genau
solchen lohnenden Verschiebungen und Tauschen - direkte Bewertung des tatsächlichen
Kosteneffekts statt blinder Neukonstruktion. Das jeweils bessere Zwischenergebnis wird
abschließend mit Large Neighborhood Search poliert: mehrere Container gleichzeitig
komplett neu aufgebaut, um Konfigurationen zu erreichen, die reines Verschieben und
Tauschen einzelner Packstücke nicht findet. Ursprünglich mit mehr Ausgangslösungen
gestartet (u. a. einer eigenständigen Hafen-bewusst- und einer eigenständigen
monobeam-Konstruktion) - beide erwiesen sich in wiederholten Kontrollen als überflüssig,
sobald der Tausch-Zug und Large Neighborhood Search vorhanden waren, und wurden entfernt
(siehe README für die vollständige Herleitung).

**Der Kipppunkt:** Hafen-bewusste Gruppierung (und Beam Search, das darauf aufbaut) führt
tendenziell zu mehr, dafür weniger voll ausgelasteten Containern (die Gruppierung zerteilt
den Packstück-Pool) als blindes Packen. Ob sich das lohnt, hängt vom Verhältnis zwischen
Seefracht (bestraft mehr Container) und Straßenkosten (belohnt zielgerichtete Gruppierung)
ab. Bei niedriger bis mittlerer Seefracht gewinnt die hafen-bewusste Gruppierung praktisch
immer; bei sehr hoher Seefracht kann blindes Packen trotz schlechterer Hafenwahl günstiger
sein, weil es mit weniger Containern auskommt. Probieren Sie den Regler "Seefracht je
Container" aus, um das selbst zu sehen - alle drei Methoden werden bei jeder Einstellung
neu gerechnet, welche gewinnt wird nicht angenommen.

**Alternative Lösungen:** Die kostenoptimale Lösung ist nicht immer die praktikabelste.
Die Häfen-Konsolidierungs-Kurve zeigt, was eine Beschränkung auf wenige Häfen kostet (bei
fester Packung, nur die Hafenwahl je Container variiert über alle Teilmengen erlaubter
Häfen) - relevant, wenn weniger Spediteure/Ansprechpartner oder mehr Verhandlungsmacht bei
einem Anbieter den Aufpreis wert sind. Die ausgeglichene Alternative sucht mit demselben
Tausch-Mechanismus wie oben, aber mit einer anderen Zielfunktion (Streuung der
Container-Füllgrade statt Kosten) - erlaubt dabei einen kleinen Kostenaufschlag (bis 5 %),
um echte Balance-Verbesserungen zu finden statt bei der ersten Kostensteigerung
abzubrechen.

**In echten Projekten** kämen meist weitere Nebenbedingungen dazu (Gewichtsgrenzen,
gefährliche Güter, feste Abfahrtstermine je Hafen, mehrstufige Transportketten) - das
Grundprinzip aus gekoppelter Gruppierung und Bewertung bleibt aber dasselbe.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Gegeben:**

- Packstücke $I = \{1,\dots,n\}$, jedes mit Größe $w_i > 0$ und Zielregion
  $g_i \in \{1,\dots,R\}$
- Häfen $K = \{1,\dots,m\}$
- Container-Kapazität $Q$
- Straßenkosten $c^{road}_{r,k} \geq 0$ je Größeneinheit von Region $r$ über Hafen $k$
  (`road_cost[r][k]`)
- Seefracht $c^{sea}_k \geq 0$ je genutztem Container über Hafen $k$ (`sea_freight[k]`)

**Gesucht:** eine Partition von $I$ in Container $C_1,\dots,C_t$ (Anzahl $t$ frei wählbar)
mit $\sum_{i \in C_c} w_i \leq Q$ für jeden Container $c$, sowie eine Hafenzuordnung
$\delta: \{1,\dots,t\} \to K$, die die Gesamtkosten minimiert:
"""
    )
    st.latex(
        r"\min \; \sum_{c=1}^{t} \Big[\, c^{sea}_{\delta(c)} "
        r"+ \sum_{i \in C_c} w_i \, c^{road}_{g_i,\delta(c)} \Big]"
    )
    st.latex(
        r"\text{u. d. N.} \quad \sum_{i \in C_c} w_i \leq Q \;\; \forall c, "
        r"\qquad \{C_1,\dots,C_t\} \text{ partitioniert } I"
    )
    st.markdown(
        r"""
Als binäres Programm mit Packvariablen $x_{ic} \in \{0,1\}$ (= 1, wenn Packstück $i$ in
Container $c$ liegt), Nutzungsvariablen $y_c \in \{0,1\}$ (= 1, wenn Container $c$
überhaupt verwendet wird) und Hafenvariablen $z_{ck} \in \{0,1\}$ (= 1, wenn Container $c$
über Hafen $k$ verschifft wird), über eine obere Schranke von höchstens $n$ potenziellen
Containern ($c = 1, \dots, n$ - im schlechtesten Fall ein Packstück je Container):
"""
    )
    st.latex(
        r"\min \; \sum_{c=1}^{n} \sum_{k=1}^{m} z_{ck}\, c^{sea}_k "
        r"+ \sum_{c=1}^{n} \sum_{k=1}^{m} \sum_{i=1}^{n} z_{ck}\, x_{ic}\, w_i \, c^{road}_{g_i,k}"
    )
    st.latex(
        r"\text{u. d. N.} \quad \sum_{c=1}^{n} x_{ic} = 1 \;\; \forall i, "
        r"\qquad \sum_{i=1}^{n} x_{ic}\, w_i \leq Q\, y_c \;\; \forall c"
    )
    st.latex(
        r"\sum_{k=1}^{m} z_{ck} = y_c \;\; \forall c, \qquad x_{ic} \leq y_c \;\; \forall i, c"
    )
    st.markdown(
        r"""
Die $z_{ck}\, x_{ic}$-Terme im Ziel machen das Problem in dieser Form quadratisch - linear
lässt sich das mit der Standard-McCormick-Substitution $u_{cki} = z_{ck}\, x_{ic} \in \{0,1\}$
schreiben (für ein Produkt zweier Binärvariablen exakt, kein Big-M nötig):
"""
    )
    st.latex(
        r"u_{cki} \leq z_{ck}, \qquad u_{cki} \leq x_{ic}, "
        r"\qquad u_{cki} \geq z_{ck} + x_{ic} - 1 \qquad \forall c,k,i"
    )
    st.markdown(
        r"""
Im Code wird dieses vollständig linearisierte Programm trotzdem nie aufgestellt oder gelöst
- für einen bereits FESTEN Packstück-Inhalt eines Containers wird die günstigste Hafenwahl
direkt (nicht als weitere Entscheidungsvariable) berechnet, siehe
`_best_port_for_container()` unten.

**Warum NP-schwer:** Für $m=1$ (nur ein Hafen) ist $c^{road}_{g_i,1}$ für jedes Packstück
unabhängig davon fix, in welchem Container es landet - die Straßenkosten-Summe über alle
Packstücke ist dann eine Konstante, unabhängig von der Partition. Die Zielfunktion
reduziert sich exakt auf $c^{sea}_1 \cdot t$ (Seefracht mal Anzahl genutzter Container) -
also auf das Minimieren der Container-Anzahl bei gegebener Kapazität $Q$: das klassische
**1D-Bin-Packing-Problem**, seit Garey & Johnson (1979) als NP-schwer bekannt. Da $m=1$
ein Spezialfall unseres Problems ist, ist auch die allgemeine Version (Bin-Packing UND
Hafenwahl gemeinsam) für $m \geq 1$ NP-schwer - eine Reduktion, kein bloßes Analogieargument.

**First-Fit-Decreasing (`_ffd_pack`):** Packstücke absteigend nach $w_i$ sortiert, jedes in
den ersten Container mit ausreichender Restkapazität gelegt, sonst einen neuen eröffnet.
Für reines 1D-Bin-Packing (ohne Hafenwahl) gilt die von Dósa (2007) als scharf bewiesene
Garantie
"""
    )
    st.latex(r"\mathrm{FFD}(I) \;\leq\; \tfrac{11}{9}\,\mathrm{OPT}(I) + \tfrac{6}{9}")
    st.markdown(
        r"""
(oft locker als "$\tfrac{11}{9}\cdot\mathrm{OPT}+1$" zitiert, so auch im README) - ein
starker Ausgangspunkt, der erklärt, warum die Gruppierungs-Entscheidung (siehe unten) den
Kipppunkt-Effekt dominiert, nicht die Packreihenfolge selbst (siehe README,
Skalierungsanalyse).

**Hafenwahl bei festem Container-Inhalt** (`_best_port_for_container`): für einen
gegebenen Container $C$ der günstigste Hafen
"""
    )
    st.latex(
        r"k^*(C) = \arg\min_{k \,\in\, K} \; \Big[\, c^{sea}_k "
        r"+ \sum_{i \in C} w_i\, c^{road}_{g_i,k} \Big]"
    )
    st.markdown(
        r"""
**Vorab-Gruppierung** (`_group_items_by_best_port`): jede Region wird - NUR anhand der
Straßenkosten, ohne Berücksichtigung der Seefracht - ihrem günstigsten Hafen zugeordnet,
bevor überhaupt gepackt wird. Genutzt von `port_aware_construction` (live als "Hafen-bewusst
gruppiert") und von `_ensemble_best_result` (dem Kern von `flexible_beam_search_construction`,
live als "Beam Search") - außerdem von den beiden Referenzimplementierungen
`beam_search_construction` und `monobeam_construction`, die zum Vergleich im Code bleiben,
aber nicht mehr in die App verdrahtet sind (siehe README):
"""
    )
    st.latex(r"k_{\mathrm{pref}}(r) = \arg\min_{k \,\in\, K} \; c^{road}_{r,k}")
    st.markdown(
        r"""
Packstücke mit gleichem $k_{\mathrm{pref}}(g_i)$ werden zu einer Gruppe zusammengefasst und
separat per First-Fit-Decreasing gepackt - dieselbe Packroutine wie beim blinden Verfahren,
nur mit vorheriger Aufteilung nach Hafen-Präferenz.

**Der Kipppunkt (README) formal:** Sei $\Delta_{road} \geq 0$ die durch die Gruppierung
erzielte Straßenkosten-Ersparnis, und $\Delta_{sea}$ die Summe der Seefracht der zusätzlichen
Container, die die Hafen-bewusste Gruppierung gegenüber blindem Packen tatsächlich benötigt
(empirisch belegt: nie weniger Container, siehe README) - nicht deren Anzahl mal ein
Durchschnittswert, sondern die Summe der konkret gewählten $c^{sea}_{\delta(c)}$ dieser
Container, da einzelne Häfen bis zu 60 % streuen können. Per Kostenbuchhaltung gilt exakt:
Hafen-bewusste Gruppierung ist günstiger genau dann, wenn
"""
    )
    st.latex(r"\Delta_{road} \;>\; \Delta_{sea}")
    st.markdown(
        r"""
- bei niedriger Seefracht dominiert $\Delta_{road}$ (Gruppierung gewinnt praktisch immer),
bei hoher Seefracht dominiert $\Delta_{sea}$ (blind gepackt gewinnt). Weil sowohl die Anzahl
zusätzlicher Container als auch deren tatsächliche Hafenwahl vom konkreten Zufallsszenario
abhängen, gibt es keinen einzelnen festen Seefracht-Wert, der für ALLE Instanzen die Grenze
zieht - genau deshalb ist der in der README-Tabelle empirisch vermessene Übergang graduell
(10/10 → 6/10 → 3/10 → 2/10 → 1/10 über den Seefracht-Multiplikator), nicht abrupt.

**Ausgeglichenere Container** (`balance_containers`) löst ein ZWEITES Optimierungsproblem
auf derselben Struktur: bei gegebener kostenoptimaler Lösung mit Kosten $B^*$ wird die
Streuung der Füllgrade $\rho_c = \big(\sum_{i \in C_c} w_i\big) / Q$ minimiert,
"""
    )
    st.latex(
        r"\min \; \mathrm{Var}(\rho) = \tfrac{1}{t}\textstyle\sum_{c=1}^{t}(\rho_c - \bar\rho)^2 "
        r"\quad \text{u. d. N.} \quad \sum_{c=1}^{t}\big[c^{sea}_{\delta(c)} + \textstyle\sum_{i \in C_c} w_i c^{road}_{g_i,\delta(c)}\big] \leq (1+\tau)\, B^*"
    )
    st.markdown(
        r"""
mit Toleranz $\tau = 0{,}05$ (5 %, Standardwert) - gelöst über paarweise Packstück-Tausche
zwischen zwei Containern, die die Varianz senken, ohne die Kostenschranke zu verletzen.

**Häfen-Konsolidierungs-Kurve** (`port_consolidation_frontier`): bei FESTER Packung wird für
jedes $k=1,\dots,m$ die günstigste $k$-elementige Teilmenge $S \subseteq K$ gesucht, wenn nur
noch Häfen aus $S$ genutzt werden dürfen:
"""
    )
    st.latex(
        r"\min_{S \subseteq K,\, |S|=k} \; \sum_{c=1}^{t} \min_{j \,\in\, S} "
        r"\Big[\, c^{sea}_j + \sum_{i \in C_c} w_i\, c^{road}_{g_i,j} \Big]"
    )
    st.markdown(
        r"""
Bei höchstens $m=5$ Häfen (App-Obergrenze) sind das über alle $k=1,\dots,m$ zusammen
höchstens $2^m - 1 = 31$ nicht-leere Teilmengen - vollständige Enumeration ist hier (anders
als beim Packen selbst) unproblematisch, siehe `port_consolidation_frontier`.

**Warum überhaupt Heuristiken:** selbst OHNE die Hafenwahl mitzuzählen, ist die Anzahl der
Möglichkeiten, $n$ Packstücke in ununterschiedene Container aufzuteilen, die Bell-Zahl
$\beta_n$ - bereits $\beta_{40} \approx 1{,}575 \times 10^{35}$, bei den in der App maximal einstellbaren
100 Packstücken astronomisch größer. Vollständige Enumeration ist von vornherein
ausgeschlossen; `evaluate_assignment()` in `freight_evaluation.py` berechnet exakt die
Zielfunktion von oben ($\texttt{total\_cost}$) für die von den Heuristiken gefundenen
Kandidatenlösungen.
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
