"""
Aggregiert die Container-Zuweisungen einer Heuristik zu Gesamtkennzahlen:
Gesamtkosten (See + Straße), Containeranzahl, Aufschlüsselung je Hafen.
"""


def evaluate_assignment(assignments, item_sizes, item_regions, road_cost, sea_freight):
    total_cost = sum(c["cost"] for c in assignments)
    n_containers = len(assignments)

    sea_cost_total = sum(float(sea_freight[c["port"]]) for c in assignments)
    road_cost_total = total_cost - sea_cost_total

    per_port_containers = {}
    for c in assignments:
        per_port_containers[c["port"]] = per_port_containers.get(c["port"], 0) + 1

    return {
        "total_cost": total_cost,
        "sea_cost_total": sea_cost_total,
        "road_cost_total": road_cost_total,
        "n_containers": n_containers,
        "per_port_containers": per_port_containers,
    }
