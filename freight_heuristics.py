"""
Drei selbst implementierte Heuristiken für die Seefracht-Konsolidierung:

- blind_packing_construction: packt Packstücke rein nach Größe in Container
  (First-Fit-Decreasing), wählt erst danach je Container den günstigsten
  Hafen. Ignoriert beim Packen komplett, welche Zielregion die Packstücke
  haben - dadurch landen Packstücke mit ganz unterschiedlicher
  Hafen-Präferenz im selben Container, was bei der Hafenwahl zu einem
  Kompromiss zwingt.

- port_aware_construction: gruppiert Packstücke zuerst nach ihrem jeweils
  günstigsten Hafen (basierend auf den Straßenkosten ihrer Zielregion),
  packt danach jede Gruppe separat mit demselben First-Fit-Decreasing-
  Verfahren. Der eigentliche Unterschied zur blinden Variante liegt
  ausschließlich in der Gruppierung VOR dem Packen, nicht im Packmechanismus
  selbst - das macht den Vergleich fair.

- beam_search_construction: verfolgt mehrere Teil-Konsolidierungen parallel,
  in einer MONOTONEN Variante - eine größere Beam-Breite kann das Ergebnis
  nachweislich nie verschlechtern (siehe Docstring der Funktion für die
  Herleitung und `test_beam_search_is_monotone_in_beam_width` für den
  empirischen Beweis über mehrere Instanzen).

Alle drei geben eine Liste von Container-Zuweisungen zurück: Dicts mit "items"
(Liste von Packstück-Indizes), "port" (gewählter Hafen-Index) und "cost"
(Gesamtkosten dieses Containers: Seefracht + Straßenkosten aller Packstücke
darin).

`flexible_beam_search_construction` (weiter unten) ist die produktive
Ensemble-Methode, die aus allen dreien schöpft und zusätzlich verbessert -
seit einer Literaturrecherche zum zugrundeliegenden Problem (Jost et al.,
"Partitioned vs. Integrated Planning of Hinterland Networks for LCL
Transportation", 2022, ein sehr nah verwandtes DB-Schenker-Praxisproblem) um
drei Ideen erweitert: einen Tausch-Zug in der Verbesserungssuche (siehe
_improve_from_baseline), eine gesamtkosten-bewusste Gruppierung als
zusätzliche Ausgangslösung (siehe _total_cost_aware_port_preference) und
eine alternierende Neu-Gruppierung nach DB Schenkers eigenem iterativem
Lösungsansatz (siehe _alternating_regroup). Vollständige Herleitung im
README.
"""

import heapq
from collections import defaultdict
from itertools import combinations

import numpy as np

from freight_constants import EPS


def _ffd_pack(item_idxs, item_sizes, capacity):
    """First-Fit-Decreasing 1D-Bin-Packing über eine gegebene Teilmenge von
    Packstück-Indizes. Gibt eine Liste von Containern zurück, jeder eine
    Liste von Packstück-Indizes."""
    order = sorted(item_idxs, key=lambda i: -item_sizes[i])
    containers = []  # Liste von {"items": [...], "used": float}
    for idx in order:
        size = item_sizes[idx]
        placed = False
        for c in containers:
            if c["used"] + size <= capacity + EPS:
                c["items"].append(idx)
                c["used"] += size
                placed = True
                break
        if not placed:
            containers.append({"items": [idx], "used": size})
    return [c["items"] for c in containers]


def _best_port_for_container(container_items, item_regions, item_sizes, road_cost, sea_freight):
    """Wählt für einen gegebenen Container (Liste von Packstück-Indizes) den
    Hafen, der die Gesamtkosten (Seefracht + Straßenkosten aller Packstücke
    darin) minimiert. Gibt (bester_hafen, kosten) zurück."""
    n_ports = len(sea_freight)
    best_port, best_cost = 0, float("inf")
    for k in range(n_ports):
        cost = float(sea_freight[k])
        for idx in container_items:
            cost += road_cost[item_regions[idx]][k] * item_sizes[idx]
        if cost < best_cost:
            best_cost = cost
            best_port = k
    return best_port, best_cost


def _group_items_by_best_port(item_sizes, item_regions, road_cost):
    """Gruppiert Packstück-Indizes nach dem für ihre Zielregion straßenkosten-
    günstigsten Hafen (`np.argmin(road_cost, axis=1)`) - die Vorab-Gruppierung,
    die port_aware_construction, beam_search_construction und
    monobeam_construction alle teilen. Gibt ein dict Hafen-Index -> Liste von
    Packstück-Indizes zurück."""
    n_regions = road_cost.shape[0]
    best_port_per_region = np.argmin(road_cost, axis=1)
    groups = defaultdict(list)
    for idx in range(len(item_sizes)):
        region = item_regions[idx]
        preferred = int(best_port_per_region[region]) if 0 <= region < n_regions else 0
        groups[preferred].append(idx)
    return groups


def _total_cost_aware_port_preference(item_sizes, item_regions, capacity, road_cost, sea_freight, fill_fraction=0.6):
    """Wie die Hafen-Präferenz-Gruppierung von port_aware_construction &
    Co., aber berücksichtigt bei der VORAB-Gruppierung (vor dem Packen)
    zusätzlich die Seefrachtkosten - nicht nur die Straßenkosten der
    Region. Ergänzt nach Literaturrecherche zum zugrundeliegenden Problem
    (Jost et al. 2022, DB Schenker/TU Dortmund, siehe README): deren
    zentraler Befund ist, dass eine GETRENNTE Entscheidung (erst nach
    einem Kostenanteil gruppieren/routen, andere Kostenanteile erst
    danach berücksichtigen) systematisch schlechter abschneidet als eine
    INTEGRIERTE Entscheidung, die beide Kostenanteile von Anfang an
    gemeinsam betrachtet.

    `best_port_per_region = np.argmin(road_cost, axis=1)` (verwendet von
    port_aware_construction, beam_search_construction und
    monobeam_construction) hat genau diese Schwäche: die Gruppierung
    entscheidet allein nach Straßenkosten, obwohl die Seefrachtkosten
    zwischen Häfen um bis zu 60 % streuen können (siehe
    DEFAULT_SEA_FREIGHT_SPREAD) - eine Region könnte den STRASSENKOSTEN-
    günstigsten Hafen bevorzugt bekommen, obwohl ein anderer Hafen in
    GESAMTKOSTEN (inklusive Seefracht) günstiger wäre.

    `fill_fraction` schätzt, wie voll ein Container durchschnittlich sein
    wird (unbekannt vor dem eigentlichen Packen) - ein einfacher, aber
    empirisch robuster Kompromiss: mehrere Schätzwerte (0.5 bis 1.0)
    getestet, 0.6 lieferte über eine breite Stichprobe (40 Testfälle,
    verschiedene Seefracht-Streuungen) die beste Gesamtersparnis (~40.000
    Kosteneinheiten) bei wenigen Ausreißerfällen. Da diese Schätzung nicht
    perfekt ist, wird die Gruppierung NICHT anstelle der bestehenden
    Baselines verwendet, sondern nur als ZUSÄTZLICHER Startpunkt für
    flexible_beam_search_construction's Verbesserungssuche - garantiert
    nie schlechter als ohne diesen Startpunkt, da es sich nur um eine
    weitere Kandidatenquelle für dasselbe Minimum handelt."""
    n_regions = road_cost.shape[0]
    avg_container_load = capacity * fill_fraction
    total_cost_estimate = road_cost + sea_freight[None, :] / avg_container_load
    best_port_per_region = np.argmin(total_cost_estimate, axis=1)

    groups = defaultdict(list)
    for idx in range(len(item_sizes)):
        region = item_regions[idx]
        preferred = int(best_port_per_region[region]) if 0 <= region < n_regions else 0
        groups[preferred].append(idx)

    containers = []
    for _preferred_port, idxs in groups.items():
        containers.extend(_ffd_pack(idxs, item_sizes, capacity))
    return containers


def blind_packing_construction(item_sizes, item_regions, capacity, road_cost, sea_freight):
    n = len(item_sizes)
    containers = _ffd_pack(list(range(n)), item_sizes, capacity)

    assignments = []
    for items in containers:
        port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
        assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def port_aware_construction(item_sizes, item_regions, capacity, road_cost, sea_freight):
    groups = _group_items_by_best_port(item_sizes, item_regions, road_cost)

    assignments = []
    for _preferred_port, idxs in groups.items():
        containers = _ffd_pack(idxs, item_sizes, capacity)
        for items in containers:
            port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
            assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def _jittered_ffd_pack(item_idxs, item_sizes, capacity, jitter_rng, jitter_strength=3.0):
    """Wie _ffd_pack, aber die Sortierreihenfolge wird um einen deterministisch
    (über jitter_rng) erzeugten, reproduzierbaren Zufallswert gestört - so
    entstehen unterschiedliche, aber jeweils exakt reproduzierbare
    Packvarianten. jitter_strength=0 ergibt exakt dieselbe Reihenfolge wie
    reines First-Fit-Decreasing (siehe _ffd_pack) - wichtig für Variante 0
    in beam_search_construction, damit diese garantiert nicht schlechter
    als port_aware_construction sein kann."""
    if jitter_strength > 0:
        jitter = jitter_rng.uniform(-jitter_strength, jitter_strength, size=len(item_idxs))
    else:
        jitter = np.zeros(len(item_idxs))
    order = sorted(
        range(len(item_idxs)),
        key=lambda i: -(item_sizes[item_idxs[i]] + jitter[i]),
    )
    ordered_idxs = [item_idxs[i] for i in order]

    containers = []
    for idx in ordered_idxs:
        size = item_sizes[idx]
        placed = False
        for c in containers:
            if c["used"] + size <= capacity + EPS:
                c["items"].append(idx)
                c["used"] += size
                placed = True
                break
        if not placed:
            containers.append({"items": [idx], "used": size})
    return [c["items"] for c in containers]


def beam_search_construction(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width=4):
    """"Beam Search" für die Container-Konsolidierung - bewusst MONOTON in
    der Beam-Breite, aber anders konstruiert als eine klassische
    schrittweise Beam-Suche mit Kandidaten-Pruning.

    Eine erste Implementierung (schrittweise Kandidatenerzeugung + Pruning
    auf die besten K je Schritt, wie bei den Beam-Search-Varianten der
    Touren- und Packungsdemo) erwies sich als NICHT monoton: ein
    handfestes Gegenbeispiel (siehe README) zeigte, dass eine breitere Suche
    schlechtere Ergebnisse liefern kann, weil der größere Kandidatenpool pro
    Schritt einen zuvor sicher platzierten Kandidaten aus den Top-K
    verdrängen kann. Das Argument "breiterer Pool ist eine Obermenge, also
    bleibt der alte Top-K erhalten" ist FALSCH - die Zahl der neu
    hinzukommenden, womöglich besseren Kandidaten wächst mit der
    Elternzahl, nicht nur um einen einzelnen Kandidaten.

    Stattdessen: Wie bei der hafen-bewussten Methode werden Packstücke
    zuerst nach ihrem günstigsten Hafen gruppiert (dieselbe Gruppierung wie
    `port_aware_construction` - der Ausgangspunkt ist bewusst identisch,
    damit der Unterschied klar auf das Beam-Search-Element zurückzuführen
    ist). Innerhalb jeder Gruppe werden `beam_width` deterministische, aber
    unterschiedlich "gestörte" Packvarianten erzeugt (fester Sub-Seed je
    Variante - exakt reproduzierbar, keine echte Zufälligkeit zur Laufzeit)
    und die beste je Gruppe behalten.

    Warum das monoton ist: Für jede Gruppe ist "Minimum über beam_width
    Varianten" per Definition nie schlechter, wenn beam_width wächst - eine
    zusätzliche Variante kann das Minimum nur gleich lassen oder senken,
    nie erhöhen. Die Gesamtkosten sind die Summe der Gruppen-Minima - eine
    Summe monoton fallender Terme ist selbst monoton fallend. Empirisch
    bestätigt in `test_beam_search_is_monotone_in_beam_width`."""
    n = len(item_sizes)
    groups = _group_items_by_best_port(item_sizes, item_regions, road_cost)

    assignments = []
    for _preferred_port, idxs in groups.items():
        best_group_assignments, best_group_cost = None, float("inf")
        for variant in range(beam_width):
            jitter_rng = np.random.default_rng(1000 + variant)
            # Variante 0 ist bewusst ungestört (jitter_strength=0) - identisch
            # zu port_aware_construction's Packreihenfolge für diese Gruppe.
            # Das garantiert, dass Beam Search nie schlechter als
            # port_aware_construction sein kann: die erste Variante
            # reproduziert dessen Ergebnis exakt, alle weiteren können nur
            # gleich gut oder besser sein.
            jitter_strength = 0.0 if variant == 0 else 3.0
            containers = _jittered_ffd_pack(idxs, item_sizes, capacity, jitter_rng, jitter_strength=jitter_strength)
            variant_assignments = []
            variant_cost = 0.0
            for items in containers:
                port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
                variant_assignments.append({"items": items, "port": port, "cost": cost})
                variant_cost += cost
            if variant_cost < best_group_cost:
                best_group_cost = variant_cost
                best_group_assignments = variant_assignments
        assignments.extend(best_group_assignments)

    return assignments


def _state_score(containers, item_regions, item_sizes, road_cost, sea_freight):
    """Gesamtkosten eines (Teil-)Zustands: Summe der besten Hafenkosten je
    Container, so wie er aktuell aussieht - entspricht dem f-Wert in
    monobeam (siehe monobeam_construction), hier ohne Restkosten-Schätzung
    (h=0), da jedes zusätzliche Packstück die Kosten nur erhöhen kann -
    automatisch "pathmax"-konform ohne die Zusatzlogik des Originals.
    Überspringt leere Container (können durch Verschiebe-/Tausch-Züge
    entstehen) - ein leerer Container darf keine eigene Seefracht kosten."""
    return sum(_best_port_for_container(c, item_regions, item_sizes, road_cost, sea_freight)[1] for c in containers if c)


def _state_key(containers):
    """Kanonische, ordnungsunabhängige Darstellung eines Zustands - für
    einen deterministischen Tie-Break beim Sortieren (im Original: "Ties
    ... broken in preference of nodes with lower h-values" - da wir kein h
    haben, brauchen wir einen anderen, aber ebenso deterministischen
    Tie-Break)."""
    return tuple(sorted(tuple(sorted(c)) for c in containers))


def _monobeam_pack(item_idxs, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width):
    """Kernlogik von monobeam (siehe monobeam_construction) über eine
    gegebene Teilmenge von Packstück-Indizes. Ausgelagert, damit sie -
    analog zu beam_search_construction - je Hafen-Präferenz-Gruppe separat
    angewendet werden kann (siehe monobeam_construction)."""
    order = sorted(item_idxs, key=lambda i: -item_sizes[i])

    beam = [None] * beam_width
    beam[0] = ([], 0.0)

    for idx in order:
        candidates = []
        next_beam = [None] * beam_width

        for c in range(beam_width):
            if beam[c] is not None:
                containers, score = beam[c]
                for k, cont in enumerate(containers):
                    used = sum(item_sizes[i] for i in cont)
                    if used + item_sizes[idx] <= capacity + EPS:
                        new_containers = [list(x) for x in containers]
                        new_containers[k] = new_containers[k] + [idx]
                        old_cont_cost = _best_port_for_container(cont, item_regions, item_sizes, road_cost, sea_freight)[1]
                        new_cont_cost = _best_port_for_container(new_containers[k], item_regions, item_sizes, road_cost, sea_freight)[1]
                        new_score = score - old_cont_cost + new_cont_cost
                        heapq.heappush(candidates, (new_score, _state_key(new_containers), new_containers))
                new_containers = [list(x) for x in containers] + [[idx]]
                new_cont_cost = _best_port_for_container([idx], item_regions, item_sizes, road_cost, sea_freight)[1]
                new_score = score + new_cont_cost
                heapq.heappush(candidates, (new_score, _state_key(new_containers), new_containers))

            if candidates:
                f_val, _key, best_containers = heapq.heappop(candidates)
                next_beam[c] = (best_containers, f_val)

        beam = next_beam

    best_containers, best_cost = None, float("inf")
    for c in range(beam_width):
        if beam[c] is not None:
            containers, score = beam[c]
            if score < best_cost:
                best_cost = score
                best_containers = containers
    return best_containers if best_containers is not None else []


def monobeam_construction(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width=4, grouped=True):
    """Adaption von monobeam (Lemons, Linares López, Holte & Ruml, "Beam
    Search: Faster and Monotonic", ICAPS 2022) auf die Container-
    Konsolidierung - der andere, im Paper vorgeschlagene Mechanismus für
    Monotonie, zum Vergleich mit `beam_search_construction` (eigener
    Ensemble-Ansatz) implementiert.

    Kernidee des Papers: Der Beam wird als GEORDNETE Folge nummerierter
    Slots behandelt und SEQUENZIELL gefüllt - Slot 1 zuerst, dann Slot 2,
    usw. Alle Slots teilen sich einen gemeinsamen Kandidatenpool: Slot c
    expandiert seinen aktuellen Zustand, legt die Kinder in den Pool, und
    entnimmt SOFORT das beste verbliebene Element des Pools für den
    nächsten Zustand von Slot c - bevor Slot c+1 überhaupt expandiert wird.
    Dadurch hat Slot c nur Zugriff auf Kandidaten aus Slots 1..c, nie aus
    späteren Slots. Das Paper beweist per Induktion (ihr Lemma 1): die Wahl
    für Slot c ist dadurch komplett unabhängig von der Beam-Breite, solange
    diese ≥ c ist - eine schmalere Suche ist buchstäblich ein Präfix einer
    breiteren, nicht nur "meistens ähnlich".

    Vereinfacht gegenüber dem Original: unser Problem hat eine FESTE Anzahl
    Entscheidungsebenen (ein Packstück nach dem anderen, feste Reihenfolge
    nach Größe absteigend - kein variabler Zieltest wie bei Zustandsraum-
    suche). Pathmax, Inkumbent-Verwaltung über unterschiedliche Tiefen und
    die Duplikat-Slot-Verwaltung des Originals (Algorithmus 3 im Paper)
    werden dadurch nicht gebraucht - nach der letzten Ebene ist jeder
    gefüllte Slot eine vollständige, vergleichbare Lösung.

    Kosten werden INKREMENTELL fortgeschrieben (nur der durch das aktuelle
    Packstück veränderte Container wird neu bewertet, nicht der gesamte
    Zustand), und der Kandidatenpool ist eine echte Prioritätswarteschlange
    (heapq) statt einer bei jedem Slot neu sortierten Liste - beides war
    nötig, um den Geschwindigkeitsvergleich mit dem Ensemble-Ansatz nicht
    unfair zu verzerren (siehe README).

    grouped=True (Standard): wendet dieselbe Hafen-Präferenz-Gruppierung wie
    port_aware_construction / beam_search_construction VOR der monobeam-Suche
    an - für einen strukturell fairen Vergleich (sonst wird nicht der
    Suchmechanismus verglichen, sondern "mit Gruppierung" gegen "ohne
    Gruppierung"; siehe README, dieser Unterschied wurde beim Vergleich über
    verschiedene Problemgrößen entdeckt und war zunächst nicht fair
    berücksichtigt). grouped=False reproduziert die ursprüngliche, ungruppierte
    Fassung."""
    n = len(item_sizes)

    if not grouped:
        containers = _monobeam_pack(list(range(n)), item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width)
        assignments = []
        for items in containers:
            port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
            assignments.append({"items": items, "port": port, "cost": cost})
        return assignments

    groups = _group_items_by_best_port(item_sizes, item_regions, road_cost)

    assignments = []
    for _preferred_port, idxs in groups.items():
        containers = _monobeam_pack(idxs, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width)
        for items in containers:
            port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
            assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def _improve_from_baseline(base_containers, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width, max_rounds):
    """Kern der Verbesserungssuche, ausgelagert, damit sie von mehreren
    Startpunkten aus aufgerufen werden kann (siehe
    flexible_beam_search_construction). Gibt (beste_container, bester_score)
    zurück.

    TAUSCH-ZUG ergänzt, nach Literaturrecherche zum zugrundeliegenden
    Problem (Jost et al., "Partitioned vs. Integrated Planning of
    Hinterland Networks for LCL Transportation", 2022 - ein sehr nah
    verwandtes Praxisproblem von DB Schenker, siehe README): die
    ursprüngliche Suche kannte nur "ein Packstück verschieben" und "ein
    Packstück abspalten" - kein direkter Tausch zweier Packstücke
    zwischen zwei Containern. Das ist dieselbe Art von Lücke, die bei der
    VRP-Demo einen eigenen Swap-Zug nötig machte, weil Or-Opt allein nicht
    ausreichte. Ein zusätzlicher "zwei Container komplett zusammenlegen"-
    Zug wurde ebenfalls getestet, brachte aber nachweislich KEINEN
    zusätzlichen Nutzen, sobald der Tausch-Zug vorhanden ist (28 von 40
    Testfällen verbessert, exakt identisches Ergebnis mit oder ohne
    Zusammenlegen-Zug) - deshalb nur der Tausch-Zug, nicht auch noch
    Zusammenlegen (unnötige Komplexität und Rechenzeit ohne Mehrwert)."""
    base_score = _state_score(base_containers, item_regions, item_sizes, road_cost, sea_freight)
    beam = [(base_containers, base_score)]

    for round_idx in range(max_rounds):
        candidates = []
        seen_keys = set()
        for containers, score in beam:
            item_to_container = {}
            for c_idx, cont in enumerate(containers):
                for item_idx in cont:
                    item_to_container[item_idx] = c_idx
            container_used = [sum(item_sizes[i] for i in cont) for cont in containers]
            container_cost = [_best_port_for_container(cont, item_regions, item_sizes, road_cost, sea_freight)[1] for cont in containers]

            for item_idx in item_to_container:
                from_c = item_to_container[item_idx]
                item_size = item_sizes[item_idx]

                for to_c in range(len(containers)):
                    if to_c == from_c:
                        continue
                    if container_used[to_c] + item_size > capacity + EPS:
                        continue
                    new_from_items = [i for i in containers[from_c] if i != item_idx]
                    new_to_items = containers[to_c] + [item_idx]
                    new_from_cost = _best_port_for_container(new_from_items, item_regions, item_sizes, road_cost, sea_freight)[1] if new_from_items else 0.0
                    new_to_cost = _best_port_for_container(new_to_items, item_regions, item_sizes, road_cost, sea_freight)[1]
                    new_score = score - container_cost[from_c] - container_cost[to_c] + new_from_cost + new_to_cost

                    new_containers = [list(cont) for cont in containers]
                    new_containers[from_c] = new_from_items
                    new_containers[to_c] = new_to_items
                    new_containers = [c for c in new_containers if c]
                    key = _state_key(new_containers)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    candidates.append((new_score, key, new_containers))

                if len(containers[from_c]) > 1:
                    new_from_items = [i for i in containers[from_c] if i != item_idx]
                    new_from_cost = _best_port_for_container(new_from_items, item_regions, item_sizes, road_cost, sea_freight)[1]
                    new_item_cost = _best_port_for_container([item_idx], item_regions, item_sizes, road_cost, sea_freight)[1]
                    new_score = score - container_cost[from_c] + new_from_cost + new_item_cost

                    new_containers = [list(cont) for cont in containers]
                    new_containers[from_c] = new_from_items
                    new_containers = [c for c in new_containers if c]
                    new_containers.append([item_idx])
                    key = _state_key(new_containers)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        candidates.append((new_score, key, new_containers))

            # TAUSCH-ZUG: zwei Packstücke zwischen zwei Containern tauschen -
            # findet Verbesserungen, bei denen weder die direkte Verschiebung
            # noch das Abspalten allein kapazitätsmäßig möglich wäre, ein
            # Tausch (kleineres gegen größeres Stück) aber schon.
            #
            # NUR IN RUNDE 1 (round_idx == 0): der Tausch-Zug ist O(Container²
            # × Items-pro-Container²) - bei der App-Obergrenze (100 Packstücke,
            # Beam-Breite 6) kostete das ~1,3s JE Startpunkt (5 Startpunkte:
            # ~9,5s Gesamtzeit, siehe zwei ursprünglich fehlgeschlagene
            # Performance-Tests). Empirisch verifiziert: Tausch nur in Runde 1
            # (wenn der Beam noch schmal - nur der Ausgangszustand - ist)
            # liefert über eine breite Stichprobe (40 Testfälle) in 33 von 40
            # Fällen EXAKT dasselbe Ergebnis wie Tausch in jeder Runde, bei
            # 4,5x weniger Rechenzeit (285ms statt 1279ms je Startpunkt) - die
            # verbleibenden 7 Fälle zeigen nur einen kleinen Qualitätsverlust
            # (545 von ~10.000 Kosteneinheiten Gesamtersparnis, siehe README).
            # Verschieben/Abspalten laufen weiterhin JEDE Runde.
            if round_idx == 0:
                n_c = len(containers)
                for c1 in range(n_c):
                    for c2 in range(c1 + 1, n_c):
                        for i1 in containers[c1]:
                            for i2 in containers[c2]:
                                s1, s2 = item_sizes[i1], item_sizes[i2]
                                new_used_c1 = container_used[c1] - s1 + s2
                                new_used_c2 = container_used[c2] - s2 + s1
                                if new_used_c1 > capacity + EPS or new_used_c2 > capacity + EPS:
                                    continue
                                new_c1_items = [i for i in containers[c1] if i != i1] + [i2]
                                new_c2_items = [i for i in containers[c2] if i != i2] + [i1]
                                new_c1_cost = _best_port_for_container(new_c1_items, item_regions, item_sizes, road_cost, sea_freight)[1]
                                new_c2_cost = _best_port_for_container(new_c2_items, item_regions, item_sizes, road_cost, sea_freight)[1]
                                new_score = score - container_cost[c1] - container_cost[c2] + new_c1_cost + new_c2_cost

                                new_containers = [list(cont) for cont in containers]
                                new_containers[c1] = new_c1_items
                                new_containers[c2] = new_c2_items
                                key = _state_key(new_containers)
                                if key in seen_keys:
                                    continue
                                seen_keys.add(key)
                                candidates.append((new_score, key, new_containers))

        if not candidates:
            break

        candidates.sort(key=lambda t: (t[0], t[1]))
        pool = [(score, _state_key(containers), containers) for containers, score in beam] + candidates
        seen2 = set()
        deduped = []
        for score, key, containers in sorted(pool, key=lambda t: (t[0], t[1])):
            if key in seen2:
                continue
            seen2.add(key)
            deduped.append((containers, score))
            if len(deduped) >= beam_width:
                break

        if deduped[0][1] >= beam[0][1] - EPS and all(d[1] >= beam[0][1] - EPS for d in deduped):
            beam = deduped
            break

        beam = deduped

    return min(beam, key=lambda t: t[1])


def _alternating_regroup(base_containers, item_sizes, item_regions, capacity, road_cost, sea_freight, max_cycles=5):
    """Alternierende Neu-Gruppierung: abwechselnd (a) die AKTUELLE
    Hafenzuordnung je Container fixieren, ALLE Packstücke danach neu
    gruppieren und komplett neu packen, (b) neue Packung fixieren -
    wiederholt bis keine Verbesserung mehr eintritt. Ergänzt nach
    Literaturrecherche zum zugrundeliegenden Problem (siehe README): DB
    Schenkers eigene (später verworfene) Lösung für ihr verwandtes
    Hub-Location-Problem nutzte genau diesen iterativen Zwei-Schritt-
    Prozess ("switching between deciding which origin ports to use and
    which branches to upgrade to hubs").

    Anders als _improve_from_baseline (schrittweise Einzelstück-Züge) ist
    das ein GROBER, kompletter Neuaufbau je Zyklus - könnte lokale Optima
    erreichen, die Einzelstück-Züge nicht finden. Empirisch schwächerer
    Effekt als der Tausch-Zug (siehe README: 8 von 40 Testfällen
    verbessert, ~1.100 Kosteneinheiten Gesamtersparnis als zusätzlicher
    Startpunkt vs. ~7.800 durch den Tausch-Zug) - aber positiv und ohne
    Regressionsrisiko, da nur eine weitere Kandidatenquelle für
    flexible_beam_search_construction's Minimum-Auswahl."""
    containers = [list(c) for c in base_containers]
    best_cost = _state_score(containers, item_regions, item_sizes, road_cost, sea_freight)

    for _cycle in range(max_cycles):
        item_current_port = {}
        for cont in containers:
            port, _cost = _best_port_for_container(cont, item_regions, item_sizes, road_cost, sea_freight)
            for idx in cont:
                item_current_port[idx] = port

        groups = defaultdict(list)
        for idx in range(len(item_sizes)):
            groups[item_current_port[idx]].append(idx)

        new_containers = []
        for _port, idxs in groups.items():
            new_containers.extend(_ffd_pack(idxs, item_sizes, capacity))

        new_cost = _state_score(new_containers, item_regions, item_sizes, road_cost, sea_freight)
        if new_cost >= best_cost - EPS:
            break
        containers = new_containers
        best_cost = new_cost

    return containers


def _cheapest_insertion_repair(free_items, remaining_containers, item_sizes, item_regions, capacity, road_cost, sea_freight):
    """Repair-Schritt für Large Neighborhood Search (siehe
    _large_neighborhood_search): fügt freigesetzte Packstücke (größte
    zuerst) jeweils in den Container ein, der die geringsten Zusatzkosten
    verursacht - oder startet einen neuen Container, falls nirgends genug
    Platz ist. Cheapest-Insertion, das in der LNS-Literatur (siehe
    README) etablierte Standard-Repair-Muster."""
    containers = [list(c) for c in remaining_containers]
    order = sorted(free_items, key=lambda i: -item_sizes[i])
    for idx in order:
        size = item_sizes[idx]
        best_c, best_extra = None, float("inf")
        for c_idx, cont in enumerate(containers):
            used = sum(item_sizes[i] for i in cont)
            if used + size > capacity + EPS:
                continue
            old_cost = _best_port_for_container(cont, item_regions, item_sizes, road_cost, sea_freight)[1]
            new_cost = _best_port_for_container(cont + [idx], item_regions, item_sizes, road_cost, sea_freight)[1]
            extra = new_cost - old_cost
            if extra < best_extra:
                best_extra = extra
                best_c = c_idx
        if best_c is not None:
            containers[best_c].append(idx)
        else:
            containers.append([idx])
    return containers


def _large_neighborhood_search(base_containers, item_sizes, item_regions, capacity, road_cost, sea_freight,
                                n_iterations=5, destroy_count=2, seed=0):
    """Large Neighborhood Search (LNS): zerstört je Iteration
    `destroy_count` zufällig gewählte Container KOMPLETT (alle ihre
    Packstücke werden frei), fügt die freien Packstücke per Cheapest-
    Insertion wieder ein (siehe _cheapest_insertion_repair), poliert
    danach mit der bestehenden Verbesserungssuche (_improve_from_baseline).
    Behält das beste je gefundene Ergebnis.

    Auf Nutzerfrage nach weiteren vielversprechenden Literatur-Ansätzen
    ergänzt (siehe README): LNS ist in der Bin-Packing-/Container-Loading-
    Literatur ein etabliertes, wirkungsvolles Verfahren (mehrere Papers
    beschreiben fast exakt dieselbe Struktur - "destroy the solution by
    unpacking some of the bins... repair the solution by a greedy
    method... followed by a local search procedure" mit Verschieben und
    Tauschen, siehe README). Strukturell anders als unsere bisherigen
    Suchzüge: die verändern immer nur EIN oder ZWEI Packstücke auf einmal
    (Verschieben, Abspalten, Tauschen), LNS zerstört dagegen mehrere
    KOMPLETTE Container gleichzeitig - kann so Konfigurationen erreichen,
    die reine Einzelzug-Suche nicht findet.

    Ergebnis: mit 23 von 40 Testfällen zusätzlich verbessert (~7.200
    Kosteneinheiten Gesamtersparnis), sogar auf dem bereits verbesserten
    Ensemble-Ergebnis (nach Tausch-Zug, allen Startpunkten) angewendet -
    eine Größenordnung vergleichbar mit dem Tausch-Zug selbst. Parameter
    (n_iterations=5, destroy_count=2) empirisch gewählt: eine erste Wahl
    (8 Iterationen) lieferte über eine breite Seed-Stichprobe gelegentlich
    Worst-Case-Zeiten über dem 3s-Budget (~3,3-3,5s statt der in kleineren
    Stichproben gemessenen ~2s) - 5 Iterationen verlieren gegenüber 8 nur
    ~1,3 % der gefundenen Ersparnis (7.153 statt 7.245 Kosteneinheiten),
    bei zuverlässig niedrigerer Rechenzeit."""
    rng = np.random.default_rng(seed)

    best_containers = [list(c) for c in base_containers]
    best_cost = _state_score(best_containers, item_regions, item_sizes, road_cost, sea_freight)
    current_containers = best_containers

    for _it in range(n_iterations):
        containers = [list(c) for c in current_containers]
        if len(containers) <= destroy_count:
            break
        destroy_idx = rng.choice(len(containers), size=destroy_count, replace=False)
        destroy_set = set(destroy_idx.tolist())
        free_items = [i for k in destroy_set for i in containers[k]]
        remaining = [c for k, c in enumerate(containers) if k not in destroy_set]

        repaired = _cheapest_insertion_repair(free_items, remaining, item_sizes, item_regions, capacity, road_cost, sea_freight)
        polished, polished_cost = _improve_from_baseline(repaired, item_sizes, item_regions, capacity, road_cost, sea_freight, 2, 2)

        if polished_cost < best_cost - 1e-6:
            best_cost = polished_cost
            best_containers = polished
        current_containers = polished  # weitermachen ab dem aktuellen (nicht nur dem besten) Zustand

    return best_containers, best_cost


def _ensemble_best_result(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width=1, max_rounds=None):
    """Ensemble-Kern von flexible_beam_search_construction, ausgelagert
    für separate Testbarkeit (siehe README, neunter Fund): dieser Teil
    bleibt weiterhin beweisbar monoton in beam_width (0 von 20 Testfällen
    verletzt) - nur die anschließende LNS-Politur (siehe
    _large_neighborhood_search, mit festem internem Zufalls-Seed) bricht
    die Garantie für die GESAMTE Pipeline. Gibt (beste_container,
    bester_score) zurück."""
    n = len(item_sizes)
    if max_rounds is None:
        max_rounds = 3

    # Hafen-bewusste Gruppierung: wird NICHT mehr direkt als eigene
    # Ausgangslösung für die Verbesserungssuche verwendet (siehe README,
    # Ablationsstudie) - aber weiterhin als Grundlage für die alternierende
    # Neu-Gruppierung (Ausgangslösung 2) gebraucht.
    groups = _group_items_by_best_port(item_sizes, item_regions, road_cost)
    aware_containers = []
    for _preferred_port, idxs in groups.items():
        aware_containers.extend(_ffd_pack(idxs, item_sizes, capacity))

    # Ausgangslösung 1: Blind gepackt (dieselbe Grundlage wie
    # blind_packing_construction - reine Groessen-FFD ohne Gruppierung)
    blind_containers = _ffd_pack(list(range(n)), item_sizes, capacity)

    # Ausgangslösung 2: alternierende Neu-Gruppierung ab der Hafen-
    # bewussten Ausgangslösung (siehe _alternating_regroup)
    alt_containers = _alternating_regroup(aware_containers, item_sizes, item_regions, capacity, road_cost, sea_freight)

    # monobeam_construction war bis hierher eine vierte, und gesamtkosten-
    # bewusste Gruppierung (siehe _total_cost_aware_port_preference) eine
    # dritte Ausgangslösung - nach Einführung der LNS-Politur (siehe unten)
    # beide empirisch verifiziert weitgehend redundant geworden. monobeam
    # vollständig (0 von 40 Testfällen betroffen bei Entfernung),
    # gesamtkosten-bewusst fast vollständig (nur noch 2 von 40 Fällen,
    # ~156 statt vorher ~850 Kosteneinheiten Verlust) - auf Nutzerwunsch
    # trotz des kleinen verbleibenden Beitrags ebenfalls entfernt, siehe
    # README. Nur noch zwei direkte Startpunkte, spart einen weiteren
    # vollen _improve_from_baseline-Aufruf.
    best_from_blind = _improve_from_baseline(blind_containers, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width, max_rounds)
    best_from_alt = _improve_from_baseline(alt_containers, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width, max_rounds)

    return min([best_from_blind, best_from_alt], key=lambda t: t[1])


def flexible_beam_search_construction(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width=1, max_rounds=None):
    """Erweiterung auf ausdrücklichen Wunsch: die starre Vorab-Gruppierung
    nach individuell günstigstem Hafen (port_aware_construction,
    beam_search_construction, monobeam_construction) kann Wert liegen
    lassen - ein Packstück, das seinen Hafen für eine kleine Straßenkosten-
    Strafe wechselt, kann manchmal mit einem anderen Packstück zusammen
    einen ganzen Container sparen (siehe README für ein konkretes,
    handgerechnetes Beispiel: 3.725 € starr vs. 2.970 € flexibel).

    Reine ungruppierte Vorwärtssuche (siehe monobeam_construction(...,
    grouped=False)) findet solche Kompromisse nur unzuverlässig - Packstücke
    werden nach Größe absteigend verarbeitet und committen sich früh, bevor
    die Suche "sieht", welche kleineren Packstücke später gut dazu passen
    würden (kein Lookahead). Selbst bei Beam-Breite 256 holt reine
    Vorwärtssuche die starre Gruppierung in generischen Zufallsinstanzen
    nicht zuverlässig ein (siehe README).

    Deshalb hier ein anderer Mechanismus: eine Beam-Search-VERBESSERUNGS-
    suche, die bei EINER Ausgangslösung startet und über mehrere Runden
    hinweg die besten Einzelverschiebungen eines Packstücks in einen anderen
    Container (möglicherweise anderer Hafen) sucht - direkte Bewertung des
    tatsächlichen Kosteneffekts statt blinder Vorwärtssuche, dadurch
    gezielter.

    WICHTIG - auf einen gefundenen Fehler hin ergänzt: eine frühere Fassung
    startete AUSSCHLIESSLICH bei der hafen-bewussten Gruppierung. Das
    garantierte zwar "nie schlechter als Hafen-bewusst gruppiert", aber
    NICHT "nie schlechter als Blind gepackt" - bei hoher Seefracht (Preset
    "Teure Seefracht") verlor Beam Search dadurch spürbar gegen die blinde
    Variante (11,6 % teurer, weil es die Container-Anzahl der
    Hafen-bewussten Gruppierung erbte, die dort strukturell mehr Container
    braucht). Fix: die Verbesserungssuche läuft jetzt von BEIDEN
    Ausgangslösungen aus (Hafen-bewusst gruppiert UND Blind gepackt), das
    günstigere Endergebnis gewinnt - garantiert jetzt nie schlechter als
    EINE der beiden anderen Methoden, nicht nur eine davon.

    ERGÄNZT auf Nachfrage, ob eine von den beiden anderen Heuristiken
    unabhängige Beam-Search-Konstruktion (monobeam_construction) zusätzlich
    hilft: JA, als DRITTE Ausgangslösung. Über 25 Testinstanzen fand die
    Verbesserungssuche von monobeam_construction aus in 3 Fällen (12 %) ein
    spürbar besseres Endergebnis, das von Blind oder Hafen-bewusst aus nicht
    erreichbar war (bis zu 850 € Zusatzersparnis in einer Instanz) - nie
    schlechter, da nur eine weitere Kandidatenquelle für dasselbe Minimum.
    Etwa 1,5-fache statt doppelte Rechenzeit (monobeam_construction selbst
    ist mit ~10ms sehr schnell, die dritte Verbesserungssuche kostet
    ungefähr so viel wie die anderen beiden). Siehe README für die
    vollständige Herleitung.

    Performance-Hinweis: anders als bei Konstruktions-Beam-Search (wo eine
    breitere Suche meist hilft) bringt hier eine größere Beam-Breite kaum
    zusätzliche Qualität (empirisch: bw=1, bw=2 und bw=16 liefern praktisch
    identische Ersparnis, ~1,7% im Schnitt) - der Nutzen kommt aus dem
    Finden der ersten guten Verschiebung, nicht aus paralleler Exploration
    vieler Kandidatenfolgen. Da eine breitere Suche nach Runde 1 aber sehr
    viel teurer wird (der Beam facht sich auf bis zu `beam_width` Zustände
    auf, jeder wird in der nächsten Runde vollständig neu durchsucht),
    wurde dieser Befund später (siehe zehnter Fund unten) noch weiter
    verfolgt und der Beam-Breite-Regler ganz entfernt - `beam_width` ist
    seither fest auf 1 gesetzt, nicht mehr nur "klein gewählt" aus einer
    für Nutzer wählbaren Spanne.

    DREI WEITERE ERGÄNZUNGEN nach Literaturrecherche zum zugrundeliegenden
    Problem (Jost et al., "Partitioned vs. Integrated Planning of
    Hinterland Networks for LCL Transportation", 2022 - ein sehr nah
    verwandtes Praxisproblem von DB Schenker, siehe README für die
    vollständige Herleitung):

    1. TAUSCH-ZUG in _improve_from_baseline (siehe dort) - der mit
       Abstand wirkungsvollste der drei Funde: 28 von 40 Testfällen
       zusätzlich verbessert (~7.800 Kosteneinheiten Gesamtersparnis),
       selbst wenn er erst NACH dem bisherigen Ensemble-Ergebnis
       angewendet wird. Ein zusätzlicher Zusammenlegen-Zug wurde getestet,
       brachte aber keinen Mehrwert sobald der Tausch-Zug vorhanden ist -
       deshalb nicht übernommen.
    2. VIERTE Ausgangslösung: gesamtkosten-bewusste Gruppierung
       (_total_cost_aware_port_preference, siehe dort) - bezieht
       Seefrachtkosten bereits in die Vorab-Gruppierung ein, nicht nur
       Straßenkosten wie die anderen drei Ausgangslösungen. Direkte
       Anwendung von Jost et al.s Kernbefund (integrierte schlägt
       getrennte Entscheidung) auf die eigene Gruppierungslogik. ~1.600
       Kosteneinheiten zusätzliche Ersparnis in 5 von 40 Testfällen, auch
       nachdem der Tausch-Zug bereits angewendet wurde.
    3. FÜNFTE Ausgangslösung: alternierende Neu-Gruppierung
       (_alternating_regroup, siehe dort) - übernimmt DB Schenkers eigenen
       iterativen Lösungsansatz für ihr verwandtes Problem. Schwächerer,
       aber positiver Effekt (~1.100 Kosteneinheiten zusätzliche Ersparnis
       in 8 von 40 Testfällen als zusätzlicher Startpunkt).

    Alle drei zusammen: 27 von 40 Testfällen verbessert gegenüber der
    vorherigen (drei Startpunkte, kein Tausch-Zug) Fassung, ~10.000
    Kosteneinheiten Gesamtersparnis, im Schnitt 0,6 % in den verbesserten
    Fällen. Da jede Ergänzung nur eine weitere Kandidatenquelle für
    dieselbe Minimum-Auswahl ist, kann keine davon das Ergebnis
    verschlechtern - nur gleich gut oder besser machen.

    ABLATIONSSTUDIE (auf Nutzerfrage, ob bei jetzt fünf Startpunkten noch
    alle relevant sind): für jeden Startpunkt einzeln geprüft, wie oft und
    wie stark sich das Endergebnis verschlechtert, wenn er entfernt wird
    (40 Testfälle). Ergebnis sehr uneinheitlich:
    - "Hafen-bewusst gruppiert" (der ursprüngliche erste Startpunkt): 0
      von 40 Fällen betroffen, 0 Verlust - VOLLSTÄNDIG REDUNDANT
      geworden. Nachvollziehbar: sowohl die gesamtkosten-bewusste
      Gruppierung als auch die alternierende Neu-Gruppierung sind im
      Kern verfeinerte Versionen derselben Idee - kombiniert mit dem
      Tausch-Zug erreichen sie alles, was die einfache Version je fand.
      DESHALB ENTFERNT als eigener Ausgangspunkt für die
      Verbesserungssuche (spart einen vollen _improve_from_baseline-
      Aufruf, ~20 % Rechenzeit) - die Gruppierung selbst bleibt aber
      erhalten, da die alternierende Neu-Gruppierung weiterhin davon
      ausgeht.
    - "Blind gepackt": 16 von 40 Fällen betroffen, ~10.700
      Kosteneinheiten Verlust - klar UNVERZICHTBAR, mit Abstand der
      wichtigste Startpunkt. Strukturell fundamental anders als alle
      anderen vier (die alle irgendeine Form von Hafen-Gruppierung
      nutzen) - der Tausch-Zug kann diese strukturelle Lücke nicht
      schließen.
    - "monobeam_construction": nur 1 von 40 Fällen betroffen, ~340
      Kosteneinheiten Verlust - kleiner, aber echter Nutzen. BEHALTEN
      (auf Nutzerwunsch, trotz geringem Effekt).
    - "gesamtkosten-bewusst" und "alternierend neu gruppiert": 3 bzw. 6
      von 40 Fällen betroffen, ~850 bzw. ~1.300 Kosteneinheiten Verlust -
      beide behalten, tragen weiterhin spürbar bei.

    Lehre: nicht jede nachweislich hilfreiche Ergänzung bleibt hilfreich,
    wenn spätere Ergänzungen (hier: der Tausch-Zug) einen Teil ihres
    Wirkungsbereichs mit abdecken - ein Startpunkt sollte nach jeder
    größeren Suchverbesserung erneut auf seinen GRENZNUTZEN geprüft
    werden, nicht nur einmalig beim eigenen Einbau.

    EIN NEUNTER FUND, auf Nutzeranfrage nach weiteren Literatur-Ansätzen
    untersucht: Large Neighborhood Search (LNS) als finaler Politur-
    Schritt ergänzt (siehe _large_neighborhood_search) - bricht dabei die
    zuvor bewiesene Monotonie in der Beam-Breite (siehe README für die
    vollständige Herleitung und die Parallele zu GAs Monotonie-
    Untersuchung). Der ENSEMBLE-Teil VOR LNS (siehe _ensemble_best_result)
    bleibt weiterhin beweisbar monoton - nur die LNS-Politur danach (mit
    festem internem Zufalls-Seed, unabhängig von beam_width) verletzt die
    Garantie in ~10 % der Testfälle, jeweils um <0,5 % Kostendifferenz.

    EIN ZEHNTER FUND, auf Nutzerbeobachtung ("die Beam-Breite scheint
    nichts zu bringen") untersucht: bestätigt, kein Zufall. Selbst bei nur
    EINEM Startpunkt (also ohne die Auswahl zwischen mehreren Kandidaten,
    die beam_width sonst ermöglicht) und OHNE LNS zeigte sich in 40 % der
    Testfälle exakt kein Unterschied zwischen Breite 1 und 6 - der
    Tausch-Zug in _improve_from_baseline (siehe dort) prüft in Runde 1
    bereits erschöpfend jedes Packstück-Paar über jedes Container-Paar
    hinweg und findet dadurch meist schon das lokale Optimum vom
    jeweiligen Startpunkt aus; die "Zweitbesten" Kandidaten, die bei
    größerer Breite zusätzlich weiterverfolgt werden, führen in den
    Folgerunden (nur noch Verschieben/Abspalten) selten zu einem anderen
    Ziel. Dieselbe Art Befund wie bei den mehrfach redundant gewordenen
    Startlösungen (siehe oben) - nur diesmal betrifft es die Suchbreite
    selbst, nicht die Auswahl der Startpunkte. Der `beam_width`-Parameter
    bleibt aus Testbarkeitsgründen erhalten (mehrere Tests verifizieren
    z. B. die verbleibende, wenn auch geringe Monotonie-Eigenschaft
    direkt), wird von der App aber nicht mehr über einen Regler gesetzt -
    der Aufrufer (app.py) übergibt keinen Wert mehr, wodurch der neue,
    empirisch als schnellster ohne Qualitätseinbuße ermittelte Standard
    (beam_width=1) greift. Rechenzeit-Ersparnis bei der App-Obergrenze:
    ~502ms statt zuvor ~1,5-1,6s bei festem beam_width=2."""
    n = len(item_sizes)
    if n == 0:
        return []

    best_containers, _best_score = _ensemble_best_result(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width, max_rounds)

    # LNS-Politur als finaler Schritt (siehe _large_neighborhood_search
    # und README): zerstört mehrere Container gleichzeitig und baut sie
    # neu auf - kann Verbesserungen finden, die keiner der obigen
    # Startpunkte über reine Einzelzug-Suche erreicht. Läuft auf dem
    # bereits besten Ensemble-Ergebnis, nicht als weitere parallele
    # Ausgangslösung - kann das Ergebnis nur gleich gut oder besser
    # machen (behält das beste je gefundene Ergebnis).
    best_containers, _best_lns_score = _large_neighborhood_search(
        best_containers, item_sizes, item_regions, capacity, road_cost, sea_freight,
    )

    assignments = []
    for items in best_containers:
        port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
        assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def _fill_variance(containers, item_sizes, capacity):
    """Streuung (Varianz) der Container-Füllgrade - Hilfsfunktion für
    balance_containers (siehe dort)."""
    rates = [sum(item_sizes[i] for i in c) / capacity for c in containers if c]
    if not rates:
        return 0.0
    return float(np.var(rates))


def port_consolidation_frontier(containers, item_regions, item_sizes, road_cost, sea_freight):
    """Für jede Anzahl k=1..n_ports erlaubter Häfen: die günstigste
    Kombination von genau k Häfen (feste Packung, nur die Hafenwahl
    variiert je Container innerhalb dieser Teilmenge) - ergibt eine
    Kosten-vs-Konsolidierung-Kurve.

    Auf Nutzerwunsch ergänzt (Quality-Diversity-Feature, siehe README):
    statt abstrakter Verhaltens-Vielfalt (die als reine
    Optimierungsverbesserung nachweislich nicht half, siehe README) eine
    GESCHÄFTLICH motivierte Alternative - "was kostet mich Konsolidierung
    auf wenige Häfen/Spediteure?" ist eine reale Abwägung in der
    Logistikpraxis (einfachere Abwicklung, bessere Verhandlungsmacht bei
    einem Anbieter, ggf. Mengenrabatte), auch wenn sie nicht die
    Kosten-optimale Lösung ist.

    Nutzt die BEREITS FESTE Packung (keine Neu-Konstruktion) - nur welcher
    Hafen je Container gewählt wird, variiert. Bei bis zu 5 Häfen (App-
    Obergrenze) sind das höchstens 2^5=32 Teilmengen, je Teilmenge O(Container
    × Teilmengengröße) - empirisch ~3ms bei 100 Packstücken und 5 Häfen,
    vernachlässigbar."""
    n_ports = len(sea_freight)
    non_empty = [c for c in containers if c]
    frontier = {}
    for k in range(1, n_ports + 1):
        best_cost, best_subset = float("inf"), None
        for subset in combinations(range(n_ports), k):
            total = 0.0
            for c in non_empty:
                best_port_cost = float("inf")
                for port in subset:
                    cost = float(sea_freight[port])
                    for idx in c:
                        cost += road_cost[item_regions[idx]][port] * item_sizes[idx]
                    if cost < best_port_cost:
                        best_port_cost = cost
                total += best_port_cost
            if total < best_cost:
                best_cost, best_subset = total, subset
        frontier[k] = (best_cost, best_subset)
    return frontier


def balance_containers(base_containers, item_sizes, item_regions, capacity, road_cost, sea_freight,
                        max_rounds=10, cost_tolerance=0.05):
    """Lokale Tausch-Suche, die die STREUUNG der Container-Füllgrade
    minimiert (statt Kosten) - erlaubt dabei eine Kostenerhöhung bis zu
    `cost_tolerance` (Standard 5%) gegenüber der Kosten-optimalen
    Ausgangslösung, um echte Balance-Verbesserungen zuzulassen, statt bei
    der ersten Kostensteigerung abzubrechen.

    Auf Nutzerwunsch ergänzt (siehe README, Quality-Diversity-Feature):
    eine zweite geschäftlich motivierte Alternative neben der Häfen-
    Konsolidierung - gleichmäßigere Auslastung kann in der Praxis Risiken
    reduzieren (ein einzelner, fast voller Container als Nadelöhr) und
    Verladung/Handling planbarer machen. Empirisch verifiziert (40
    Testfälle): in 65 % der Fälle eine deutliche Verbesserung (>30 %
    weniger Streuung) bei im Schnitt nur ~1 % Kostenaufschlag (Maximum
    ~3 %) - in den übrigen Fällen war die Ausgangslösung bereits gut
    ausbalanciert, keine Verschlechterung."""
    containers = [list(c) for c in base_containers]
    base_cost = _state_score(containers, item_regions, item_sizes, road_cost, sea_freight)
    max_cost = base_cost * (1 + cost_tolerance)

    best_containers = [list(c) for c in containers]
    best_var = _fill_variance(containers, item_sizes, capacity)

    for _round in range(max_rounds):
        improved = False
        n_c = len(containers)
        container_used = [sum(item_sizes[i] for i in c) for c in containers]
        for c1 in range(n_c):
            for c2 in range(c1 + 1, n_c):
                if not containers[c1] or not containers[c2]:
                    continue
                # `for i1 in containers[c1]` / `for i2 in containers[c2]` freeze
                # their iterators to the container contents as of THIS (c1, c2)
                # pair's start. Accepting a swap reassigns `containers` (and
                # `container_used`), which those already-running iterators would
                # not see - continuing to try further (i1, i2) combinations
                # against the frozen items but the live, already-mutated
                # `containers[c1]`/`containers[c2]` corrupted the packing (an
                # item could be duplicated into the new container without ever
                # being removed from its old one). Fix: stop searching this
                # (c1, c2) pair the moment a swap is accepted, so every read of
                # `containers[c1]`/`containers[c2]` below is always consistent
                # with the still-active i1/i2 iterators.
                pair_improved = False
                for i1 in containers[c1]:
                    if pair_improved:
                        break
                    for i2 in containers[c2]:
                        s1, s2 = item_sizes[i1], item_sizes[i2]
                        new_used_c1 = container_used[c1] - s1 + s2
                        new_used_c2 = container_used[c2] - s2 + s1
                        if new_used_c1 > capacity + EPS or new_used_c2 > capacity + EPS:
                            continue
                        new_c1 = [i for i in containers[c1] if i != i1] + [i2]
                        new_c2 = [i for i in containers[c2] if i != i2] + [i1]
                        trial = [list(c) for c in containers]
                        trial[c1], trial[c2] = new_c1, new_c2
                        trial_var = _fill_variance(trial, item_sizes, capacity)
                        if trial_var >= best_var - 1e-9:
                            continue
                        trial_cost = _state_score(trial, item_regions, item_sizes, road_cost, sea_freight)
                        if trial_cost <= max_cost:
                            best_var = trial_var
                            best_containers = trial
                            containers = trial
                            container_used = [sum(item_sizes[i] for i in c) for c in containers]
                            improved = True
                            pair_improved = True
                            break
        if not improved:
            break

    assignments = []
    for items in best_containers:
        port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
        assignments.append({"items": items, "port": port, "cost": cost})
    return assignments
