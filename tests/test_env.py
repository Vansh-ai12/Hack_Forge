"""
AeroSync AI — Test Suite (Drone-Only)
Validates OpenEnv compliance: reset(), step(), state(), graders, models,
drone-specific actions, rich reward components, and grid map.

Run: python -m pytest tests/test_env.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from env.aerosync_env import AeroSyncEnv
from env.models import (
    AeroSyncAction, AeroSyncObservation, AeroSyncReward,
    DroneAgentState, AgentType, TaskStatus, FlightMode,
    Position, DroneTiltState, ActionType,
)
from grader.grader import grade, detailed_report
from tasks.easy   import get_config as easy_config
from tasks.medium import get_config as medium_config
from tasks.hard   import get_config as hard_config


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def easy_env():
    env = AeroSyncEnv(easy_config())
    env.reset()
    return env

@pytest.fixture
def medium_env():
    env = AeroSyncEnv(medium_config())
    env.reset()
    return env

@pytest.fixture
def hard_env():
    env = AeroSyncEnv(hard_config())
    env.reset()
    return env


# ─────────────────────────────────────────────
# OpenEnv API Compliance
# ─────────────────────────────────────────────

class TestOpenEnvAPI:

    def test_reset_returns_observation(self, easy_env):
        obs = easy_env.reset()
        assert isinstance(obs, AeroSyncObservation)
        assert obs.step == 0
        assert not obs.done

    def test_state_returns_dict(self, easy_env):
        s = easy_env.state()
        assert isinstance(s, dict)
        assert "step" in s
        assert "tasks" in s
        assert "drone_states" in s

    def test_step_returns_tuple(self, easy_env):
        # Use drone_0 for easy task
        action = AeroSyncAction(agent_id="drone_0", action_type=ActionType.WAIT)
        obs, reward, done, info = easy_env.step(action)
        assert isinstance(obs, AeroSyncObservation)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert hasattr(info, "reward_breakdown")

    def test_step_increments_step(self, easy_env):
        assert easy_env.state()["step"] == 0
        easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.WAIT))
        assert easy_env.state()["step"] == 1

    def test_reset_restores_clean_state(self, easy_env):
        for _ in range(5):
            easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.WAIT))
        assert easy_env.state()["step"] == 5
        obs = easy_env.reset()
        assert obs.step == 0
        assert easy_env.state()["step"] == 0

    def test_observation_has_grid(self, easy_env):
        obs = easy_env.reset()
        assert hasattr(obs, "grid")
        assert isinstance(obs.grid, dict)
        assert len(obs.grid) > 0

    def test_observation_has_drone_states(self, easy_env):
        obs = easy_env.reset()
        assert hasattr(obs, "drone_states")
        assert len(obs.drone_states) >= 1
        drone = list(obs.drone_states.values())[0]
        assert isinstance(drone, DroneAgentState)


# ─────────────────────────────────────────────
# Typed Models
# ─────────────────────────────────────────────

class TestTypedModels:

    def test_observation_is_pydantic(self, easy_env):
        obs = easy_env.reset()
        d = obs.model_dump()
        assert isinstance(d, dict)
        assert "drone_states" in d
        assert "grid" in d

    def test_drone_action_typed(self):
        a = AeroSyncAction(agent_id="drone_0", action_type=ActionType.HOVER)
        assert a.action_type == ActionType.HOVER

    def test_battery_bounded(self, easy_env):
        obs = easy_env.reset()
        for drone in obs.drone_states.values():
            assert 0.0 <= drone.battery <= 100.0

    def test_drone_has_flight_params(self, easy_env):
        obs = easy_env.reset()
        drone = list(obs.drone_states.values())[0]
        assert hasattr(drone, "flight")
        assert hasattr(drone.flight, "hover_stability_score")
        assert hasattr(drone.flight, "tilt")
        assert isinstance(drone.flight.tilt, DroneTiltState)

    def test_drone_has_diagnostics(self, easy_env):
        obs = easy_env.reset()
        drone = list(obs.drone_states.values())[0]
        assert hasattr(drone, "diagnostics")
        assert hasattr(drone.diagnostics, "nearest_obstacle_dist")


# ─────────────────────────────────────────────
# Task Configs
# ─────────────────────────────────────────────

class TestTaskConfigs:

    def test_easy_has_correct_agents(self):
        cfg = easy_config()
        assert len(cfg.get("robots", [])) == 0  # Should be 0 in drone-only
        assert len(cfg["drones"]) == 2
        assert len(cfg["tasks"]) == 2

    def test_medium_has_correct_agents(self):
        cfg = medium_config()
        assert len(cfg["drones"]) == 3
        assert len(cfg["tasks"]) == 6

    def test_delivery_locations_are_ground_level(self):
        for get_cfg in [easy_config, medium_config, hard_config]:
            cfg = get_cfg()
            for t in cfg["tasks"]:
                assert t["delivery"].get("z", 0) == 0


# ─────────────────────────────────────────────
# Drone Mechanics
# ─────────────────────────────────────────────

class TestDroneMechanics:

    def test_drone_starts_at_altitude_1(self, easy_env):
        obs = easy_env.reset()
        drone = obs.drone_states["drone_0"]
        assert drone.position.z == 1

    def test_drone_hover_changes_flight_mode(self, easy_env):
        easy_env.reset()
        obs, _, _, _ = easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.HOVER))
        drone = obs.drone_states["drone_0"]
        assert drone.flight.flight_mode == FlightMode.HOVER

    def test_drone_ascend_increases_altitude(self, easy_env):
        easy_env.reset()
        easy_env._drone_states["drone_0"].position.z = 1
        obs, _, _, _ = easy_env.step(AeroSyncAction(
            agent_id="drone_0", action_type=ActionType.ASCEND, target_altitude=3
        ))
        assert obs.drone_states["drone_0"].position.z == 2

    def test_drone_descend_decreases_altitude(self, easy_env):
        easy_env.reset()
        easy_env._drone_states["drone_0"].position.z = 2
        obs, _, _, _ = easy_env.step(AeroSyncAction(
            agent_id="drone_0", action_type=ActionType.DESCEND, target_altitude=0
        ))
        assert obs.drone_states["drone_0"].position.z == 1

    def test_drone_battery_drains_on_move(self, easy_env):
        easy_env.reset()
        start_bat = easy_env._drone_states["drone_0"].battery
        easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.MOVE, direction="east"))
        assert easy_env._drone_states["drone_0"].battery < start_bat

    def test_drone_rtb_fires_rtb_event(self, easy_env):
        easy_env.reset()
        # Drain battery to force RTB or just call action
        _, _, _, info = easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.RETURN_TO_BASE))
        # RTB event is added to drone_rtb_events list in EpisodeInfo
        assert "drone_0" in info.drone_rtb_events

    def test_drone_pick_works_on_ground(self, easy_env):
        easy_env.reset()
        # Move to pickup location and descend
        task = easy_env._tasks["task_0"]
        drone = easy_env._drone_states["drone_0"]
        drone.position.x = task.pickup_location.x
        drone.position.y = task.pickup_location.y
        drone.position.z = 0
        
        easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.PICK, task_id="task_0"))
        assert drone.carrying_task_id == "task_0"
        assert task.status == TaskStatus.IN_FLIGHT


# ─────────────────────────────────────────────
# Reward & Grader
# ─────────────────────────────────────────────

class TestRewardAndGrader:

    def test_reward_is_float(self, easy_env):
        _, reward, _, _ = easy_env.step(AeroSyncAction(agent_id="drone_0", action_type=ActionType.WAIT))
        assert isinstance(reward, float)

    def test_score_in_range(self):
        for get_cfg in [easy_config, medium_config, hard_config]:
            env = AeroSyncEnv(get_cfg())
            env.reset()
            env.step(AeroSyncAction(agent_id=list(env._drone_states.keys())[0], action_type=ActionType.WAIT))
            s = grade(env.state())
            assert 0.0 <= s <= 1.0

    def test_collision_reduces_score(self, easy_env):
        easy_env.reset()
        s1 = grade(easy_env.state())
        easy_env._collision_count = 5
        s2 = grade(easy_env.state())
        assert s2 < s1

    def test_full_delivery_gives_high_score(self, easy_env):
        easy_env.reset()
        for task in easy_env._tasks.values():
            task.status = TaskStatus.DELIVERED
            task.completed_at_step = 10
        easy_env._step = 30
        s = grade(easy_env.state())
        assert s > 0.7


# ─────────────────────────────────────────────
# BFS Pathfinder
# ─────────────────────────────────────────────

class TestBFS:

    def test_bfs_finds_path(self, easy_env):
        start = Position(x=0, y=0)
        goal  = Position(x=3, y=3)
        # Needs agent_type
        path = easy_env.bfs_path(start, goal, agent_type=AgentType.DRONE)
        assert len(path) > 0
        assert len(path) == 6  # Manhattan distance
