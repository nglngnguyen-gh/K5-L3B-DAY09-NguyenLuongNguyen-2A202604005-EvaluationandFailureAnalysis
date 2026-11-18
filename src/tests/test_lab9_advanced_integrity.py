"""M7: integrity_check against traps beyond lab9.traps (hidden-trap candidates), on hand-built reports."""
import copy

import pytest

pytestmark = pytest.mark.student

SEEDS = (1, 2, 3)
ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "slices": ["money_movement"] if i < 2 else [],
         "pass_rate": not (i == 3 and s == 1), "refund_amount_correct": True, "cost": 1.0}
        for i in range(4) for s in SEEDS]
SPEC = {"eval_set_version": "v2", "seeds": list(SEEDS), "pass_k": [1, 3],
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.8}},
                    {"id": "refund_amount_correct", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.9, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.95, "blocking": True}]}


def report(rows=None, **over):
    from lab9.eval import aggregate
    rows = copy.deepcopy(ROWS if rows is None else rows)
    rep = {"run_id": "t", "manifest": {"eval_set_sha": "x", "items": 4, "seeds": list(SEEDS)},
           "rows": rows, "evaluator_failures": [],
           "metrics": aggregate(rows, ["pass_rate", "refund_amount_correct"], k_values=[1, 3])}
    rep.update(over)
    return rep


def check(pr, spec=SPEC, base_spec=None):
    from lab9 import gate
    return gate.integrity_check(pr, report(), spec, base_spec)


def test_advanced_honest_report_is_clean():
    assert check(report()) == []
    assert check(report(), SPEC, SPEC) == []


def test_advanced_duplicate_row_replacing_a_failing_one():
    rows = [r for r in ROWS if not (r["item_id"] == "E-003" and r["seed"] == 1)]
    rows.append(dict(ROWS[0]))                       # same row count, one failing row swapped for a copy
    assert any("duplicated" in p for p in check(report(rows)))


def test_advanced_evaluator_failures_on_a_green_run():
    assert any("evaluator failure" in p for p in check(report(evaluator_failures=["E-001@1:pass_rate:boom"])))


def test_advanced_hand_edited_summary():
    rep = report()
    rep["metrics"]["pass_rate"] = 1.0
    assert any("summary edited" in p for p in check(rep))


def test_advanced_item_relabelled_out_of_a_slice():
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-001":
            r["slices"] = []
    assert any("slice tags" in p for p in check(report(rows)))


def test_advanced_inf_metric_and_non_bool_score():
    assert check(report(metrics={**report()["metrics"], "pass_rate": float("inf")}))
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = float("nan")
    assert any("no boolean score" in p for p in check(report(rows)))


@pytest.mark.parametrize("edit", [
    lambda s: s["metrics"][1].__setitem__("blocking", False),
    lambda s: s["metrics"][1]["threshold"].pop("no_significant_drop"),
    lambda s: s["metrics"].pop(0),
    lambda s: s["slices"].clear(),
    lambda s: s["slices"][0].__setitem__("min", 0.5),
    lambda s: s.__setitem__("seeds", [1, 2]),
])
def test_advanced_ratchet_rejects_looser_spec(edit):
    loose = copy.deepcopy(SPEC)
    edit(loose)
    assert check(report(), loose, SPEC)


def test_advanced_ratchet_allows_stricter_or_new_version():
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.9
    strict["slices"].append({"name": "adversarial", "metric": "pass_rate", "min": 0.95, "blocking": True})
    assert check(report(), strict, SPEC) == []
    new_version = dict(copy.deepcopy(SPEC), eval_set_version="v3", slices=[])
    assert check(report(), new_version, SPEC) == []
