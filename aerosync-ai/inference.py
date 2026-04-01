"""
AeroSync AI — Baseline Inference Script
Uses OpenAI-compatible client to run an LLM agent against all 3 tasks.

Environment variables required:
    API_BASE_URL    — LLM endpoint (e.g. https://api.openai.com/v1)
    MODEL_NAME      — Model to use (e.g. gpt-4o-mini)
    HF_TOKEN        — Hugging Face token (used as API key if API_BASE_URL points to HF)

Usage:
    python inference.py
    python inference.py --task easy
    python inference.py --task all --max_steps 60
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

# ── Local imports (works both locally and inside Docker) ────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env.aerosync_env import AeroSyncEnv
from env.models import AeroSyncAction
from grader.grader import grade, detailed_report
from tasks.easy   import get_config as easy_config
from tasks.medium import get_config as medium_config
from tasks.hard   import get_config as hard_config


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
API_KEY      = os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_TOKEN", "")

TASK_CONFIGS = {
    "easy":   easy_config,
    "medium": medium_config,
    "hard":   hard_config,
}

# Steps to run per task in baseline (keep short for speed)
MAX_STEPS_PER_TASK = {
    "easy":   40,
    "medium": 80,
    "hard":   120,
}


# ──────────────────────────────────────────────────────────────────────────────
# LLM agent helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    return """You are an AI agent controlling a logistics system with robots and drones.

WORLD:
- Robots move on ground (z=0). They PICK items from shelves and PLACE them at dispatch zones.
- Drones fly at altitude (z=1). They PICK from dispatch zones and PLACE at customer delivery points.
- Charging stations restore battery. Agents with battery=0 cannot act.

YOUR JOB: Issue ONE action per turn to move tasks through the pipeline:
  PENDING → (robot picks) → PICKED → (robot places at dispatch) → DISPATCHED →
  (drone picks) → IN_FLIGHT → (drone places at delivery) → DELIVERED

ACTION FORMAT (respond with ONLY valid JSON, no markdown):
{
  "agent_id": "robot_0",
  "action_type": "move|pick|place|charge|wait|assign_task",
  "direction": "north|south|east|west",   // only for move
  "task_id": "task_0"                      // for assign_task / pick / place
}

STRATEGY:
1. Assign pending tasks to idle robots (assign_task).
2. Move robots toward pickup locations, then PICK.
3. Move robots to dispatch zone, then PLACE.
4. Move drones to dispatch zone, PICK dispatched items.
5. Move drones to delivery location, PLACE.
6. Charge agents with battery < 20.
7. Prioritise urgent tasks (priority=3).
"""


def obs_to_prompt(obs: Dict[str, Any]) -> str:
    """Summarise observation for LLM context."""
    agents_summary = []
    for aid, a in obs.get("agents", {}).items():
        pos = a.get("position", {})
        agents_summary.append(
            f"  {aid} ({a.get('agent_type')}): pos=({pos.get('x')},{pos.get('y')},z{pos.get('z')}) "
            f"battery={a.get('battery', 0):.0f}% "
            f"carrying={a.get('carrying_task_id') or 'none'} "
            f"idle={a.get('is_idle')}"
        )

    tasks_summary = []
    for tid, t in obs.get("tasks", {}).items():
        pick = t.get("pickup_location", {})
        disp = t.get("dispatch_location", {})
        deli = t.get("delivery_location", {})
        tasks_summary.append(
            f"  {tid} [{t.get('status')}] p={t.get('priority')} "
            f"pickup=({pick.get('x')},{pick.get('y')}) "
            f"dispatch=({disp.get('x')},{disp.get('y')}) "
            f"delivery=({deli.get('x')},{deli.get('y')}) "
            f"robot={t.get('assigned_robot') or 'unassigned'}"
        )

    dispatch_q = obs.get("dispatch_queue", [])
    metrics = obs.get("metrics", {})

    return f"""STEP {obs.get('step')}/{obs.get('max_steps')}
TASK: {obs.get('task_name')} | completion={metrics.get('completion_rate', 0):.1%}

AGENTS:
{chr(10).join(agents_summary)}

TASKS:
{chr(10).join(tasks_summary)}

DISPATCH QUEUE (waiting for drone): {dispatch_q}
LAST REWARD: {obs.get('reward', 0):.2f}

Choose the BEST single action. Respond with JSON only."""


def call_llm(client: OpenAI, conversation: List[Dict], obs: Dict[str, Any]) -> Optional[Dict]:
    """Call LLM and parse action JSON."""
    conversation.append({
        "role": "user",
        "content": obs_to_prompt(obs),
    })

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=conversation,
            temperature=0.2,
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        conversation.append({"role": "assistant", "content": content})

        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content.strip())

    except json.JSONDecodeError as e:
        print(f"    [WARN] JSON parse error: {e} — using WAIT fallback")
        return None
    except Exception as e:
        print(f"    [WARN] LLM error: {e} — using WAIT fallback")
        return None


def parse_action(raw: Optional[Dict], agents: Dict) -> AeroSyncAction:
    """Parse LLM output into a typed AeroSyncAction, with fallback."""
    if raw is None:
        # Fallback: pick first agent, WAIT
        agent_id = next(iter(agents.keys()), "robot_0")
        return AeroSyncAction(agent_id=agent_id, action_type="wait")

    return AeroSyncAction(
        agent_id=raw.get("agent_id", next(iter(agents.keys()), "robot_0")),
        action_type=raw.get("action_type", "wait"),
        direction=raw.get("direction"),
        task_id=raw.get("task_id"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Run one task
# ──────────────────────────────────────────────────────────────────────────────

def run_task(client: OpenAI, task_name: str, max_steps: int) -> Dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"  TASK: {task_name.upper()}  (max {max_steps} agent steps)")
    print(f"{'='*60}")

    config = TASK_CONFIGS[task_name]()
    env = AeroSyncEnv(config)
    obs = env.reset()
    obs_dict = obs.dict()

    conversation = [{"role": "system", "content": build_system_prompt()}]

    total_reward = 0.0
    step_count = 0
    t0 = time.time()

    for step_i in range(max_steps):
        raw_action = call_llm(client, conversation, obs_dict)
        action = parse_action(raw_action, obs_dict.get("agents", {}))

        obs, reward, done, info = env.step(action)
        obs_dict = obs.dict()
        total_reward += reward
        step_count += 1

        # Progress print every 10 steps
        if step_i % 10 == 0 or done:
            metrics = obs_dict.get("metrics", {})
            print(f"  step={step_i:4d} | reward={reward:+6.2f} | "
                  f"completion={metrics.get('completion_rate', 0):.1%} | "
                  f"collisions={int(metrics.get('collisions', 0))}")

        if done:
            print(f"  Episode finished at step {step_i}")
            break

    elapsed = time.time() - t0
    final_state = env.state()
    score = grade(final_state)
    report = detailed_report(final_state)

    print(f"\n  ─── Results for {task_name} ───")
    print(f"  Final score  : {score:.4f}")
    print(f"  Delivered    : {report['delivered']} / {report['total_tasks']}")
    print(f"  Collisions   : {report['collisions']}")
    print(f"  Bat. failures: {report['battery_failures']}")
    print(f"  Steps used   : {report['steps_used']}")
    print(f"  Wall time    : {elapsed:.1f}s")

    return {
        "task_name":      task_name,
        "score":          score,
        "total_reward":   round(total_reward, 2),
        "steps":          step_count,
        "delivered":      report["delivered"],
        "total_tasks":    report["total_tasks"],
        "collisions":     report["collisions"],
        "bat_failures":   report["battery_failures"],
        "wall_time_s":    round(elapsed, 1),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AeroSync AI — Baseline Inference")
    parser.add_argument("--task", default="all",
                        choices=["all", "easy", "medium", "hard"],
                        help="Which task(s) to run")
    parser.add_argument("--max_steps", type=int, default=None,
                        help="Override max steps per task")
    args = parser.parse_args()

    if not API_KEY:
        print("[ERROR] Set OPENAI_API_KEY or HF_TOKEN environment variable.")
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    tasks_to_run = ["easy", "medium", "hard"] if args.task == "all" else [args.task]

    results = []
    for task_name in tasks_to_run:
        max_steps = args.max_steps or MAX_STEPS_PER_TASK[task_name]
        result = run_task(client, task_name, max_steps)
        results.append(result)

    # ── Summary table ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  BASELINE SCORES SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Task':<10} {'Score':>7}  {'Delivered':>10}  {'Collisions':>11}  {'Steps':>6}")
    print(f"  {'-'*54}")
    for r in results:
        delivered_str = f"{r['delivered']}/{r['total_tasks']}"
        print(f"  {r['task_name']:<10} {r['score']:>7.4f}  {delivered_str:>10}  "
              f"{r['collisions']:>11}  {r['steps']:>6}")

    avg_score = sum(r["score"] for r in results) / len(results)
    print(f"  {'-'*54}")
    print(f"  {'AVERAGE':<10} {avg_score:>7.4f}")
    print(f"{'='*60}\n")

    # Write JSON results
    out_path = os.path.join(os.path.dirname(__file__), "baseline_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "model":   MODEL_NAME,
            "results": results,
            "average_score": round(avg_score, 4),
        }, f, indent=2)
    print(f"Results saved to: {out_path}")

    return results


if __name__ == "__main__":
    main()
