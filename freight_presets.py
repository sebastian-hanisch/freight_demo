"""
Ein-Klick-Beispielszenarien und Permalink-Logik - dasselbe SETTING_SPECS-
Muster wie in den anderen drei Demos, von Anfang an mit NaN/Bounds-Schutz.
"""

import math
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

from freight_constants import (
    DEFAULT_CONTAINER_CAPACITY,
    DEFAULT_N_ITEMS,
    DEFAULT_N_PORTS,
    DEFAULT_N_REGIONS,
    DEFAULT_SEA_FREIGHT_BASE,
    DEFAULT_SEA_FREIGHT_SPREAD,
)


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "n_items_slider": SettingSpec("n_items", int, DEFAULT_N_ITEMS, 10, 100),
    "n_regions_slider": SettingSpec("n_regions", int, DEFAULT_N_REGIONS, 3, 8),
    "n_ports_slider": SettingSpec("n_ports", int, DEFAULT_N_PORTS, 2, 5),
    "capacity_slider": SettingSpec("cap", float, DEFAULT_CONTAINER_CAPACITY, 30.0, 300.0),
    "sea_freight_slider": SettingSpec("sea", float, DEFAULT_SEA_FREIGHT_BASE, 200.0, 4000.0),
    "sea_spread_slider": SettingSpec("spread", float, DEFAULT_SEA_FREIGHT_SPREAD, 0.0, 0.8),
    "beam_width_slider": SettingSpec("beam", int, 8, 1, 32),
    "seed_input": SettingSpec("seed", int, 42, 0, 2_000_000_000),
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def apply_preset(n_items_val, n_regions_val, n_ports_val, capacity_val, sea_freight_val, sea_spread_val, seed_val, beam_width_val=8):
    st.session_state["n_items_slider"] = n_items_val
    st.session_state["n_regions_slider"] = n_regions_val
    st.session_state["n_ports_slider"] = n_ports_val
    st.session_state["capacity_slider"] = capacity_val
    st.session_state["sea_freight_slider"] = sea_freight_val
    st.session_state["sea_spread_slider"] = sea_spread_val
    st.session_state["beam_width_slider"] = beam_width_val
    st.session_state["seed_input"] = seed_val
    st.session_state["force_regen"] = True


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    applied_any = False
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                st.session_state[state_key] = value
                applied_any = True
            except (ValueError, TypeError):
                pass
    if applied_any:
        st.session_state["force_regen"] = True
    st.session_state["permalink_loaded"] = True


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def sync_query_params(n_items, n_regions, n_ports, capacity, sea_freight, sea_spread, seed, beam_width):
    try:
        st.query_params["n_items"] = str(n_items)
        st.query_params["n_regions"] = str(n_regions)
        st.query_params["n_ports"] = str(n_ports)
        st.query_params["cap"] = str(capacity)
        st.query_params["sea"] = str(sea_freight)
        st.query_params["spread"] = str(sea_spread)
        st.query_params["beam"] = str(beam_width)
        st.query_params["seed"] = str(int(seed))
    except Exception:
        pass
