"""DF-153 PVG-Cross-Entity-Revenue [CRUX-MK]
Cross-Entity Revenue Aggregation fuer Place Value Group.
Invariante: NIEMALS Inter-Entity-Transfer.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json

VALID_ENTITIES = frozenset({"heylou", "9dots", "lexvance"})

ENTITY_DESCRIPTIONS: Dict[str, str] = {
    "heylou":   "HeyLou Hotels",
    "9dots":    "9dots SaaS Platform",
    "lexvance": "LexVance Legal Services",
}


@dataclass
class EntityRevenue:
    """Single revenue + cost entry for exactly one PVG entity."""
    entity:  str
    revenue: float
    costs:   float
    date:    str
    source:  str = "manual"   # "manual" | "api"

    def __post_init__(self) -> None:
        if self.entity not in VALID_ENTITIES:
            raise ValueError(
                f"Unknown entity '{self.entity}'. "
                f"Allowed: {sorted(VALID_ENTITIES)}. "
                "NIEMALS Inter-Entity-Transfer."
            )
        if self.revenue < 0:
            raise ValueError(f"Revenue cannot be negative: {self.revenue}")
        if self.costs < 0:
            raise ValueError(f"Costs cannot be negative: {self.costs}")

    @property
    def pnl(self) -> float:
        return self.revenue - self.costs


def _empty_row() -> dict:
    return {"revenue": 0.0, "costs": 0.0, "pnl": 0.0}


def aggregate_revenue(entries: List[EntityRevenue]) -> dict:
    """
    Aggregate revenue, costs, PnL per entity and as total.

    Invariant: inter_entity_transfer is *always* False — entries are
    attributed only to their declared entity; cross-entity arithmetic
    never happens.

    Returns a dict keyed by entity name + 'total' + 'inter_entity_transfer'.
    """
    buckets: Dict[str, dict] = {e: _empty_row() for e in VALID_ENTITIES}

    for entry in entries:
        b = buckets[entry.entity]          # entity validated in __post_init__
        b["revenue"] += entry.revenue
        b["costs"]   += entry.costs
        b["pnl"]      = round(b["revenue"] - b["costs"], 2)

    for b in buckets.values():
        b["revenue"] = round(b["revenue"], 2)
        b["costs"]   = round(b["costs"],   2)
        b["pnl"]     = round(b["pnl"],     2)

    total = _empty_row()
    for b in buckets.values():
        total["revenue"] += b["revenue"]
        total["costs"]   += b["costs"]
    total["revenue"] = round(total["revenue"], 2)
    total["costs"]   = round(total["costs"],   2)
    total["pnl"]     = round(total["revenue"] - total["costs"], 2)

    result = dict(buckets)
    result["total"]                  = total
    result["inter_entity_transfer"]  = False   # hard invariant, never True

    return result


def generate_report(
    entries: List[EntityRevenue],
    report_dir: str = "reports",
    date_override: Optional[str] = None,
) -> str:
    """Persist a JSON report and return its path."""
    aggregated = aggregate_revenue(entries)
    date_str   = date_override or datetime.now().strftime("%Y-%m-%d")

    report = {
        "df":          "df-153",
        "mission":     "PVG Cross-Entity Revenue Aggregation",
        "date":        date_str,
        "entry_count": len(entries),
        "aggregates":  aggregated,
        "crux_mk":     True,
    }

    out_dir  = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"df-153-{date_str}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return str(out_path)
# [CRUX-MK]
