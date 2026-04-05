"""
Easy Task — AeroSync AI
=======================
Difficulty:  1 / 3
Agents:      1 robot  +  1 drone
Deliveries:  2 tasks  (both priority 1 — normal)
Grid:        10 × 10  (open, no obstacles)
Max steps:   120
Battery:     Both agents start at 100 %

Challenge:
  Learn the 3-stage handoff pipeline end-to-end:
    robot   → pick from shelf → carry to dispatch zone → place
    drone   → descend to dispatch zone → pick → fly to delivery → place

Layout (z = 0 ground plane):
  ┌──────────────────────────────┐
  │ R .  .  .  .  .  .  .  .  . │  row 0  (R=robot_0 start)
  │ .  .  .  .  .  .  .  .  .  . │  row 1
  │ . [P0] .  .         .  .  . │  row 2  (P0=task_0 pickup)
  │ .  .  .  .  .  .  .  .  .  . │  row 3
  │ .  .  .  .  [D] .  .  .  .  . │  row 4  (D=dispatch zone 4,4)
  │ .  .  .  .  .  .  .  .  .  . │  row 5
  │ .  .  .  .  .  .  .  .  .  . │  row 6
  │ .  .  .  .  .  .  .  .  .  . │  row 7
  │ .  .  .  .  .  .  .  . [T0] . │  row 8  (T0=task_0 delivery)
  │ [C] .  .  .  .  .  .  .  . [C] │  row 9  (C=charging stations)
  └──────────────────────────────┘

Charging stations: (0,9)  (9,9)
Drone starts at:   (5,0)  altitude z=1
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        # ── Identity ─────────────────────────────────────────────────────
        "task_name":   "easy",
        "grid_width":  10,
        "grid_height": 10,
        "max_steps":   120,

        # ── Agents ───────────────────────────────────────────────────────
        # robot_0 — starts at warehouse entrance, full battery
        # drone_0 — parks above dispatch area, full battery
        "robots": [
            {
                "id":      "robot_0",
                "start_x": 0,
                "start_y": 0,
                "battery": 100.0,
            },
        ],
        "drones": [
            {
                "id":      "drone_0",
                "start_x": 5,        # hovers above centre — equidistant from both dispatch zones
                "start_y": 0,
                "battery": 100.0,
            },
        ],

        # ── Tasks ─────────────────────────────────────────────────────────
        # task_0: Small Package  — shelf at (1,2) → dispatch (4,4) → deliver (8,8)
        # task_1: Documents      — shelf at (2,1) → dispatch (4,4) → deliver (9,2)
        #
        # Both share the single dispatch zone at (4,4).
        # The drone must make two separate trips or handle sequentially.
        "tasks": [
            {
                "id":       "task_0",
                "item":     "Small Package",
                "pickup":   {"x": 1, "y": 2, "z": 0},   # shelf row A
                "dispatch": {"x": 4, "y": 4, "z": 0},   # central dispatch pad
                "delivery": {"x": 8, "y": 8, "z": 0},   # customer address — south-east corner
                "priority": 1,                            # normal
            },
            {
                "id":       "task_1",
                "item":     "Documents",
                "pickup":   {"x": 2, "y": 1, "z": 0},   # shelf row B
                "dispatch": {"x": 4, "y": 4, "z": 0},   # same dispatch pad
                "delivery": {"x": 9, "y": 2, "z": 0},   # customer address — east side
                "priority": 1,                            # normal
            },
        ],

        # ── Map Geometry ──────────────────────────────────────────────────
        # No obstacles — open grid lets the agent focus purely on
        # understanding the sequential pipeline without routing complexity.
        "obstacles": [],

        # Single dispatch zone in the centre of the warehouse floor
        "dispatch_zones": [
            (4, 4),   # drone must descend here (z=0) to pick up dispatched tasks
        ],

        # Two charging stations along the south wall
        "charging_stations": [
            (0, 9),   # south-west pad  — convenient for robot after first delivery
            (9, 9),   # south-east pad  — convenient for drone after east deliveries
        ],
    }