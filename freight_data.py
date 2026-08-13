"""
Erzeugt ein Seefracht-Konsolidierungs-Szenario: Häfen und Zielregionen mit
2D-Koordinaten, eine Straßenkosten-Matrix (Region × Hafen, proportional zur
Distanz), leicht variierende Seefrachtkosten je Hafen, sowie einzelne
Packstücke mit Größe und Zielregion.
"""

import numpy as np

from freight_constants import DEFAULT_ROAD_COST_PER_UNIT, DEFAULT_SEA_FREIGHT_BASE, DEFAULT_SEA_FREIGHT_SPREAD


def generate_freight_scenario(
    n_items, n_regions, n_ports, seed,
    sea_freight_base=DEFAULT_SEA_FREIGHT_BASE, sea_freight_spread=DEFAULT_SEA_FREIGHT_SPREAD,
    item_size_range=(5, 30),
):
    """Erzeugt ein vollständiges Szenario. Straßenkosten sind proportional zur
    euklidischen Distanz zwischen Region und Hafen (realistischer Proxy für
    Lkw-Transportkosten) - unterschiedliche Häfen sind für dieselbe Region
    unterschiedlich teuer, und umgekehrt ist ein Hafen für unterschiedliche
    Regionen unterschiedlich attraktiv. Genau diese Variation macht die
    Gruppierungsentscheidung (welche Packstücke teilen sich einen Container)
    bedeutsam.

    sea_freight_base ist bewusst als Parameter (nicht nur als Konstante)
    verfügbar: das Verhältnis von Seefracht zu Straßenkosten bestimmt, ob
    sich hafen-bewusste Gruppierung überhaupt lohnt (siehe README - bei
    hoher Seefracht relativ zu den Straßenkosten kann die naive Methode
    tatsächlich günstiger sein, weil sie mit weniger Containern auskommt).

    Gibt (port_coords, region_coords, road_cost, sea_freight, item_sizes,
    item_regions) zurück. road_cost[r][k] = € pro Größeneinheit von Region r
    über Hafen k. sea_freight[k] = € je genutztem Container über Hafen k.
    """
    rng = np.random.default_rng(seed)

    port_coords = rng.uniform(5, 95, size=(n_ports, 2))
    region_coords = rng.uniform(5, 95, size=(n_regions, 2))

    road_cost = np.zeros((n_regions, n_ports))
    for r in range(n_regions):
        for k in range(n_ports):
            dist = float(np.linalg.norm(region_coords[r] - port_coords[k]))
            road_cost[r][k] = dist * DEFAULT_ROAD_COST_PER_UNIT / 10.0

    sea_freight = sea_freight_base * (
        1.0 + rng.uniform(-sea_freight_spread, sea_freight_spread, size=n_ports)
    )

    lo, hi = item_size_range
    item_sizes = rng.uniform(lo, hi, size=n_items).round(1)
    item_regions = rng.integers(0, n_regions, size=n_items)

    return port_coords, region_coords, road_cost, sea_freight, item_sizes, item_regions
