"""Regression test from docs/trace_case.md: seeded_regression C-002@11 (FM-03 ticket_trust).

First wrong step = event 3 `model_override` (ticket's 5 days over the DB's 2). The fixed shape
must never emit it and must leave the ledger empty.
"""

import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def kinds(trial):
    return [e.get("kind") for e in trial["events"]]


def test_lab9_trace_case_c002_seeded_regression_overrides_db():
    t = investigate("seeded_regression", "C-002", 11)["trial"]
    k = kinds(t)
    assert k.index("model_override") == 2                     # event 3: first wrong step
    assert t["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2   # DB was right
    assert t["events"][2]["payload"] == {"delay_days": 5}
    assert t["snapshot"]["refund_vnd"] == 20000 and not t["lab8_pass"]


def test_lab9_trace_case_c002_fixed_keeps_db_fact():
    t = investigate("fixed", "C-002", 11)["trial"]
    assert "model_override" not in kinds(t)
    assert t["snapshot"]["refund_vnd"] == 0 and t["result"]["status"] == "denied"
    assert t["lab8_pass"]
