"""
Hard Task — AeroSync AI
6 robots + 4 drones, 12 tasks, 20x20 grid.
Battery starts degraded on some agents.
3 dispatch zones that can congest.
Mixed priorities including 3 urgent tasks.
Obstacles create complex routing.
"""
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    return {
        "task_name": "hard",
        "grid_width": 20,
        "grid_height": 20,
        "max_steps": 500,

        # Agents — some start with degraded batteries
        "robots": [
            {"id": "robot_0", "start_x": 0,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_1", "start_x": 2,  "start_y": 0,  "battery": 100.0},
            {"id": "robot_2", "start_x": 4,  "start_y": 0,  "battery": 60.0},  # degraded
            {"id": "robot_3", "start_x": 0,  "start_y": 2,  "battery": 100.0},
            {"id": "robot_4", "start_x": 2,  "start_y": 3,  "battery": 80.0},
            {"id": "robot_5", "start_x": 1,  "start_y": 4,  "battery": 45.0},  # critically low
        ],
        "drones": [
            {"id": "drone_0", "start_x": 10, "start_y": 0,  "battery": 100.0},
            {"id": "drone_1", "start_x": 10, "start_y": 5,  "battery": 70.0},  # degraded
            {"id": "drone_2", "start_x": 10, "start_y": 10, "battery": 100.0},
            {"id": "drone_3", "start_x": 10, "start_y": 15, "battery": 55.0},  # degraded
        ],

        # 12 tasks with mixed priorities
        "tasks": [
            {
                "id": "task_0",
                "item": "Urgent Medicine",
                "pickup":   {"x": 1,  "y": 2,  "z": 0},
                "dispatch": {"x": 9,  "y": 4,  "z": 0},
                "delivery": {"x": 18, "y": 1,  "z": 1},
                "priority": 3,
            },
            {
                "id": "task_1",
                "item": "Electronics Bundle",
                "pickup":   {"x": 3,  "y": 1,  "z": 0},
                "dispatch": {"x": 9,  "y": 4,  "z": 0},
                "delivery": {"x": 17, "y": 6,  "z": 1},
                "priority": 2,
            },
            {
                "id": "task_2",
                "item": "Frozen Food",
                "pickup":   {"x": 2,  "y": 3,  "z": 0},
                "dispatch": {"x": 9,  "y": 9,  "z": 0},
                "delivery": {"x": 19, "y": 10, "z": 1},
                "priority": 3,
            },
            {
                "id": "task_3",
                "item": "Clothing Set",
                "pickup":   {"x": 4,  "y": 2,  "z": 0},
                "dispatch": {"x": 9,  "y": 9,  "z": 0},
                "delivery": {"x": 16, "y": 14, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_4",
                "item": "Books Order",
                "pickup":   {"x": 1,  "y": 5,  "z": 0},
                "dispatch": {"x": 9,  "y": 14, "z": 0},
                "delivery": {"x": 17, "y": 18, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_5",
                "item": "Tools Kit",
                "pickup":   {"x": 3,  "y": 4,  "z": 0},
                "dispatch": {"x": 9,  "y": 4,  "z": 0},
                "delivery": {"x": 18, "y": 4,  "z": 1},
                "priority": 2,
            },
            {
                "id": "task_6",
                "item": "Smart Device",
                "pickup":   {"x": 5,  "y": 1,  "z": 0},
                "dispatch": {"x": 9,  "y": 9,  "z": 0},
                "delivery": {"x": 15, "y": 8,  "z": 1},
                "priority": 2,
            },
            {
                "id": "task_7",
                "item": "Fragile Glassware",
                "pickup":   {"x": 2,  "y": 6,  "z": 0},
                "dispatch": {"x": 9,  "y": 9,  "z": 0},
                "delivery": {"x": 19, "y": 15, "z": 1},
                "priority": 2,
            },
            {
                "id": "task_8",
                "item": "Baby Supplies",
                "pickup":   {"x": 4,  "y": 5,  "z": 0},
                "dispatch": {"x": 9,  "y": 14, "z": 0},
                "delivery": {"x": 16, "y": 19, "z": 1},
                "priority": 3,
            },
            {
                "id": "task_9",
                "item": "Sports Equipment",
                "pickup":   {"x": 1,  "y": 7,  "z": 0},
                "dispatch": {"x": 9,  "y": 14, "z": 0},
                "delivery": {"x": 18, "y": 16, "z": 1},
                "priority": 1,
            },
            {
                "id": "task_10",
                "item": "Furniture Part",
                "pickup":   {"x": 5,  "y": 3,  "z": 0},
                "dispatch": {"x": 9,  "y": 4,  "z": 0},
                "delivery": {"x": 14, "y": 3,  "z": 1},
                "priority": 1,
            },
            {
                "id": "task_11",
                "item": "Office Supplies",
                "pickup":   {"x": 3,  "y": 6,  "z": 0},
                "dispatch": {"x": 9,  "y": 9,  "z": 0},
                "delivery": {"x": 17, "y": 12, "z": 1},
                "priority": 1,
            },
        ],

        # Map geometry — warehouse corridors + dispatch wall
        "obstacles": [
            # Warehouse shelf rows (horizontal)
            (0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (6, 8), (7, 8),
            # Dispatch corridor wall
            (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5),
            (8, 6), (8, 7), (8, 8),
            (8, 10), (8, 11), (8, 12), (8, 13), (8, 14), (8, 15),
            (8, 16), (8, 17), (8, 18), (8, 19),
            # Internal pillars
            (3, 10), (3, 11),
            (5, 13), (5, 14),
        ],
        "dispatch_zones": [(9, 4), (9, 9), (9, 14)],
        "charging_stations": [
            (0, 19),   # bottom-left for robots
            (6, 19),   # mid bottom for robots
            (11, 0),   # drone pad 1
            (11, 19),  # drone pad 2
        ],
    }
