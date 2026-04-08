"""
Medium Task — AeroSync AI (Drone-Only)
=======================================
Difficulty:  2 / 3
Agents:      3 drones
Deliveries:  6 tasks (mix of priority 1, 2, 3)
Grid:        15 × 15 (warehouse wall obstacles)
Max steps:   250
Battery:     drone_0=100%, drone_1=80%, drone_2=80%

Challenge:
  • Battery management — drones at 80% must monitor consumption and may
    need to recharge mid-episode.
  • Multi-drone coordination — 3 drones share 6 tasks; smart assignment
    avoids one drone doing all the work while others idle.
  • Obstacle wall splits the warehouse into pick zone (x < 6) and
    delivery corridor (x >= 7), drones MUST fly at z=1 to cross.
  • Priority scheduling — urgent tasks (p=3) must be delivered first.

Pipeline (drone-only):
    Drone moves to pickup_location → descends z=0 → pick →
    ascends z=1 → flies to delivery_location → descends z=0 →
    hover (stabilise) → place (DELIVERED)

Layout (z=0 ground plane, 15 × 15):
  Col:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14
  r00: [dr0][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r01: [  ][  ][  ][P1][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r02: [dr1][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r03: [  ][P0][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][T0][  ]
  r04: [  ][  ][  ][  ][P4][  ][##][  ][  ][  ][  ][  ][T1][  ][  ]
  r05: [  ][P5][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][T4][  ]
  r06: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r07: [  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ]  ← corridor gap
  r08: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r09: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][T2]
  r10: [  ][P2][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r11: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][T3][  ][  ][  ]
  r12: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r13: [  ][  ][  ][  ][  ][  ][  ][  ][  ][dr2][  ][  ][  ][  ][  ]
  r14: [C ][  ][  ][  ][C ][  ][  ][  ][  ][C ][  ][  ][  ][  ][  ]  ← charging row

  ## = obstacle (wall) — gap at rows 3, 7, 13 for ground passage (drones fly over)
  P* = pickup shelf  T* = delivery address  C = charging station
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        # ── Identity ─────────────────────────────────────────────────────
        "task_name":   "medium",
        "grid_width":  15,
        "grid_height": 15,
        "max_steps":   250,

        # ── Drones ───────────────────────────────────────────────────────
        # drone_0 — north zone, full battery, covers tasks near top rows
        # drone_1 — mid zone, 80% battery, covers mid-row tasks
        # drone_2 — south zone, 80% battery, covers bottom tasks
        "drones": [
            {"id": "drone_0", "start_x": 0, "start_y": 0,  "battery": 100.0},
            {"id": "drone_1", "start_x": 0, "start_y": 2,  "battery":  80.0},
            {"id": "drone_2", "start_x": 9, "start_y": 13, "battery":  80.0},
        ],

        # ── Tasks ─────────────────────────────────────────────────────────
        # Priorities:
        #   task_3 — priority 3 (URGENT)    Groceries
        #   task_4 — priority 3 (URGENT)    Medical Supplies
        #   task_0 — priority 2 (EXPRESS)   Electronics
        #   task_1 — priority 1 (normal)    Clothing
        #   task_2 — priority 1 (normal)    Books
        #   task_5 — priority 1 (normal)    Tools
        "tasks": [
            {
                "id":       "task_0",
                "item":     "Electronics",
                "pickup":   {"x": 1, "y": 3, "z": 0},
                "delivery": {"x": 13, "y": 1, "z": 0},
                "priority": 2,
            },
            {
                "id":       "task_1",
                "item":     "Clothing",
                "pickup":   {"x": 3, "y": 1, "z": 0},
                "delivery": {"x": 12, "y": 5, "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_2",
                "item":     "Books",
                "pickup":   {"x": 1, "y": 10, "z": 0},
                "delivery": {"x": 14, "y": 9, "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_3",
                "item":     "Groceries",
                "pickup":   {"x": 4, "y": 2, "z": 0},
                "delivery": {"x": 11, "y": 13, "z": 0},
                "priority": 3,
            },
            {
                "id":       "task_4",
                "item":     "Medical Supplies",
                "pickup":   {"x": 4, "y": 4, "z": 0},
                "delivery": {"x": 12, "y": 4, "z": 0},
                "priority": 3,
            },
            {
                "id":       "task_5",
                "item":     "Tools",
                "pickup":   {"x": 1, "y": 5, "z": 0},
                "delivery": {"x": 13, "y": 5, "z": 0},
                "priority": 1,
            },
        ],

        # ── Map Geometry ──────────────────────────────────────────────────
        # Vertical wall at x=6 divides grid into pick zone (x<=5) and
        # delivery corridor (x>=7). Drones fly over at z=1.
        # Gaps at row 3, 7, 13 allow ground access if needed.
        "obstacles": [
            # Upper wall segment
            (6, 0), (6, 1), (6, 2),
            # gap at row 3
            (6, 4), (6, 5), (6, 6),
            # gap at row 7
            (6, 8), (6, 9), (6, 10), (6, 11), (6, 12),
            # gap at row 13
        ],

        # Three charging stations
        "charging_stations": [
            (0, 14),   # south-west
            (4, 14),   # south-centre
            (9, 14),   # south drone pad
        ],
    }
