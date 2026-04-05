"""
Hard Task — AeroSync AI
========================
Difficulty:  3 / 3
Agents:      6 robots  +  4 drones
Deliveries:  12 tasks  (3 urgent p=3, 4 express p=2, 5 normal p=1)
Grid:        20 × 20   (warehouse corridors + internal pillars)
Max steps:   500
Battery:     Two robots degraded (60 %, 45 %); two drones degraded (70 %, 55 %)

Challenge:
  • Priority scheduling — 3 urgent tasks (p=3) must be handled before
    lower-priority ones; poor scheduling is heavily penalised.
  • Energy-aware routing — 4 degraded agents must plan conservative routes
    and recharge proactively; a dead agent costs −50 reward + fails its task.
  • Dispatch congestion — 3 dispatch zones means multiple robots may arrive
    simultaneously; a drone cannot pick from a zone already occupied.
  • Large fleet coordination — 10 active agents on a 20×20 grid; collision
    avoidance becomes significant (−30 per collision).
  • Complex obstacle map — horizontal shelf rows, vertical corridor wall,
    and internal pillars require BFS planning to avoid dead-ends.

Layout (z = 0 ground plane, 20 × 20):
  Columns:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19
  ──────────────────────────────────────────────────────────────────────
  row 00:  [R0][  ][R1][  ][  ][  ][  ][  ][##][  ][dr0][  ][  ][  ]…
  row 01:  [  ][  ][  ][P0][  ][  ][  ][  ][##][  ][  ][  ][  ][  ]…  P0=task_0 shelf
  row 02:  [R2][  ][P2][  ][R3][  ][  ][  ][##][  ][  ][  ][  ][  ]…
  row 03:  [  ][  ][  ][  ][P1][P5][  ][  ][##][  ][  ][  ][  ][  ]…
  row 04:  [  ][  ][  ][  ][  ][  ][  ][  ][##][D1][  ][  ][  ]…T0… ← D1 dispatch
  row 05:  [R4][dr1][  ][  ][  ][  ][  ][  ][##][  ][  ][  ][  ]…T1…
  row 06:  [  ][  ][  ][P6][  ][P8][  ][  ][##][  ][  ][  ][  ][  ]…
  row 07:  [  ][  ][P7][  ][P10][  ][  ][  ][##][  ][dr2][  ][  ]…
  row 08:  [##][##][##][##][##][##][##][##][  ][  ][  ][  ]…          ← shelf row wall
  row 09:  [  ][  ][  ][  ][  ][  ][  ][  ][##][D2][  ]…             ← D2 dispatch
  row 10:  [  ][  ][  ][P3][  ][P11][  ][  ][##][  ][  ][  ][  ]…
  row 11:  [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ][  ]…T6…
  row 12:  [##][  ][##][  ][##][  ][  ][  ][##][  ][  ][  ][  ]…     ← pillars row
  row 13:  [  ][  ][  ][  ][P9][  ][  ][  ][##][  ][  ][  ][  ]…
  row 14:  [R5][  ][  ][  ][  ][  ][  ][  ][##][D3][  ]…dr3…         ← D3 dispatch
  row 15:  [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ][  ]…T3…
  row 16:  [  ][  ][  ][  ][P4][  ][  ][  ][##][  ][  ][  ][  ]…
  row 17:  [  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ]…T8/T9…  ← open corridor
  row 18:  [  ][  ][  ][  ][  ][  ][  ][  ][  ][  ][  ]…T4…T5…
  row 19:  [C ][  ][  ][  ][  ][C ][  ][  ][  ][  ][C ][  ][  ][C ] ← charging row

  ##=obstacle (wall/shelf/pillar)
  D1=(9,4)  D2=(9,9)  D3=(9,14)  — three dispatch zones
  P*=task pickup (shelf)   T*=task delivery address
  C =charging station      R*=robot start   dr*=drone start

Robot dispatch zone assignment (suggested, not enforced by env):
  D1 (9,4)  → robot_0, robot_1   (shortest from top)
  D2 (9,9)  → robot_2, robot_3   (mid zone)
  D3 (9,14) → robot_4, robot_5   (bottom zone)

Drone coverage:
  drone_0 → D1 (north)
  drone_1 → D1 / D2  (flexible mid; battery degraded → plan RTB early)
  drone_2 → D2 (centre)
  drone_3 → D3 (south; critically degraded → recharge first)
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        # ── Identity ─────────────────────────────────────────────────────
        "task_name":   "hard",
        "grid_width":  20,
        "grid_height": 20,
        "max_steps":   500,

        # ── Agents ───────────────────────────────────────────────────────
        # Robot notes:
        #   robot_2  (60 %) — 1-2 tasks before recharge needed
        #   robot_5  (45 %) — must recharge before first long trip; assign a
        #                     shelf close to charging station at (0,19)
        #
        # Drone notes:
        #   drone_1  (70 %) — budget ~46 cruise steps at 1.5 %/step before RTB
        #   drone_3  (55 %) — budget ~36 cruise steps; should recharge before
        #                     attempting long south deliveries
        "robots": [
            {"id": "robot_0", "start_x": 0,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_1", "start_x": 2,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_2", "start_x": 0,  "start_y": 2,  "battery":  60.0},  # degraded
            {"id": "robot_3", "start_x": 4,  "start_y": 2,  "battery": 100.0},
            {"id": "robot_4", "start_x": 0,  "start_y": 5,  "battery":  80.0},
            {"id": "robot_5", "start_x": 0,  "start_y": 14, "battery":  45.0},  # critically low
        ],
        "drones": [
            {"id": "drone_0", "start_x": 10, "start_y": 0,  "battery": 100.0},
            {"id": "drone_1", "start_x": 10, "start_y": 5,  "battery":  70.0},  # degraded
            {"id": "drone_2", "start_x": 10, "start_y": 10, "battery": 100.0},
            {"id": "drone_3", "start_x": 10, "start_y": 15, "battery":  55.0},  # degraded
        ],

        # ── Tasks ─────────────────────────────────────────────────────────
        # Priority legend:   3 = URGENT  |  2 = EXPRESS  |  1 = normal
        #
        # Drone dispatch zone routing:
        #   → D1 (9,4) : task_0, task_1, task_5
        #   → D2 (9,9) : task_2, task_6, task_7, task_11
        #   → D3 (9,14): task_3, task_4, task_8, task_9, task_10
        "tasks": [
            # ── URGENT (priority 3) ──────────────────────────────────────
            {
                "id":       "task_0",
                "item":     "Urgent Medicine",
                "pickup":   {"x": 3,  "y": 1,  "z": 0},   # shelf — north pick zone
                "dispatch": {"x": 9,  "y": 4,  "z": 0},   # D1 — north dispatch
                "delivery": {"x": 18, "y": 1,  "z": 0},   # customer — far north-east
                "priority": 3,
            },
            {
                "id":       "task_1",
                "item":     "Frozen Food",
                "pickup":   {"x": 2,  "y": 3,  "z": 0},   # shelf — top-left
                "dispatch": {"x": 9,  "y": 4,  "z": 0},   # D1
                "delivery": {"x": 19, "y": 10, "z": 0},   # customer — mid east edge
                "priority": 3,
            },
            {
                "id":       "task_2",
                "item":     "Baby Supplies",
                "pickup":   {"x": 4,  "y": 5,  "z": 0},   # shelf — mid pick zone
                "dispatch": {"x": 9,  "y": 9,  "z": 0},   # D2 — centre dispatch
                "delivery": {"x": 16, "y": 19, "z": 0},   # customer — south zone
                "priority": 3,
            },

            # ── EXPRESS (priority 2) ─────────────────────────────────────
            {
                "id":       "task_3",
                "item":     "Electronics Bundle",
                "pickup":   {"x": 4,  "y": 3,  "z": 0},   # shelf — near corridor gap
                "dispatch": {"x": 9,  "y": 14, "z": 0},   # D3 — south dispatch
                "delivery": {"x": 17, "y": 6,  "z": 0},   # customer — east-north
                "priority": 2,
            },
            {
                "id":       "task_4",
                "item":     "Smart Device",
                "pickup":   {"x": 5,  "y": 1,  "z": 0},   # shelf — top row, near wall
                "dispatch": {"x": 9,  "y": 9,  "z": 0},   # D2
                "delivery": {"x": 15, "y": 8,  "z": 0},   # customer — mid east
                "priority": 2,
            },
            {
                "id":       "task_5",
                "item":     "Tools Kit",
                "pickup":   {"x": 3,  "y": 4,  "z": 0},   # shelf — centre-left
                "dispatch": {"x": 9,  "y": 4,  "z": 0},   # D1
                "delivery": {"x": 18, "y": 4,  "z": 0},   # customer — east, same row
                "priority": 2,
            },
            {
                "id":       "task_6",
                "item":     "Fragile Glassware",
                "pickup":   {"x": 3,  "y": 6,  "z": 0},   # shelf — above pillar row
                "dispatch": {"x": 9,  "y": 9,  "z": 0},   # D2
                "delivery": {"x": 19, "y": 15, "z": 0},   # customer — far south-east
                "priority": 2,
            },

            # ── NORMAL (priority 1) ──────────────────────────────────────
            {
                "id":       "task_7",
                "item":     "Clothing Set",
                "pickup":   {"x": 4,  "y": 7,  "z": 0},   # shelf — above shelf row wall
                "dispatch": {"x": 9,  "y": 9,  "z": 0},   # D2
                "delivery": {"x": 16, "y": 14, "z": 0},   # customer — south-east
                "priority": 1,
            },
            {
                "id":       "task_8",
                "item":     "Books Order",
                "pickup":   {"x": 1,  "y": 10, "z": 0},   # shelf — below shelf wall
                "dispatch": {"x": 9,  "y": 14, "z": 0},   # D3
                "delivery": {"x": 17, "y": 18, "z": 0},   # customer — south zone
                "priority": 1,
            },
            {
                "id":       "task_9",
                "item":     "Sports Equipment",
                "pickup":   {"x": 4,  "y": 13, "z": 0},   # shelf — south pick zone
                "dispatch": {"x": 9,  "y": 14, "z": 0},   # D3
                "delivery": {"x": 18, "y": 16, "z": 0},   # customer — south zone
                "priority": 1,
            },
            {
                "id":       "task_10",
                "item":     "Furniture Part",
                "pickup":   {"x": 5,  "y": 3,  "z": 0},   # shelf — near corridor gap
                "dispatch": {"x": 9,  "y": 14, "z": 0},   # D3
                "delivery": {"x": 14, "y": 3,  "z": 0},   # customer — east-north
                "priority": 1,
            },
            {
                "id":       "task_11",
                "item":     "Office Supplies",
                "pickup":   {"x": 5,  "y": 11, "z": 0},   # shelf — south-left zone
                "dispatch": {"x": 9,  "y": 9,  "z": 0},   # D2
                "delivery": {"x": 17, "y": 12, "z": 0},   # customer — east-south
                "priority": 1,
            },
        ],

        # ── Map Geometry ──────────────────────────────────────────────────
        # Three structural layers:
        #
        # 1. Horizontal shelf row wall  (y=8, x=0–7)
        #    — separates north pick zone from south pick zone
        #    — robots must go around via x=8 gap or through y≤7 rows
        #
        # 2. Vertical dispatch corridor wall  (x=8, all y except gaps)
        #    — gap at y=4  (for D1), y=9 (for D2), y=14 (for D3)
        #    — forces robots to approach dispatch zones at exact gap rows
        #    — drones fly over at z=1 and are unaffected
        #
        # 3. Internal pillars  (y=12, even columns 0,2,4)
        #    — create routing complexity in the south pick zone
        #    — robots must weave between pillars to reach shelves y>=13
        "obstacles": [
            # Horizontal shelf row wall (y=8, x=0..7)
            (0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (6, 8), (7, 8),

            # Vertical corridor wall (x=8) — full column EXCEPT gap rows 4, 9, 14
            (8, 0),  (8, 1),  (8, 2),  (8, 3),
            # gap at (8,4) — D1 entrance
            (8, 5),  (8, 6),  (8, 7),  (8, 8),
            # gap at (8,9) — D2 entrance
            (8, 10), (8, 11), (8, 12), (8, 13),
            # gap at (8,14) — D3 entrance
            (8, 15), (8, 16), (8, 17), (8, 18), (8, 19),

            # Internal pillars — south pick zone (y=12)
            (0, 12), (2, 12), (4, 12),
        ],

        # Three dispatch zones — one per corridor gap
        "dispatch_zones": [
            (9, 4),    # D1 — north  (gap at x=8,y=4)
            (9, 9),    # D2 — centre (gap at x=8,y=9)
            (9, 14),   # D3 — south  (gap at x=8,y=14)
        ],

        # Four charging stations:
        #   (0,19)  — robot south-west pad  (robot_5 starts nearby at 45 %)
        #   (5,19)  — robot south-centre pad (general robot fallback)
        #   (10,0)  — drone north pad  (drone_0 & drone_1 closest)
        #   (10,19) — drone south pad  (drone_2 & drone_3 closest)
        "charging_stations": [
            (0,  19),   # robot pad SW — robot_5 priority recharge
            (5,  19),   # robot pad SC — general robot recharge
            (10,  0),   # drone pad N  — drone_0 / drone_1
            (10, 19),   # drone pad S  — drone_2 / drone_3
        ],
    }
