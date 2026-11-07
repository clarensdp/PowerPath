"""Opt-in illustrative starter scenario (v30.8.2).

When a user ticks "start with an illustrative working scenario" while creating a project, PowerPath creates one
underwriting scenario from the unchanged engine defaults, changing only the building list so that IT MW sums
exactly to the project's stated target. Without this, every new project needed manual building edits before any
financial step would run. Nothing else is assumed: rents, costs, debt terms and timing are the engine defaults and
are labelled illustrative. Never applied without the explicit opt-in.
"""

import copy
import math

STARTER_NAME = "Illustrative working scenario"
_MAX_BUILDINGS = 10  # keeps the last building's power month inside the default 120-month horizon
_TEMPLATE_MW = 50
_STAGGER_MONTHS = 9


def sized_buildings(template: list[dict], target_mw: float) -> list[dict]:
    if not template or target_mw <= 0:
        raise ValueError("A positive target MW and a building template are required")
    n = min(_MAX_BUILDINGS, max(1, math.ceil(target_mw / _TEMPLATE_MW)))
    each = round(target_mw / n, 6)
    first = template[0]
    out = []
    for i in range(n):
        b = copy.deepcopy(template[i] if i < len(template) else first)
        offset = _STAGGER_MONTHS * i
        b["name"] = f"Building {chr(65 + i)}"
        b["itMW"] = each
        b["constructionStart"] = first["constructionStart"] + offset
        b["powerMonth"] = first["powerMonth"] + offset
        b["leaseMonth"] = first["leaseMonth"] + offset
        out.append(b)
    out[-1]["itMW"] = round(target_mw - each * (n - 1), 6)  # exact total despite rounding
    return out


def starter_config(defaults_project: dict, target_mw: float) -> dict:
    config = copy.deepcopy(defaults_project)
    config["buildings"] = sized_buildings(defaults_project["buildings"], target_mw)
    config["starterScenario"] = {
        "kind": "illustrative_defaults",
        "sized_to_target_mw": target_mw,
        "note": "Engine defaults with building IT MW sized to the project target. Not a site, utility, lease or financing assumption set.",
    }
    return config
