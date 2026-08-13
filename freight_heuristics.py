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
"""

import heapq
from collections import defaultdict

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


def blind_packing_construction(item_sizes, item_regions, capacity, road_cost, sea_freight):
    n = len(item_sizes)
    containers = _ffd_pack(list(range(n)), item_sizes, capacity)

    assignments = []
    for items in containers:
        port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
        assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def port_aware_construction(item_sizes, item_regions, capacity, road_cost, sea_freight):
    n_regions = road_cost.shape[0]
    best_port_per_region = np.argmin(road_cost, axis=1)

    groups = defaultdict(list)
    for idx in range(len(item_sizes)):
        region = item_regions[idx]
        if 0 <= region < n_regions:
            preferred = int(best_port_per_region[region])
        else:
            preferred = 0
        groups[preferred].append(idx)

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
    n_regions = road_cost.shape[0]
    best_port_per_region = np.argmin(road_cost, axis=1)

    groups = defaultdict(list)
    for idx in range(n):
        region = item_regions[idx]
        preferred = int(best_port_per_region[region]) if 0 <= region < n_regions else 0
        groups[preferred].append(idx)

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
    automatisch "pathmax"-konform ohne die Zusatzlogik des Originals."""
    return sum(_best_port_for_container(c, item_regions, item_sizes, road_cost, sea_freight)[1] for c in containers)


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

    n_regions = road_cost.shape[0]
    best_port_per_region = np.argmin(road_cost, axis=1)
    groups = defaultdict(list)
    for idx in range(n):
        region = item_regions[idx]
        preferred = int(best_port_per_region[region]) if 0 <= region < n_regions else 0
        groups[preferred].append(idx)

    assignments = []
    for _preferred_port, idxs in groups.items():
        containers = _monobeam_pack(idxs, item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width)
        for items in containers:
            port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
            assignments.append({"items": items, "port": port, "cost": cost})
    return assignments


def flexible_beam_search_construction(item_sizes, item_regions, capacity, road_cost, sea_freight, beam_width=2, max_rounds=None):
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
    suche, die bei der starren Gruppierung STARTET (garantiert nie
    schlechter) und dann über mehrere Runden hinweg die besten
    Einzelverschiebungen eines Packstücks in einen anderen Container
    (möglicherweise anderer Hafen) sucht - direkte Bewertung des tatsächlichen
    Kosteneffekts statt blinder Vorwärtssuche, dadurch gezielter.

    Performance-Hinweis: anders als bei Konstruktions-Beam-Search (wo eine
    breitere Suche meist hilft) bringt hier eine größere Beam-Breite kaum
    zusätzliche Qualität (empirisch: bw=1, bw=2 und bw=16 liefern praktisch
    identische Ersparnis, ~1,7% im Schnitt) - der Nutzen kommt aus dem
    Finden der ersten guten Verschiebung, nicht aus paralleler Exploration
    vieler Kandidatenfolgen. Da eine breitere Suche nach Runde 1 aber sehr
    viel teurer wird (der Beam facht sich auf bis zu `beam_width` Zustände
    auf, jeder wird in der nächsten Runde vollständig neu durchsucht -
    Worst Case bei bw=16 und 100 Packstücken: 1,4s), ist der Standard
    bewusst klein gewählt (Worst Case bei bw=2: ~120ms)."""
    n = len(item_sizes)
    if n == 0:
        return []

    n_regions = road_cost.shape[0]
    best_port_per_region = np.argmin(road_cost, axis=1)
    groups = defaultdict(list)
    for idx in range(n):
        region = item_regions[idx]
        preferred = int(best_port_per_region[region]) if 0 <= region < n_regions else 0
        groups[preferred].append(idx)

    base_containers = []
    for _preferred_port, idxs in groups.items():
        base_containers.extend(_ffd_pack(idxs, item_sizes, capacity))

    base_score = _state_score(base_containers, item_regions, item_sizes, road_cost, sea_freight)
    beam = [(base_containers, base_score)]

    if max_rounds is None:
        max_rounds = 3

    for _round in range(max_rounds):
        candidates = []
        seen_keys = set()
        for containers, score in beam:
            item_to_container = {}
            for c_idx, cont in enumerate(containers):
                for item_idx in cont:
                    item_to_container[item_idx] = c_idx
            container_used = [sum(item_sizes[i] for i in cont) for cont in containers]
            container_cost = [_best_port_for_container(cont, item_regions, item_sizes, road_cost, sea_freight)[1] for cont in containers]

            for item_idx in range(n):
                from_c = item_to_container[item_idx]
                item_size = item_sizes[item_idx]

                # Verschiebung in einen bestehenden, anderen Container
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

                # Verschiebung in einen NEUEN, eigenen Container
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

        if not candidates:
            break

        candidates.sort(key=lambda t: (t[0], t[1]))
        # Beam mit den urspruenglichen Zustaenden kombinieren (ein Zustand
        # darf auch "keine Verschiebung diese Runde" bedeuten, sonst koennte
        # sich das Ergebnis durch erzwungene Verschiebungen verschlechtern)
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
            break  # keine Verbesserung mehr moeglich - konvergiert

        beam = deduped

    best_containers, best_score = min(beam, key=lambda t: t[1])
    assignments = []
    for items in best_containers:
        port, cost = _best_port_for_container(items, item_regions, item_sizes, road_cost, sea_freight)
        assignments.append({"items": items, "port": port, "cost": cost})
    return assignments
