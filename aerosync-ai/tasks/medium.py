"""
Medium Task — AeroSync AI
3 robots + 2 drones, 6 delivery tasks, 15x15 grid with obstacles.
Battery drain matters. Two dispatch zones create coordination pressure.
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        "task_name": "medium",
        "grid_width": 15,
        "grid_height": 15,
        "max_steps": 250,

        # Agents — robots start near shelves, drones near dispatch
        "robots": [
            {"id": "robot_0", "start_x": 0,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_1", "start_x": 2,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_2", "start_x": 0,  "start_y": 2,  "battery": 100.0},
        ],
        "drones": [
            {"id": "drone_0", "start_x": 7,  "start_y": 2,  "battery": 80.0},
            {"id": "drone_1", "start_x": 7,  "start_y": 6,  "battery": 80.0},
        ],

        # Tasks
        "tasks": [
            {
                "id": "task_0",
                "item": "Electronics",
                "pickup":   {"x": 1, "y": 3, "z": 0},
                "dispatch": {"x": 7, "y": 3, "z": 0},
                "delivery": {"x": 13, "y": 1, "z": 1},
                "priority": 2,
            },
            {
                "id": "task_1",
                "item": "Clothing",
                "pickup":   {"x": 3, "y": 1, "z": 0},
                "dispatch": {"x": 7, "y": 3, "z": 0},
                "delivery": {"x": 12, "y": 5, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_2",
                "item": "Books",
                "pickup":   {"x": 1, "y": 5, "z": 0},
                "dispatch": {"x": 7, "y": 7, "z": 0},
                "delivery": {"x": 14, "y": 9, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_3",
                "item": "Groceries",
                "pickup":   {"x": 4, "y": 2, "z": 0},
                "dispatch": {"x": 7, "y": 7, "z": 0},
                "delivery": {"x": 11, "y": 13, "z": 1},
                "priority": 3,
            },
            {
                "id": "task_4",
                "item": "Medical Supplies",
                "pickup":   {"x": 2, "y": 4, "z": 0},
                "dispatch": {"x": 7, "y": 3, "z": 0},
                "delivery": {"x": 13, "y": 11, "z": 1},
                "priority": 3,
            },
            {
                "id": "task_5",
                "item": "Tools",
                "pickup":   {"x": 5, "y": 1, "z": 0},
                "dispatch": {"x": 7, "y": 7, "z": 0},
                "delivery": {"x": 14, "y": 14, "z": 1},
                "priority": 1,
            },
        ],

        # Map geometry — internal shelf rows create routing pressure
        "obstacles": [
            (6, 0), (6, 1), (6, 2), (6, 3), (6, 4),   # left warehouse wall
            (6, 8), (6, 9), (6, 10), (6, 11), (6, 12), # lower wall
        ],
        "dispatch_zones": [(7, 3), (7, 7)],
        "charging_stations": [(0, 14), (4, 14), (9, 0)],
    }
