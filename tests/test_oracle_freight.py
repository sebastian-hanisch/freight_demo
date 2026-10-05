"""
Orakel-Tests für die Seefracht-Konsolidierung: unabhängiger Rechenweg statt Selbstvergleich.

* Vollaufzählung aller Mengenpartitionen (Restricted-Growth-Strings) mit Hafenwahl je Block liefert das
  exakte Optimum kleiner Instanzen: keine Heuristik darf darunter liegen, Beam Search ist nie schlechter
  als Blind und Hafen-bewusst.
* Jede Zuweisung ist eine gültige Partition (Kapazität, jedes Packstück genau einmal), die gemeldeten
  Kosten stimmen mit einer Neuberechnung überein, Kennzahlen (See/Straße) ebenso.
* FFD-Packung gegen eine unabhängige Implementierung und die Garantie FFD <= 11/9 OPT + 6/9 (Dósa 2007)
  gegen das per Teilmengen-DP berechnete Bin-Packing-Optimum.
* Häfen-Konsolidierungskurve gegen Teilmengen-Enumeration.
"""

import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from freight_data import generate_freight_scenario  # noqa: E402
from freight_evaluation import evaluate_assignment  # noqa: E402
from freight_heuristics import (  # noqa: E402
    _ffd_pack,
    balance_containers,
    blind_packing_construction,
    flexible_beam_search_construction,
    port_aware_construction,
    port_consolidation_frontier,
)


def _partitions(n):
    def rec(i, a, m):
        if i == n:
            yield list(a)
            return
        for v in range(m + 1):
            a.append(v)
            yield from rec(i + 1, a, max(m, v + 1))
            a.pop()

    yield from rec(0, [], 0)


def _block_cost(block, sizes, regions, road, sea):
    return min(sea[k] + sum(road[regions[i]][k] * sizes[i] for i in block) for k in range(len(sea)))


def _brute_opt(sizes, regions, cap, road, sea):
    best = float("inf")
    cache = {}
    for a in _partitions(len(sizes)):
        blocks = [[] for _ in range(max(a) + 1)]
        for i, v in enumerate(a):
            blocks[v].append(i)
        total, ok = 0.0, True
        for b in blocks:
            if sum(sizes[i] for i in b) > cap + 1e-9:
                ok = False
                break
            key = tuple(b)
            if key not in cache:
                cache[key] = _block_cost(b, sizes, regions, road, sea)
            total += cache[key]
        if ok and total < best:
            best = total
    return best


def _min_bins(sizes, cap):
    n = len(sizes)
    sums = [0.0] * (1 << n)
    for m in range(1, 1 << n):
        lb = (m & -m).bit_length() - 1
        sums[m] = sums[m & (m - 1)] + sizes[lb]
    dp = [99] * (1 << n)
    dp[0] = 0
    for m in range(1, 1 << n):
        sub = m
        while sub:
            if sums[sub] <= cap + 1e-9 and dp[m ^ sub] + 1 < dp[m]:
                dp[m] = dp[m ^ sub] + 1
            sub = (sub - 1) & m
    return dp[(1 << n) - 1]


def _ffd_indep(sizes, cap):
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i], i))
    rem, content = [], []
    for i in order:
        for b in range(len(rem)):
            if sizes[i] <= rem[b] + 1e-9:
                rem[b] -= sizes[i]
                content[b].append(i)
                break
        else:
            rem.append(cap - sizes[i])
            content.append([i])
    return content


def _assert_valid(assign, sizes, regions, cap, road, sea):
    seen = []
    for a in assign:
        assert a["items"]
        seen += a["items"]
        assert sum(sizes[i] for i in a["items"]) <= cap + 1e-6
        assert abs(_block_cost(a["items"], sizes, regions, road, sea) - a["cost"]) < 1e-6
    assert sorted(seen) == list(range(len(sizes)))
    stats = evaluate_assignment(assign, np.array(sizes), np.array(regions), road, sea)
    sea_tot = sum(sea[a["port"]] for a in assign)
    road_tot = sum(road[regions[i]][a["port"]] * sizes[i] for a in assign for i in a["items"])
    assert abs(stats["sea_cost_total"] - sea_tot) < 1e-6
    assert abs(stats["road_cost_total"] - road_tot) < 1e-6


def _instances(count, seed=2024):
    rng = np.random.default_rng(seed)
    for _ in range(count):
        n = int(rng.integers(3, 8))
        cap = float(rng.choice([30.0, 50.0, 100.0]))
        _pc, _rc, road, sea, sizes, regions = generate_freight_scenario(
            n, int(rng.integers(2, 5)), int(rng.integers(2, 4)), int(rng.integers(0, 10**6)),
            sea_freight_base=float(rng.choice([50, 200, 800, 2000])),
            sea_freight_spread=float(rng.choice([0.0, 0.3, 0.8])), item_size_range=(5, min(30.0, cap)),
        )
        yield [float(x) for x in sizes], [int(x) for x in regions], cap, road, sea


def test_heuristics_valid_and_not_below_exact_optimum():
    for sizes, regions, cap, road, sea in _instances(40):
        opt = _brute_opt(sizes, regions, cap, road, sea)
        totals = {}
        for name, fn in (
            ("blind", blind_packing_construction),
            ("aware", port_aware_construction),
            ("beam", flexible_beam_search_construction),
        ):
            a = fn(np.array(sizes), np.array(regions), cap, road, sea)
            _assert_valid(a, sizes, regions, cap, road, sea)
            totals[name] = sum(x["cost"] for x in a)
            assert totals[name] >= opt - 1e-6
        assert totals["beam"] <= min(totals["blind"], totals["aware"]) + 1e-6


def test_ffd_matches_independent_implementation_and_dosa_bound():
    for sizes, _regions, cap, _road, _sea in _instances(40, seed=5):
        mine = _ffd_pack(list(range(len(sizes))), sizes, cap)
        ref = _ffd_indep(sizes, cap)
        assert sorted(map(sorted, mine)) == sorted(map(sorted, ref))
        assert len(ref) <= 11 / 9 * _min_bins(sizes, cap) + 6 / 9 + 1e-9


def test_port_frontier_matches_subset_enumeration_and_balance_stays_valid():
    for sizes, regions, cap, road, sea in _instances(25, seed=9):
        a = flexible_beam_search_construction(np.array(sizes), np.array(regions), cap, road, sea)
        cont = [x["items"] for x in a]
        fr = port_consolidation_frontier(cont, np.array(regions), np.array(sizes), road, sea)
        for k in range(1, len(sea) + 1):
            ref = min(
                sum(min(sea[p] + sum(road[regions[i]][p] * sizes[i] for i in b) for p in sub) for b in cont)
                for sub in itertools.combinations(range(len(sea)), k)
            )
            assert abs(ref - fr[k][0]) < 1e-6
        bal = balance_containers(cont, np.array(sizes), np.array(regions), cap, road, sea)
        _assert_valid(bal, sizes, regions, cap, road, sea)
        assert sum(x["cost"] for x in bal) <= sum(x["cost"] for x in a) * 1.05 + 1e-6
