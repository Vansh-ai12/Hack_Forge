"""
Easy Task — AeroSync AI
1 robot + 1 drone, 2 delivery tasks, open 10x10 grid
No battery pressure, no obstacles, minimal coordination needed.
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        "task_name": "easy",
        "grid_width": 10,
        "grid_height": 10,
        "max_steps": 120,

        # Agents
        "robots": [
            {"id": "robot_0", "start_x": 0, "start_y": 0, "battery": 100.0},
        ],
        "drones": [
            {"id": "drone_0", "start_x": 5, "start_y": 0, "battery": 100.0},
        ],

        # Tasks
        "tasks": [
            {
                "id": "task_0",
                "item": "Small Package",
                "pickup":   {"x": 1, "y": 2, "z": 0},
                "dispatch": {"x": 4, "y": 4, "z": 0},
                "delivery": {"x": 8, "y": 8, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_1",
                "item": "Documents",
                "pickup":   {"x": 2, "y": 1, "z": 0},
                "dispatch": {"x": 4, "y": 4, "z": 0},
                "delivery": {"x": 9, "y": 2, "z": 1},
                "priority": 1,
            },
        ],

        # Map geometry
        "obstacles": [],
        "dispatch_zones": [(4, 4)],
        "charging_stations": [(0, 9), (9, 9)],
    }
