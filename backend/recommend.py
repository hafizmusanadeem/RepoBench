"""Turn finished runs into "which agent is best for this repo".

success  = Wilson lower bound of the pass rate (penalises small samples)
cost     = 1 - median_cost / max median_cost across agents
time     = 1 - median_duration / max median_duration across agents
score    = weighted blend of the terms that exist (weights renormalised).
"""

from __future__ import annotations

from math import sqrt
from statistics import median
from typing import Any


def wilson(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = passes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _med(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def build_recommendation(
    runs: list[dict[str, Any]], votes: list[dict[str, Any]], weights: dict[str, float]
) -> dict[str, Any]:
    total_w = sum(max(0.0, v) for v in weights.values()) or 1.0
    w = {k: max(0.0, v) / total_w for k, v in weights.items()}

    agents = sorted({r["agent"] for r in runs})
    run_agent = {r["id"]: r["agent"] for r in runs}
    tally: dict[str, dict[str, int]] = {a: {"wins": 0, "losses": 0, "ties": 0} for a in agents}
    for v in votes:
        a, b = run_agent.get(v["runA"]), run_agent.get(v["runB"])
        if not a or not b or a == b:
            continue
        if v["winner"] == "tie":
            tally[a]["ties"] += 1
            tally[b]["ties"] += 1
        else:
            win, lose = (a, b) if v["winner"] == "a" else (b, a)
            tally[win]["wins"] += 1
            tally[lose]["losses"] += 1

    stats: list[dict[str, Any]] = []
    for agent in agents:
        mine = [r for r in runs if r["agent"] == agent]
        done = [r for r in mine if r.get("status") == "success" and r.get("result") in ("PASS", "FAIL")]
        passes = sum(1 for r in done if r["result"] == "PASS")
        lo, hi = wilson(passes, len(done))
        costs = [r["costUsd"] for r in done if r.get("costUsd") is not None]
        toks = [r["tokens"] for r in done if r.get("tokens") is not None]
        stats.append({
            "agent": agent, "n": len(done), "passes": passes,
            "errors": sum(1 for r in mine if r.get("status") == "error"),
            "success_rate": passes / len(done) if done else 0.0, "ci_low": lo, "ci_high": hi,
            "median_duration_s": _med([r["durationSeconds"] for r in done if r.get("durationSeconds") is not None]),
            "median_cost_usd": _med(costs),
            "median_tokens": int(_med(toks)) if toks else None,
            "regression_rate": (sum(1 for r in done if (r.get("regressions") or 0) > 0) / len(done)) if done else 0.0,
            **tally[agent], "score": 0.0,
        })

    max_cost = max((s["median_cost_usd"] for s in stats if s["median_cost_usd"]), default=None)
    max_time = max((s["median_duration_s"] for s in stats if s["median_duration_s"]), default=None)
    for s in stats:
        terms: list[tuple[float, float]] = [(w.get("success", 0), s["ci_low"])]
        if max_cost and s["median_cost_usd"] is not None:
            terms.append((w.get("cost", 0), 1 - s["median_cost_usd"] / max_cost))
        if max_time and s["median_duration_s"] is not None:
            terms.append((w.get("time", 0), 1 - s["median_duration_s"] / max_time))
        tw = sum(t[0] for t in terms) or 1.0
        s["score"] = sum(t[0] * t[1] for t in terms) / tw

    ranked = sorted((s for s in stats if s["n"] > 0), key=lambda s: s["score"], reverse=True)
    stats.sort(key=lambda s: s["score"], reverse=True)
    if not ranked:
        return {"best_agent": None, "confidence": "none", "stats": stats, "weights": w,
                "summary": "No finished runs yet. Results appear here as runs complete."}

    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    overlap = runner_up is not None and runner_up["ci_high"] >= best["ci_low"]
    if best["n"] < 3:
        confidence = "low"
    elif overlap or best["n"] < 5:
        confidence = "medium"
    else:
        confidence = "high"

    parts = [f"{best['agent']} passed {best['passes']} of {best['n']} runs ({best['success_rate']:.0%})."]
    if best["median_duration_s"] is not None:
        parts.append(f"Median time {best['median_duration_s']:.0f}s.")
    if best["median_cost_usd"] is not None:
        parts.append(f"Median cost ${best['median_cost_usd']:.2f}.")
    if best["regression_rate"] > 0:
        parts.append(f"It broke existing tests in {best['regression_rate']:.0%} of runs.")
    if confidence == "low":
        parts.append("Too few runs to be confident: increase epochs and re-run.")
    elif overlap:
        parts.append(f"{runner_up['agent']} is statistically close; more runs would separate them.")  # type: ignore[index]
    return {"best_agent": best["agent"], "confidence": confidence, "summary": " ".join(parts),
            "stats": stats, "weights": w}
