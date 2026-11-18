"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    graded = _graded_ids(spec)
    problems += [f"PR {p}" for p in _report_problems(pr, graded)]
    problems += [f"BASELINE {p}" for p in _report_problems(base, graded)]

    # Same population as the baseline: same manifest, same (item, seed) pairs, same slice tags.
    pm, bm = pr.get("manifest") or {}, base.get("manifest") or {}
    for key in ("items", "seeds", "eval_set"):
        if key in bm and pm.get(key) != bm.get(key):
            problems.append(f"manifest {key} {pm.get(key)!r} != baseline {bm.get(key)!r}")
    pr_pairs, base_pairs = _pairs(pr), _pairs(base)
    if pr_pairs != base_pairs:
        miss, extra = sorted(base_pairs - pr_pairs), sorted(pr_pairs - base_pairs)
        problems.append(f"(item, seed) set differs from baseline: missing {len(miss)} {miss[:3]}, "
                        f"extra {len(extra)} {extra[:3]}")
    base_tags = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows") or []}
    relabelled = sorted({r.get("item_id") for r in pr.get("rows") or []
                         if r.get("item_id") in base_tags and sorted(r.get("slices") or []) != base_tags[r.get("item_id")]})
    if relabelled:
        problems.append(f"slice tags differ from baseline on {len(relabelled)} item(s): {relabelled[:5]}")

    if base_spec is not None:
        problems += [f"RATCHET {p}" for p in _ratchet(spec, base_spec)]
    return problems


def _graded_ids(spec: dict) -> list[str]:
    """Spec metrics scored per row by a grader (the ones a crash can silently drop)."""
    from lab9.graders import GRADERS
    return [m["id"] for m in spec.get("metrics") or [] if m["id"] in GRADERS]


def _pairs(rep: dict) -> set[tuple]:
    return {(r.get("item_id"), r.get("seed")) for r in rep.get("rows") or []}


def _bad_number(v) -> bool:
    return isinstance(v, float) and (math.isnan(v) or math.isinf(v))


def _report_problems(rep: dict, graded: list[str]) -> list[str]:
    """Structural checks a report must pass on its own, before any comparison."""
    out: list[str] = []
    rows = rep.get("rows") or []
    man = rep.get("manifest") or {}
    bad = sorted(k for k, v in (rep.get("metrics") or {}).items() if _bad_number(v))
    if bad:
        out.append(f"metric value is NaN/inf: {bad}")
    if not rows:
        out.append("report has no rows")
    want = int(man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        out.append(f"{len(rows)} rows != {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want}")
    pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
    dup = sorted({p for p in pairs if pairs.count(p) > 1})
    if dup:
        out.append(f"duplicated (item, seed) rows: {dup[:3]}")
    off_seed = sorted({r.get("seed") for r in rows} - set(man.get("seeds") or []))
    if off_seed:
        out.append(f"rows on seeds not in the manifest: {off_seed}")
    if rep.get("evaluator_failures"):
        out.append(f"{len(rep['evaluator_failures'])} evaluator failure(s), first: {rep['evaluator_failures'][0][:80]}")
    for m in graded:
        holes = [f"{r.get('item_id')}@{r.get('seed')}" for r in rows
                 if m not in r or r[m] is None or not isinstance(r[m], bool)]
        if holes:
            out.append(f"{m}: {len(holes)} row(s) with no boolean score (crashed grader?), e.g. {holes[:3]}")
    # Metrics must be what the rows say: catches a hand-edited summary over honest rows.
    if rows and not any(p.startswith(m + ":") for p in out for m in graded):
        from lab9.eval import aggregate
        ids = [m for m in graded if all(m in r for r in rows)]
        k_values = [int(k.split("_")[-1]) for k in (rep.get("metrics") or {}) if k.startswith("pass_hat_")]
        try:
            again = aggregate(rows, ids, k_values=k_values)
        except (KeyError, TypeError, ValueError):
            again = None
        if again is not None:
            for k, v in (rep.get("metrics") or {}).items():
                if k in again and not _bad_number(v) and not _close(v, again[k]):
                    out.append(f"metric {k}={v} but rows give {again[k]} (summary edited?)")
    return out


def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6
    return a == b


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Same eval-set version => thresholds may only get stricter. A new version restarts them."""
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []
    out: list[str] = []
    if not set(base_spec.get("seeds") or []) <= set(spec.get("seeds") or []):
        out.append(f"seeds {spec.get('seeds')} drop baseline seeds {base_spec.get('seeds')}")
    for key in ("eval_set", "labels"):
        if key in base_spec and spec.get(key) != base_spec.get(key):
            out.append(f"{key} changed on the same eval-set version")
    if (spec.get("bootstrap") or {}).get("confidence", 0.95) < (base_spec.get("bootstrap") or {}).get("confidence", 0.95):
        out.append("bootstrap confidence lowered")
    new_m = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        out += _looser(f"metric {m['id']}", m, m.get("threshold") or {}, new_m.get(m["id"]),
                       (new_m.get(m["id"]) or {}).get("threshold") or {})
    new_s = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        key = (s["name"], s["metric"])
        out += _looser(f"slice {key[0]}/{key[1]}", s, s, new_s.get(key), new_s.get(key) or {})
    return out


def _looser(label: str, old: dict, old_th: dict, new: dict | None, new_th: dict) -> list[str]:
    if new is None:
        return [f"{label} removed"]
    out = []
    if old.get("blocking") and not new.get("blocking"):
        out.append(f"{label} no longer blocking")
    if "min" in old_th and ("min" not in new_th or new_th["min"] < old_th["min"]):
        out.append(f"{label} min {old_th['min']} -> {new_th.get('min')}")
    for k in ("max", "max_increase"):
        if k in old_th and (k not in new_th or new_th[k] > old_th[k]):
            out.append(f"{label} {k} {old_th[k]} -> {new_th.get(k)}")
    if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
        out.append(f"{label} dropped no_significant_drop")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note, val = "ok", "", None
        if not a:
            # An empty slice cannot vouch for anything: relabelled or dropped items must not pass.
            verdict, note = "missing", "no PR rows in slice"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027),
                                                       confidence=bs.get("confidence", 0.95))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
                else:
                    verdict, note = "missing", "no items shared with baseline"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
        lines.append(f"  {sid:<34} {val!s:<8} n={len(a):<3} {json.dumps(th):<36} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
