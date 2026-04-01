"""
AeroSync AI — Task Grader
Produces deterministic scores in [0.0, 1.0] for each task difficulty.

Score formula:
    score = completion_ratio
            * efficiency_factor
            * safety_factor
            * priority_factor
    clipped to [0.0, 1.0]
"""
from __future__ import annotations
from typing import Dict, Any
from env.models import TaskStatus


# ──────────────────────────────────────────────────────────────────────────────
# Grading weights per difficulty
# ──────────────────────────────────────────────────────────────────────────────
GRADE_PARAMS = {
    "easy": {
        "completion_weight":  0.70,
        "efficiency_weight":  0.15,   # steps used vs max
        "safety_weight":      0.10,   # collision / battery penalty
        "priority_weight":    0.05,
    },
    "medium": {
        "completion_weight":  0.55,
        "efficiency_weight":  0.20,
        "safety_weight":      0.15,
        "priority_weight":    0.10,
    },
    "hard": {
        "completion_weight":  0.45,
        "efficiency_weight":  0.20,
        "safety_weight":      0.20,
        "priority_weight":    0.15,
    },
}


def grade(state: Dict[str, Any]) -> float:
    """
    Grade a completed (or timed-out) episode.

    Args:
        state: dict returned by env.state()

    Returns:
        float in [0.0, 1.0]
    """
    task_name = state.get("task_name", "easy")
    params = GRADE_PARAMS.get(task_name, GRADE_PARAMS["easy"])

    tasks = state.get("tasks", {})
    if not tasks:
        return 0.0

    # ── 1. Completion ratio ─────────────────────────────────────────────────
    total_tasks = len(tasks)
    delivered = sum(
        1 for t in tasks.values()
        if t.get("status") == TaskStatus.DELIVERED or t.get("status") == "delivered"
    )
    completion_ratio = delivered / total_tasks

    # ── 2. Priority-weighted completion ────────────────────────────────────
    priority_score = _priority_score(tasks, delivered)

    # ── 3. Efficiency (steps used) ─────────────────────────────────────────
    steps_used = state.get("step", 1)
    max_steps  = state.get("max_steps", 1)
    # Perfect = finish in 50% of steps; using 100% = 0.5 efficiency
    efficiency_ratio = max(0.0, 1.0 - (steps_used / max_steps) * 0.5) if max_steps > 0 else 0.5

    # ── 4. Safety factor ───────────────────────────────────────────────────
    collisions       = state.get("collision_count", 0)
    battery_failures = state.get("battery_failures", 0)
    # Each collision subtracts 0.1, each battery failure subtracts 0.15
    safety_deduction = (collisions * 0.10) + (battery_failures * 0.15)
    safety_factor    = max(0.0, 1.0 - safety_deduction)

    # ── 5. Weighted sum ─────────────────────────────────────────────────────
    score = (
        params["completion_weight"] * completion_ratio
        + params["efficiency_weight"] * efficiency_ratio
        + params["safety_weight"]    * safety_factor
        + params["priority_weight"]  * priority_score
    )

    return round(float(min(1.0, max(0.0, score))), 4)


def _priority_score(tasks: Dict[str, Any], delivered_count: int) -> float:
    """
    Score based on whether high-priority tasks were completed first.
    Returns 0.0 – 1.0.
    """
    if delivered_count == 0:
        return 0.0

    delivered_tasks = [
        t for t in tasks.values()
        if t.get("status") in ("delivered", TaskStatus.DELIVERED)
    ]

    if not delivered_tasks:
        return 0.0

    # Average priority of delivered tasks (normalised: priority 3 = best = 1.0)
    total_priority = sum(t.get("priority", 1) for t in delivered_tasks)
    max_possible   = 3 * len(delivered_tasks)
    return total_priority / max_possible if max_possible > 0 else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Per-task sub-scores (for verbose reporting)
# ──────────────────────────────────────────────────────────────────────────────
def detailed_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return detailed grading breakdown for inspection."""
    task_name = state.get("task_name", "easy")
    tasks     = state.get("tasks", {})
    total     = len(tasks)
    delivered = sum(
        1 for t in tasks.values()
        if t.get("status") in ("delivered", TaskStatus.DELIVERED)
    )

    return {
        "task_name":        task_name,
        "total_tasks":      total,
        "delivered":        delivered,
        "completion_ratio": delivered / total if total > 0 else 0.0,
        "collisions":       state.get("collision_count", 0),
        "battery_failures": state.get("battery_failures", 0),
        "steps_used":       state.get("step", 0),
        "max_steps":        state.get("max_steps", 0),
        "final_score":      grade(state),
        "task_statuses": {
            tid: t.get("status")
            for tid, t in tasks.items()
        },
    }
