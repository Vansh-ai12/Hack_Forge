"""
Medium Task — AeroSync AI
==========================
Difficulty:  2 / 3
Agents:      3 robots  +  2 drones
Deliveries:  6 tasks   (mix of priority 1, 2, 3)
Grid:        15 × 15   (with warehouse wall obstacles)
Max steps:   250
Battery:     Robots full (100 %); drones start at 80 % (partial charge)

Challenge:
  • Multi-robot task assignment — 3 robots share 6 tasks; smart assignment
    avoids one robot doing all the work while others idle.
  • Battery management — drones at 80 % must monitor consumption and may
    need to recharge mid-episode.
  • Dual dispatch zones ((7,3) and (7,7)) — agents must coordinate which
    robot delivers to which zone so drones aren't blocked waiting.
  • Obstacle walls split the warehouse into a pick zone (x < 6) and a
    dispatch zone (x ≥ 7), forcing robots through the corridor gap at x=6.

Layout (z = 0 ground plane, 15 × 15):
  Col:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14
  r00: [R0][  ][R1][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r01: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r02: [R2][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r03: [  ][P0][  ][  ][  ][  ][  ][D1][  ][  ][  ][  ][  ][T0][  ]  ← dispatch zone 1
  r04: [  ][  ][  ][  ][P4][  ][##][  ][  ][  ][  ][  ][T1][  ][  ]
  r05: [  ][P1][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][T4][  ]
  r06: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r07: [  ][  ][  ][  ][  ][  ][  ][D2][  ][  ][  ][  ][  ][  ][  ]  ← dispatch zone 2
  r08: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r09: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][T2]
  r10: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r11: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][T3][  ][  ][  ]
  r12: [  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ][  ][  ][  ][  ]
  r13: [  ][  ][  ][  ][  ][  ][  ][  ][  ][dr1][  ][  ][  ][  ][  ]
  r14: [C ][  ][  ][  ][C ][  ][  ][  ][  ][C ][  ][  ][  ][  ][  ]  ← charging row

  ##  = obstacle (warehouse wall)
  D1  = dispatch zone (7,3);  D2 = dispatch zone (7,7)
  P*  = task pickup (shelf)
  T*  = task delivery address
  C   = charging station
  R*  = robot start;  dr* = drone start
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        # ── Identity ─────────────────────────────────────────────────────
        "task_name":   "medium",
        "grid_width":  15,
        "grid_height": 15,
        "max_steps":   250,

        # ── Agents ───────────────────────────────────────────────────────
        # Robots cluster near the pick zone (x ≤ 5) to reach shelves fast.
        # Drones start near the dispatch corridor at 80 % battery — they
        # will need at least one recharge cycle across 6 deliveries.
        "robots": [
            {"id": "robot_0", "start_x": 0, "start_y": 0,  "battery": 100.0},
            {"id": "robot_1", "start_x": 2, "start_y": 0,  "battery": 100.0},
            {"id": "robot_2", "start_x": 0, "start_y": 2,  "battery": 100.0},
        ],
        "drones": [
            # drone_0 — near north dispatch zone (7,3)
            {"id": "drone_0", "start_x": 7, "start_y": 2,  "battery": 80.0},
            # drone_1 — near south dispatch zone (7,7), further from charging
            {"id": "drone_1", "start_x": 7, "start_y": 6,  "battery": 80.0},
        ],

        # ── Tasks ─────────────────────────────────────────────────────────
        # Priorities:
        #   task_3  — priority 3 (URGENT)    Groceries
        #   task_4  — priority 3 (URGENT)    Medical Supplies
        #   task_0  — priority 2 (EXPRESS)   Electronics
        #   task_1  — priority 1 (normal)    Clothing
        #   task_2  — priority 1 (normal)    Books
        #   task_5  — priority 1 (normal)    Tools
        #
        # Dispatch zone routing:
        #   North zone (7,3)  → task_0, task_1, task_4
        #   South zone (7,7)  → task_2, task_3, task_5
        "tasks": [
            {
                "id":       "task_0",
                "item":     "Electronics",
                "pickup":   {"x": 1, "y": 3, "z": 0},    # shelf — left warehouse
                "dispatch": {"x": 7, "y": 3, "z": 0},    # north dispatch zone
                "delivery": {"x": 13, "y": 1, "z": 0},   # customer — north-east
                "priority": 2,                             # express
            },
            {
                "id":       "task_1",
                "item":     "Clothing",
                "pickup":   {"x": 3, "y": 1, "z": 0},    # shelf — top row
                "dispatch": {"x": 7, "y": 3, "z": 0},    # north dispatch zone
                "delivery": {"x": 12, "y": 5, "z": 0},   # customer — east-centre
                "priority": 1,
            },
            {
                "id":       "task_2",
                "item":     "Books",
                "pickup":   {"x": 1, "y": 5, "z": 0},    # shelf — mid-left
                "dispatch": {"x": 7, "y": 7, "z": 0},    # south dispatch zone
                "delivery": {"x": 14, "y": 9, "z": 0},   # customer — far east
                "priority": 1,
            },
            {
                "id":       "task_3",
                "item":     "Groceries",
                "pickup":   {"x": 4, "y": 2, "z": 0},    # shelf — near wall gap
                "dispatch": {"x": 7, "y": 7, "z": 0},    # south dispatch zone
                "delivery": {"x": 11, "y": 13, "z": 0},  # customer — south-east
                "priority": 3,                             # urgent — deliver first
            },
            {
                "id":       "task_4",
                "item":     "Medical Supplies",
                "pickup":   {"x": 2, "y": 4, "z": 0},    # shelf — centre-left
                "dispatch": {"x": 7, "y": 3, "z": 0},    # north dispatch zone
                "delivery": {"x": 13, "y": 11, "z": 0},  # customer — south-east
                "priority": 3,                             # urgent — deliver first
            },
            {
                "id":       "task_5",
                "item":     "Tools",
                "pickup":   {"x": 5, "y": 1, "z": 0},    # shelf — near wall (x=5 is last free col)
                "dispatch": {"x": 7, "y": 7, "z": 0},    # south dispatch zone
                "delivery": {"x": 14, "y": 14, "z": 0},  # customer — far south-east corner
                "priority": 1,
            },
        ],

        # ── Map Geometry ──────────────────────────────────────────────────
        # Vertical warehouse wall at x=6 divides the grid into:
        #   Left  (x ≤ 5) — pick zone  (shelves, robot start positions)
        #   Right (x ≥ 7) — dispatch + delivery corridor
        #
        # Robots must pass through the gap rows (row 3 at x=6 is free,
        # row 7 at x=6 is free) to reach dispatch zones.
        #
        # Upper wall:  (6,0)–(6,4)     blocks straight north passage
        # Lower wall:  (6,8)–(6,12)    blocks straight south passage
        # Gap at (6,5), (6,6), (6,7) — open corridor
        "obstacles": [
            # Upper wall segment (blocks rows 0-4)
            (6, 0), (6, 1), (6, 2), (6, 3), (6, 4),
            # Lower wall segment (blocks rows 8-12)
            (6, 8), (6, 9), (6, 10), (6, 11), (6, 12),
        ],

        # Two dispatch pads — north and south — force routing decisions
        "dispatch_zones": [
            (7, 3),   # north pad  — covered by drone_0
            (7, 7),   # south pad  — covered by drone_1
        ],

        # Three charging stations:
        #   (0,14)  — robot recharge point (south-west)
        #   (4,14)  — robot recharge point (south-centre-left)
        #   (9,0)   — drone recharge pad (north — close to dispatch corridor)
        "charging_stations": [
            (0, 14),  # robot charging — south-west corner
            (4, 14),  # robot charging — south-centre
            (9, 0),   # drone pad — north side of delivery corridor
        ],
    }
