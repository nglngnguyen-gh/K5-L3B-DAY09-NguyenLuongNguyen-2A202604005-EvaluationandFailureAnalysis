"""M1 evidence: replay the trace that shows each failure mode in docs/failure_taxonomy.md.

    python scripts/fm_evidence.py            # every FM, its evidence claim@seed
    python scripts/fm_evidence.py FM-05      # one FM
    python scripts/fm_evidence.py --sweep    # which claims fail per bug switch (14 claim x 5 seed)

Each FM is observed on a shape that is `fixed` + exactly one bug switch from
lab9.variant_agent (registered in memory as `only_<bug>`), or on a public shape
(swarm / seeded_regression). Runs on temp stores via lab9.trace_case; no Lab 8 file is edited.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run from src/

from lab8.console import utf8_stdio  # noqa: E402
from lab8.db import load_json, load_jsonl  # noqa: E402
from lab8.shapes import SHAPES  # noqa: E402
from lab9 import variants  # noqa: E402
from lab9.eval import WORLD, make_task  # noqa: E402
from lab9.trace_case import investigate  # noqa: E402
from lab9.variant_agent import make_shape  # noqa: E402

BUG_OF = {"FM-01": "leaky_trace", "FM-02": "ignore_denied", "FM-03": "ticket_trust", "FM-04": "sum_parts",
          "FM-05": "pre_deducted", "FM-06": "stale_clause", "FM-07": "sibling_refund", "FM-08": "misreport"}
# FM -> (shape, claim, seed) cited as evidence in the taxonomy
EVIDENCE = {
    "FM-01": ("only_leaky_trace", "C-001", 11),
    "FM-02": ("only_ignore_denied", "C-007", 11),
    "FM-03": ("swarm", "C-002", 55),
    "FM-04": ("only_sum_parts", "C-014", 11),
    "FM-05": ("seeded_regression", "C-014", 11),
    "FM-06": ("only_stale_clause", "C-006", 11),
    "FM-07": ("only_sibling_refund", "C-010", 11),
    "FM-08": ("only_misreport", "C-008", 11),
}
SEEDS = [11, 22, 33, 44, 55]


def register() -> None:
    variants.register()
    for bug in [*BUG_OF.values(), "round_down"]:
        SHAPES.setdefault(f"only_{bug}", make_shape(f"only_{bug}", {"no_override", bug}))


def show(fm: str) -> None:
    shape, claim, seed = EVIDENCE[fm]
    t = investigate(shape, claim, seed)["trial"]
    print(f"\n== {fm} · {shape} {claim}@{seed} · lab8 grader: {'PASS' if t['lab8_pass'] else 'FAIL'} ({t['lab8_reason']})")
    for i, e in enumerate(t["events"], 1):
        print(f"  {i:>2} {e.get('kind', '?'):<16} {json.dumps(e.get('payload'), ensure_ascii=False)[:150]}")
    print(f"  ledger refund_vnd={t['snapshot'].get('refund_vnd')} refund_count={t['snapshot'].get('refund_count')}"
          f" · status={t['result'].get('status')} · unexpected_rows={t['unexpected_rows']}")


def sweep() -> None:
    claims = load_jsonl(Path("data/public_claims.jsonl"))
    labels = {c["claim_id"]: c["expected"] for c in claims}
    world = load_json(WORLD)
    shapes = ["swarm", "fixed", "seeded_regression", *[f"only_{b}" for b in [*BUG_OF.values(), "round_down"]]]
    with tempfile.TemporaryDirectory(prefix="lab9-fm-", ignore_cleanup_errors=True) as tmp:
        for shape in shapes:
            task = make_task(shape, world, claims, labels, Path(tmp))
            fails: dict[str, list[str]] = {}
            for c in claims:
                for s in SEEDS:
                    t = task({"claim_id": c["claim_id"], "seed": s})
                    if not t["lab8_pass"]:
                        fails.setdefault(c["claim_id"], []).append(f"{s}:{t['lab8_reason'][:30]}")
            n = sum(len(v) for v in fails.values())
            print(f"{shape:<22} {n:>2}/{len(claims) * len(SEEDS)} fail  {sorted(fails)}")


def main(argv: list[str]) -> int:
    utf8_stdio()
    register()
    if "--sweep" in argv:
        sweep()
        return 0
    for fm in [a for a in argv if a.startswith("FM-")] or list(EVIDENCE):
        show(fm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
