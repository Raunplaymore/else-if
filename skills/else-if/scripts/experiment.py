#!/usr/bin/env python3
"""Validate an experiment plan and compare submitted paired measurements; no writes or execution."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

VERSION = "next-experiment/1"
MAX_BYTES = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, where):
    require(isinstance(value, dict), f"{where}: object required")
    require(set(value) == set(names.split()), f"{where}: expected fields: {names}")


def text(value, where):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 10000,
            f"{where}: nonempty text (max 10000 characters) required")


def array(value, where, minimum=0, maximum=100):
    require(isinstance(value, list) and minimum <= len(value) <= maximum,
            f"{where}: expected {minimum}..{maximum} items")


def strings(value, where, minimum=0, maximum=100):
    array(value, where, minimum, maximum)
    for item in value:
        text(item, where)
    require(len(value) == len(set(value)), f"{where}: duplicate entries")


def number(value, where):
    require(type(value) in (int, float) and abs(value) <= 1e12 and math.isfinite(value),
            f"{where}: finite number within ±1e12 required")


def unique_ids(records, where):
    ids = [r["id"] for r in records]
    require(len(ids) == len(set(ids)), f"{where}: duplicate IDs")
    return set(ids)


def fingerprint(plan):
    encoded = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_plan(plan):
    fields(plan, "schema_version id project_id data_origin problem goal scope sources candidates selected controls budget expected_pairs criteria", "plan")
    require(plan["schema_version"] == VERSION, "plan: unsupported schema version")
    require(plan["data_origin"] in ("synthetic", "project"), "plan: invalid data_origin")
    for key in ("id", "project_id", "problem", "goal", "scope"):
        text(plan[key], key)
    strings(plan["controls"], "controls", 1)
    strings(plan["expected_pairs"], "expected_pairs", 1, 100)
    fields(plan["budget"], "minutes model_calls extra_cost currency", "budget")
    for key in ("minutes", "model_calls", "extra_cost"):
        number(plan["budget"][key], key)
        require(plan["budget"][key] >= 0, f"budget.{key}: must be nonnegative")
    require(plan["budget"]["minutes"] > 0, "budget.minutes: must be positive")
    require(type(plan["budget"]["model_calls"]) is int, "budget.model_calls: integer required")
    text(plan["budget"]["currency"], "currency")
    array(plan["sources"], "sources", 0, 50)
    for source in plan["sources"]:
        fields(source, "id locator excerpt status", "source")
        for key in ("id", "locator", "excerpt"):
            text(source[key], f"source.{key}")
        require(source["status"] in ("checked", "user_report", "unverified", "synthetic"), "source: invalid status")
    source_ids = unique_ids(plan["sources"], "sources")
    array(plan["candidates"], "candidates", 1, 3)
    warnings = []
    for candidate in plan["candidates"]:
        fields(candidate, "id mode hypothesis source_refs change procedure alternative uncertainty stop rollback", "candidate")
        for key in ("id", "hypothesis", "change", "procedure", "alternative", "uncertainty", "stop", "rollback"):
            text(candidate[key], f"candidate.{key}")
        require(candidate["mode"] in ("step_up", "breakthrough"), "candidate: invalid mode")
        strings(candidate["source_refs"], "source_refs")
        require(set(candidate["source_refs"]) <= source_ids, "candidate: unknown source reference")
        if not candidate["source_refs"]:
            warnings.append(f"{candidate['id']}: no source; hypothesis only")
    candidate_ids = unique_ids(plan["candidates"], "candidates")
    require(isinstance(plan["selected"], str) and plan["selected"] in candidate_ids, "selected: unknown candidate")
    array(plan["criteria"], "criteria", 1, 5)
    for criterion in plan["criteria"]:
        fields(criterion, "id label unit direction role minimum_delta", "criterion")
        for key in ("id", "label", "unit"):
            text(criterion[key], key)
        require(criterion["direction"] in ("lower", "higher"), "criterion: invalid direction")
        require(criterion["role"] in ("primary", "guardrail"), "criterion: invalid role")
        number(criterion["minimum_delta"], "minimum_delta")
        if criterion["role"] == "primary":
            require(criterion["minimum_delta"] > 0, "primary: minimum_delta must be positive")
    unique_ids(plan["criteria"], "criteria")
    require(sum(c["role"] == "primary" for c in plan["criteria"]) == 1, "exactly one primary criterion required")
    warnings.extend(f"{s['id']}: {s['status']} source" for s in plan["sources"] if s["status"] != "checked")
    return warnings


def review(plan, results):
    warnings = validate_plan(plan)
    fields(results, "schema_version plan_sha256 deviations usage pairs", "results")
    require(results["schema_version"] == VERSION, "results: unsupported schema version")
    require(results["plan_sha256"] == fingerprint(plan), "results: plan changed or wrong plan fingerprint")
    strings(results["deviations"], "deviations")
    fields(results["usage"], "minutes model_calls extra_cost", "usage")
    incomplete_usage = False
    for key, value in results["usage"].items():
        if value is None:
            incomplete_usage = True
        else:
            number(value, f"usage.{key}")
            require(value >= 0, f"usage.{key}: must be nonnegative")
            if key == "model_calls":
                require(type(value) is int, "usage.model_calls: integer required")
    array(results["pairs"], "pairs", 0, 100)
    metric_ids = {c["id"] for c in plan["criteria"]}
    for pair in results["pairs"]:
        fields(pair, "id baseline candidate", "pair")
        text(pair["id"], "pair.id")
        for arm in ("baseline", "candidate"):
            run = pair[arm]
            fields(run, "status metrics evidence_refs", arm)
            require(run["status"] in ("completed", "failed", "missing"), f"{arm}: invalid status")
            strings(run["evidence_refs"], "evidence_refs", 1 if run["status"] != "missing" else 0)
            require(isinstance(run["metrics"], dict) and set(run["metrics"]) <= metric_ids, f"{arm}: unknown metric")
            for key, value in run["metrics"].items():
                if value is not None:
                    number(value, key)
    pair_ids = unique_ids(results["pairs"], "pairs")
    require(pair_ids <= set(plan["expected_pairs"]), "unexpected pair ID; use a new plan for added trials")
    report = {"plan_id": plan["id"], "project_id": plan["project_id"], "data_origin": plan["data_origin"],
              "plan_sha256": fingerprint(plan), "verdict": "inconclusive", "reasons": [], "metrics": [],
              "warnings": warnings, "limitations": "Submitted measurements only; source authenticity, causality and statistical significance are not verified. No policy is activated."}
    reasons = report["reasons"]
    reasons.extend(f"condition changed: {d}" for d in results["deviations"])
    if incomplete_usage:
        reasons.append("Resource usage is incomplete; budget compliance unverified")
    for key, value in results["usage"].items():
        if value is not None and value > plan["budget"][key]:
            reasons.append(f"Budget exceeded: {key}")
    missing = sorted(set(plan["expected_pairs"]) - pair_ids)
    if missing:
        reasons.append("Missing planned pairs: " + ", ".join(missing))
    candidate_failed = False
    for pair in results["pairs"]:
        for arm in ("baseline", "candidate"):
            run = pair[arm]
            if arm == "candidate" and run["status"] == "failed":
                candidate_failed = True
            if run["status"] != "completed" or set(run["metrics"]) != metric_ids or any(v is None for v in run["metrics"].values()):
                reasons.append(f"{pair['id']}/{arm}: {run['status']}, comparison incomplete")
    if candidate_failed:
        report["verdict"] = "not_supported"
    if reasons:
        return report
    for criterion in plan["criteria"]:
        key = criterion["id"]
        sign = 1 if criterion["direction"] == "higher" else -1
        deltas = [sign * (p["candidate"]["metrics"][key] - p["baseline"]["metrics"][key]) for p in results["pairs"]]
        mean = math.fsum(deltas) / len(deltas)
        # Guardrails apply to every pair so averages cannot conceal a critical regression.
        passed = (mean >= criterion["minimum_delta"] if criterion["role"] == "primary"
                  else all(d >= criterion["minimum_delta"] for d in deltas))
        report["metrics"].append({"id": key, "role": criterion["role"], "unit": criterion["unit"],
                                  "paired_deltas": deltas, "mean_delta": mean, "minimum_delta": criterion["minimum_delta"], "passed": passed})
    report["verdict"] = "criteria_met" if all(m["passed"] for m in report["metrics"]) else "not_supported"
    return report


def no_duplicates(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def load(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Input exceeds 1 MiB limit")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Validate and fingerprint a frozen plan")
    check.add_argument("plan")
    compare = commands.add_parser("review", help="Compare results against a frozen plan")
    compare.add_argument("plan")
    compare.add_argument("results")
    args = parser.parse_args()
    try:
        plan = load(args.plan)
        if args.command == "check":
            warnings = validate_plan(plan)
            result = {"valid": True, "plan_sha256": fingerprint(plan), "warnings": warnings}
        else:
            result = review(plan, load(args.results))
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RecursionError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
