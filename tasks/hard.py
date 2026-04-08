"""
Hard Task — AeroSync AI (Drone-Only)
======================================
Difficulty:  3 / 3
Agents:      6 drones
Deliveries:  12 tasks (3 urgent p=3, 4 express p=2, 5 normal p=1)
Grid:        20 × 20 (warehouse corridors + internal pillars)
Max steps:   500
Battery:     Two drones degraded (70%, 55%): drone_4=70%, drone_5=55%

Challenge:
  • Priority scheduling — 3 urgent tasks (p=3) must be handled before
    lower-priority ones; poor scheduling is heavily penalised.
  • Energy-aware routing — 2 degraded drones must plan conservative routes
    and recharge proactively; dead drone = −50 reward + fails its task.
  • Large fleet coordination — 6 drones on a 20×20 grid with obstacles;
    collision avoidance is critical (−30 per collision).
  • Complex obstacle map — horizontal shelf row wall, vertical corridor wall,
    and internal pillars; drones FLY OVER at z=1 (no routing constraints).
  • Battery-limited: even full drones must RTB mid-episode for recharge.

Pipeline (drone-only):
    Drone flies to pickup_location → descend z=0 → pick →
    ascend z=1 → fly to delivery_location → descend z=0 →
    hover (stabilise) → place (DELIVERED) → RTB to charging pad if low battery

Layout (z=0 ground plane, 20×20):
  ## = obstacle  P* = shelf  T* = delivery  C = charging  dr* = drone start

  Columns: 0..19
  row 00: [dr0][  ][dr1][  ][  ][  ][  ][  ][##][  ][dr2][  ][  ]…
  row 01: [  ][  ][  ][P0][  ][  ][  ][  ][##][  ][  ][  ]…T0…
  row 02: [  ][  ][P2][  ][  ][  ][  ][  ][##][  ][  ][  ]…
  row 03: [  ][  ][  ][  ][P1][P5][  ][  ][##][  ][  ]…
  row 04: [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…T1…
  row 05: [dr3][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…
  row 06: [  ][  ][  ][P6][  ][P8][  ][  ][##][  ][  ]…
  row 07: [  ][  ][P7][  ][P10][  ][  ][  ][##][  ][dr4]…
  row 08: [##][##][##][##][##][##][##][##][  ][  ][  ]…  ← shelf row wall
  row 09: [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…
  row 10: [  ][  ][  ][P3][  ][P11][  ][  ][##][  ][  ]…
  row 11: [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…T6…
  row 12: [##][  ][##][  ][##][  ][  ][  ][##][  ][  ]…  ← pillars
  row 13: [  ][  ][  ][  ][P9][  ][  ][  ][##][  ][  ]…
  row 14: [dr5][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…
  row 15: [  ][  ][  ][  ][  ][  ][  ][  ][##][  ][  ]…T3…
  row 16: [  ][  ][  ][  ][P4][  ][  ][  ][##][  ][  ]…
  row 17: [  ][  ][  ][  ][  ][  ][  ][  ][  ][  ]…T8…T9…  ← open corridor
  row 18: [  ][  ][  ][  ][  ][  ][  ][  ][  ][  ]…T4…T5…
  row 19: [C ][  ][  ][  ][  ][C ][  ][  ][  ][  ][C ][  ][C ]  ← charging row

  Obstacles form walls — drones fly OVER at z=1, no routing constraint.
  Vertical wall at x=8, horizontal shelf wall at y=8 (x=0..7),
  internal pillars at y=12 (x=0,2,4).
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        # ── Identity ─────────────────────────────────────────────────────
        "task_name":   "hard",
        "grid_width":  20,
        "grid_height": 20,
        "max_steps":   500,

        # ── Drones ───────────────────────────────────────────────────────
        # drone_4 (70%) and drone_5 (55%) are battery-degraded.
        # Suggested zone coverage:
        #   drone_0 → north tasks (rows 0-4)
        #   drone_1 → north-mid tasks (rows 1-5)
        #   drone_2 → north-east tasks
        #   drone_3 → mid tasks (rows 5-9)
        #   drone_4 → mid-south tasks — budget RTB early (70%)
        #   drone_5 → south tasks — recharge first (55%)
        "drones": [
            {"id": "drone_0", "start_x": 0,  "start_y": 0,  "battery": 100.0},
            {"id": "drone_1", "start_x": 2,  "start_y": 0,  "battery": 100.0},
            {"id": "drone_2", "start_x": 10, "start_y": 0,  "battery": 100.0},
            {"id": "drone_3", "start_x": 0,  "start_y": 5,  "battery": 100.0},
            {"id": "drone_4", "start_x": 10, "start_y": 7,  "battery":  70.0},  # degraded
            {"id": "drone_5", "start_x": 0,  "start_y": 14, "battery":  55.0},  # critically low
        ],

        # ── Tasks ─────────────────────────────────────────────────────────
        # Priority: 3=URGENT | 2=EXPRESS | 1=normal
        # Drone picks directly from pickup (shelf) → flies to delivery.
        "tasks": [
            # ── URGENT (priority 3) ──────────────────────────────────────
            {
                "id":       "task_0",
                "item":     "Urgent Medicine",
                "pickup":   {"x": 3,  "y": 1,  "z": 0},
                "delivery": {"x": 18, "y": 1,  "z": 0},
                "priority": 3,
            },
            {
                "id":       "task_1",
                "item":     "Frozen Food",
                "pickup":   {"x": 4,  "y": 3,  "z": 0},
                "delivery": {"x": 19, "y": 4,  "z": 0},
                "priority": 3,
            },
            {
                "id":       "task_2",
                "item":     "Baby Supplies",
                "pickup":   {"x": 2,  "y": 2,  "z": 0},
                "delivery": {"x": 16, "y": 19, "z": 0},
                "priority": 3,
            },

            # ── EXPRESS (priority 2) ─────────────────────────────────────
            {
                "id":       "task_3",
                "item":     "Electronics Bundle",
                "pickup":   {"x": 3,  "y": 10, "z": 0},
                "delivery": {"x": 17, "y": 6,  "z": 0},
                "priority": 2,
            },
            {
                "id":       "task_4",
                "item":     "Smart Device",
                "pickup":   {"x": 5,  "y": 1,  "z": 0},
                "delivery": {"x": 15, "y": 18, "z": 0},
                "priority": 2,
            },
            {
                "id":       "task_5",
                "item":     "Tools Kit",
                "pickup":   {"x": 5,  "y": 3,  "z": 0},
                "delivery": {"x": 18, "y": 18, "z": 0},
                "priority": 2,
            },
            {
                "id":       "task_6",
                "item":     "Fragile Glassware",
                "pickup":   {"x": 3,  "y": 6,  "z": 0},
                "delivery": {"x": 19, "y": 15, "z": 0},
                "priority": 2,
            },

            # ── NORMAL (priority 1) ──────────────────────────────────────
            {
                "id":       "task_7",
                "item":     "Clothing Set",
                "pickup":   {"x": 4,  "y": 7,  "z": 0},
                "delivery": {"x": 16, "y": 14, "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_8",
                "item":     "Books Order",
                "pickup":   {"x": 2,  "y": 7,  "z": 0},
                "delivery": {"x": 17, "y": 17, "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_9",
                "item":     "Sports Equipment",
                "pickup":   {"x": 4,  "y": 13, "z": 0},
                "delivery": {"x": 18, "y": 17, "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_10",
                "item":     "Furniture Part",
                "pickup":   {"x": 4,  "y": 6,  "z": 0},
                "delivery": {"x": 14, "y": 3,  "z": 0},
                "priority": 1,
            },
            {
                "id":       "task_11",
                "item":     "Office Supplies",
                "pickup":   {"x": 5,  "y": 11, "z": 0},
                "delivery": {"x": 17, "y": 12, "z": 0},
                "priority": 1,
            },
        ],

        # ── Map Geometry ──────────────────────────────────────────────────
        # NOTE: Obstacles only block drones at z=0.
        # Drones always fly at z=1 over them during transit — obstacle
        # awareness still matters for proximity/TTC reward shaping.
        "obstacles": [
            # Horizontal shelf row wall (y=8, x=0..7)
            (0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (6, 8), (7, 8),

            # Vertical corridor wall (x=8) — full column
            (8, 0),  (8, 1),  (8, 2),  (8, 3),  (8, 4),
            (8, 5),  (8, 6),  (8, 7),  (8, 8),
            (8, 9),  (8, 10), (8, 11), (8, 12), (8, 13),
            (8, 14), (8, 15), (8, 16), (8, 17), (8, 18), (8, 19),

            # Internal pillars — south pick zone (y=12)
            (0, 12), (2, 12), (4, 12),
        ],

        # Four charging stations
        "charging_stations": [
            (0,  19),   # drone pad SW
            (5,  19),   # drone pad SC
            (10,  0),   # drone pad N
            (10, 19),   # drone pad S
        ],
    }
