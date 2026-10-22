"""Pytest suite for the delivery-deadline planner (Delhi -> Chennai, 10 t, 60/30/10)."""
import pytest
from ecoapp import plan_route, plan_route_deadline

ARGS = ("Delhi", "Chennai", 10.0, 0.6, 0.3, 0.1)
DNH = ["Delhi", "Nagpur", "Hyderabad", "Chennai"]


def modes(plan):
    return [m for *_, m in plan["legs"]]


def test_no_deadline_regression():
    p = plan_route(*ARGS)                       # untouched Round 1 planner
    assert p["path"] == DNH and modes(p) == ["Rail"] * 3
    assert round(p["time"], 1) == 84.4
    assert round(p["cost"]) == 26160 and round(p["co2"]) == 545


def test_loose_deadline_matches_no_deadline():
    base = plan_route(*ARGS)
    p, _ = plan_route_deadline(*ARGS, 100)
    assert p["path"] == base["path"] and modes(p) == modes(base)
    assert p["time"] == pytest.approx(base["time"])
    assert p["spare"] == pytest.approx(100 - base["time"])


def test_80h():
    p, _ = plan_route_deadline(*ARGS, 80)
    assert p["path"] == DNH and modes(p) == ["Rail", "Road", "Rail"]
    assert round(p["time"], 1) == 76.8 and round(p["cost"]) == 32660 and round(p["co2"]) == 870


def test_60h():
    p, _ = plan_route_deadline(*ARGS, 60)
    assert p["path"] == DNH and modes(p) == ["Road", "Air", "Road"]
    assert round(p["time"], 1) == 54.7 and round(p["cost"]) == 102000 and round(p["co2"]) == 4512


def test_20h_switches_path():
    p, _ = plan_route_deadline(*ARGS, 20)
    assert p["path"] == ["Delhi", "Kolkata", "Chennai"] and modes(p) == ["Air", "Air"]
    assert round(p["time"], 1) == 16.5 and round(p["cost"]) == 380400 and round(p["co2"]) == 19020


def test_16h_infeasible():
    p, fastest = plan_route_deadline(*ARGS, 16)
    assert p is None
    assert f"{fastest:.2f}" == "16.53"


def test_deadline_compared_unrounded():
    _, fastest = plan_route_deadline(*ARGS, 16)
    p, _ = plan_route_deadline(*ARGS, 16.52)    # just below the true fastest (16.5286)
    assert p is None
    p, _ = plan_route_deadline(*ARGS, fastest)  # exactly the fastest -> feasible
    assert p is not None and p["spare"] == pytest.approx(0, abs=1e-9)


def test_sweep_table():
    from ecoapp import deadline_sweep
    rows = {r["Deadline (h)"]: r for r in deadline_sweep(*ARGS)}
    assert rows[100]["Modes"] == "Rail/Rail/Rail"
    assert rows[20]["Modes"] == "Air/Air"
    assert all(r["Result"] == "Feasible" for r in rows.values())
    inf = deadline_sweep(*ARGS, deadlines=(16,))[0]
    assert inf["Result"] == "Infeasible (fastest 16.53 h)"