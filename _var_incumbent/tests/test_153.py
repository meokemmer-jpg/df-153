import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
# NOTE: `from 153 import` is a Python syntax error (numeric module name).
# importlib.import_module("153") is the only valid way to load it.
import importlib
import json
import os
import tempfile
import pytest

_m = importlib.import_module("153")
EntityRevenue    = _m.EntityRevenue
aggregate_revenue = _m.aggregate_revenue
generate_report  = _m.generate_report
VALID_ENTITIES   = _m.VALID_ENTITIES


# ── EntityRevenue construction ────────────────────────────────────────────────

def test_valid_entities_exist():
    assert {"heylou", "9dots", "lexvance"} == set(VALID_ENTITIES)


def test_heylou_pnl():
    e = EntityRevenue("heylou", 50_000.0, 30_000.0, "2026-06-09")
    assert e.pnl == 20_000.0


def test_9dots_pnl():
    e = EntityRevenue("9dots", 20_000.0, 12_000.0, "2026-06-09")
    assert e.pnl == 8_000.0


def test_lexvance_pnl():
    e = EntityRevenue("lexvance", 15_000.0, 9_000.0, "2026-06-09")
    assert e.pnl == 6_000.0


def test_invalid_entity_raises():
    with pytest.raises(ValueError, match="Unknown entity"):
        EntityRevenue("unknown_corp", 1_000.0, 500.0, "2026-06-09")


def test_inter_entity_name_rejected():
    """Explicit attempt to name a row 'inter_entity_transfer' must fail."""
    with pytest.raises(ValueError, match="Unknown entity"):
        EntityRevenue("inter_entity_transfer", 5_000.0, 0.0, "2026-06-09")


def test_negative_revenue_raises():
    with pytest.raises(ValueError, match="Revenue cannot be negative"):
        EntityRevenue("heylou", -1.0, 0.0, "2026-06-09")


def test_negative_costs_raises():
    with pytest.raises(ValueError, match="Costs cannot be negative"):
        EntityRevenue("9dots", 1_000.0, -0.01, "2026-06-09")


# ── aggregate_revenue ─────────────────────────────────────────────────────────

def test_aggregate_empty():
    r = aggregate_revenue([])
    assert r["total"]["revenue"] == 0.0
    assert r["total"]["pnl"]     == 0.0
    assert r["inter_entity_transfer"] is False


def test_aggregate_single_heylou():
    entries = [EntityRevenue("heylou", 10_000.0, 7_000.0, "2026-06-09")]
    r = aggregate_revenue(entries)
    assert r["heylou"]["revenue"] == 10_000.0
    assert r["heylou"]["costs"]   == 7_000.0
    assert r["heylou"]["pnl"]     == 3_000.0
    # other entities untouched
    assert r["9dots"]["revenue"]    == 0.0
    assert r["lexvance"]["revenue"] == 0.0


def test_aggregate_all_entities():
    entries = [
        EntityRevenue("heylou",   50_000.0, 30_000.0, "2026-06-09"),
        EntityRevenue("9dots",    20_000.0, 10_000.0, "2026-06-09"),
        EntityRevenue("lexvance", 15_000.0,  8_000.0, "2026-06-09"),
    ]
    r = aggregate_revenue(entries)
    assert r["total"]["revenue"] == 85_000.0
    assert r["total"]["costs"]   == 48_000.0
    assert r["total"]["pnl"]     == 37_000.0


def test_inter_entity_transfer_always_false():
    """Hard invariant: field must be False regardless of input."""
    entries = [EntityRevenue("heylou", 1.0, 1.0, "2026-06-09")]
    r = aggregate_revenue(entries)
    assert r["inter_entity_transfer"] is False


def test_entities_isolated_from_each_other():
    """High heylou revenue must NOT appear in 9dots or lexvance."""
    entries = [EntityRevenue("heylou", 999_999.0, 1.0, "2026-06-09")]
    r = aggregate_revenue(entries)
    assert r["9dots"]["revenue"]    == 0.0
    assert r["lexvance"]["revenue"] == 0.0
    assert r["9dots"]["pnl"]        == 0.0


def test_multiple_entries_same_entity():
    entries = [
        EntityRevenue("9dots", 10_000.0, 4_000.0, "2026-06-01"),
        EntityRevenue("9dots", 15_000.0, 6_000.0, "2026-06-09"),
    ]
    r = aggregate_revenue(entries)
    assert r["9dots"]["revenue"] == 25_000.0
    assert r["9dots"]["pnl"]     == 15_000.0


# ── generate_report ───────────────────────────────────────────────────────────

def test_generate_report_creates_file():
    entries = [
        EntityRevenue("heylou",   50_000.0, 30_000.0, "2026-06-09"),
        EntityRevenue("9dots",    20_000.0, 10_000.0, "2026-06-09"),
        EntityRevenue("lexvance", 15_000.0,  8_000.0, "2026-06-09"),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_report(entries, report_dir=tmpdir, date_override="2026-06-09")
        assert os.path.exists(path)
        assert path.endswith("df-153-2026-06-09.json")

        with open(path, encoding="utf-8") as f:
            rep = json.load(f)

        assert rep["df"]          == "df-153"
        assert rep["date"]        == "2026-06-09"
        assert rep["entry_count"] == 3
        assert rep["crux_mk"]     is True
        agg = rep["aggregates"]
        assert agg["inter_entity_transfer"] is False
        assert agg["total"]["revenue"]      == 85_000.0
        assert agg["total"]["pnl"]          == 37_000.0


def test_generate_report_empty_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generate_report([], report_dir=tmpdir, date_override="2026-01-01")
        with open(path, encoding="utf-8") as f:
            rep = json.load(f)
        assert rep["entry_count"]                       == 0
        assert rep["aggregates"]["total"]["revenue"]    == 0.0
        assert rep["aggregates"]["inter_entity_transfer"] is False

