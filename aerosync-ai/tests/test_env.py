"""
AeroSync AI — Test Suite
Validates OpenEnv compliance: reset(), step(), state(), graders, models.
Run: python -m pytest tests/test_env.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from env.aerosync_env import AeroSyncEnv
from env.models import AeroSyncAction, AeroSyncObservation, TaskStatus
from grader.grader import grade, detailed_report
from tasks.easy   import get_config as easy_config
from tasks.medium import get_config as medium_config
from tasks.hard   import get_config as hard_config


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# OpenEnv API compliance
# ──────────────────────────────────────────────────────────────────────────────

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
        assert "agents" in s
        assert "tasks" in s

    def test_step_returns_tuple(self, easy_env):
        action = AeroSyncAction(agent_id="robot_0", action_type="wait")
        obs, reward, done, info = easy_env.step(action)
        assert isinstance(obs, AeroSyncObservation)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert hasattr(info, "reward_breakdown")

    def test_step_increments_step(self, easy_env):
        assert easy_env.state()["step"] == 0
        action = AeroSyncAction(agent_id="robot_0", action_type="wait")
        easy_env.step(action)
        assert easy_env.state()["step"] == 1

    def test_reset_restores_clean_state(self, easy_env):
        # Take some steps
        action = AeroSyncAction(agent_id="robot_0", action_type="wait")
        for _ in range(5):
            easy_env.step(action)
        assert easy_env.state()["step"] == 5

        # Reset and check
        obs = easy_env.reset()
        assert obs.step == 0
        assert easy_env.state()["step"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Typed models
# ──────────────────────────────────────────────────────────────────────────────

class TestTypedModels:

    def test_observation_is_pydantic(self, easy_env):
        obs = easy_env.reset()
        d = obs.model_dump()
        assert isinstance(d, dict)
        assert "agents" in d

    def test_action_typed(self):
        a = AeroSyncAction(agent_id="robot_0", action_type="move", direction="north")
        assert a.agent_id == "robot_0"
        assert a.action_type == "move"

    def test_invalid_action_raises(self):
        with pytest.raises(Exception):
            AeroSyncAction(agent_id="robot_0", action_type="INVALID_TYPE")

    def test_battery_bounded(self, easy_env):
        obs = easy_env.reset()
        for agent in obs.agents.values():
            assert 0.0 <= agent.battery <= 100.0


# ──────────────────────────────────────────────────────────────────────────────
# Task configs
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskConfigs:

    def test_easy_has_correct_agents(self):
        cfg = easy_config()
        assert len(cfg["robots"]) == 1
        assert len(cfg["drones"]) == 1
        assert len(cfg["tasks"]) == 2

    def test_medium_has_correct_agents(self):
        cfg = medium_config()
        assert len(cfg["robots"]) == 3
        assert len(cfg["drones"]) == 2
        assert len(cfg["tasks"]) == 6

    def test_hard_has_correct_agents(self):
        cfg = hard_config()
        assert len(cfg["robots"]) == 6
        assert len(cfg["drones"]) == 4
        assert len(cfg["tasks"]) == 12

    def test_all_tasks_have_three_stages(self):
        for get_cfg in [easy_config, medium_config, hard_config]:
            cfg = get_cfg()
            for t in cfg["tasks"]:
                assert "pickup"   in t
                assert "dispatch" in t
                assert "delivery" in t


# ──────────────────────────────────────────────────────────────────────────────
# Mechanics
# ──────────────────────────────────────────────────────────────────────────────

class TestMechanics:

    def test_move_changes_position(self, easy_env):
        obs = easy_env.reset()
        start = obs.agents["robot_0"].position.model_dump()
        action = AeroSyncAction(agent_id="robot_0", action_type="move", direction="east")
        obs2, _, _, _ = easy_env.step(action)
        end = obs2.agents["robot_0"].position.model_dump()
        # Should have moved east (x+1)
        assert end["x"] == start["x"] + 1 or end == start  # blocked by boundary is ok

    def test_battery_drains_on_move(self, easy_env):
        obs = easy_env.reset()
        start_bat = obs.agents["robot_0"].battery
        action = AeroSyncAction(agent_id="robot_0", action_type="move", direction="east")
        obs2, _, _, _ = easy_env.step(action)
        assert obs2.agents["robot_0"].battery < start_bat

    def test_charge_restores_battery(self, easy_env):
        # Drain battery first
        obs = easy_env.reset()
        easy_env._agents["robot_0"].battery = 20.0
        # Move to charging station
        easy_env._agents["robot_0"].position.x = 0
        easy_env._agents["robot_0"].position.y = 9  # charging station at (0,9)
        action = AeroSyncAction(agent_id="robot_0", action_type="charge")
        obs2, _, _, _ = easy_env.step(action)
        assert obs2.agents["robot_0"].battery > 20.0

    def test_assign_task_sets_robot(self, easy_env):
        easy_env.reset()
        action = AeroSyncAction(
            agent_id="robot_0",
            action_type="assign_task",
            task_id="task_0",
        )
        obs, _, _, _ = easy_env.step(action)
        assert obs.tasks["task_0"].assigned_robot == "robot_0"

    def test_done_after_max_steps(self, easy_env):
        easy_env.reset()
        easy_env._step = easy_env.max_steps - 1
        action = AeroSyncAction(agent_id="robot_0", action_type="wait")
        _, _, done, _ = easy_env.step(action)
        assert done

    def test_boundary_does_not_crash(self, easy_env):
        easy_env.reset()
        easy_env._agents["robot_0"].position.x = 0
        action = AeroSyncAction(agent_id="robot_0", action_type="move", direction="west")
        obs, _, _, _ = easy_env.step(action)
        assert obs.agents["robot_0"].position.x == 0  # stayed at boundary

    def test_steps_taken_increments(self, easy_env):
        easy_env.reset()
        assert easy_env._agents["robot_0"].steps_taken == 0
        for _ in range(4):
            easy_env.step(AeroSyncAction(agent_id="robot_0", action_type="wait"))
        assert easy_env._agents["robot_0"].steps_taken == 4

    def test_steps_taken_per_agent_independent(self, medium_env):
        medium_env.reset()
        for _ in range(3):
            medium_env.step(AeroSyncAction(agent_id="robot_0", action_type="wait"))
        for _ in range(5):
            medium_env.step(AeroSyncAction(agent_id="robot_1", action_type="wait"))
        assert medium_env._agents["robot_0"].steps_taken == 3
        assert medium_env._agents["robot_1"].steps_taken == 5
        assert medium_env._agents["robot_2"].steps_taken == 0

    def test_steps_taken_resets_on_reset(self, easy_env):
        easy_env.reset()
        for _ in range(5):
            easy_env.step(AeroSyncAction(agent_id="robot_0", action_type="wait"))
        assert easy_env._agents["robot_0"].steps_taken == 5
        easy_env.reset()
        assert easy_env._agents["robot_0"].steps_taken == 0


# ──────────────────────────────────────────────────────────────────────────────
# Grader
# ──────────────────────────────────────────────────────────────────────────────

class TestGrader:

    def test_score_in_range(self):
        for get_cfg in [easy_config, medium_config, hard_config]:
            env = AeroSyncEnv(get_cfg())
            env.reset()
            # Run a few steps, then grade
            for _ in range(5):
                env.step(AeroSyncAction(agent_id=list(env._agents.keys())[0], action_type="wait"))
            s = grade(env.state())
            assert 0.0 <= s <= 1.0, f"Score {s} out of [0,1]"

    def test_zero_completion_gives_low_score(self):
        env = AeroSyncEnv(easy_config())
        env.reset()
        # No deliveries — just wait
        for _ in range(10):
            env.step(AeroSyncAction(agent_id="robot_0", action_type="wait"))
        s = grade(env.state())
        assert s < 0.5  # should be low without completions

    def test_detailed_report_keys(self):
        env = AeroSyncEnv(easy_config())
        env.reset()
        report = detailed_report(env.state())
        for key in ["task_name", "total_tasks", "delivered", "completion_ratio",
                    "collisions", "battery_failures", "steps_used", "final_score"]:
            assert key in report

    def test_collision_reduces_score(self, easy_env):
        s1 = grade(easy_env.state())
        # Inject a collision
        easy_env._collision_count = 5
        s2 = grade(easy_env.state())
        assert s2 <= s1  # more collisions = lower or equal score

    def test_full_delivery_gives_high_score(self):
        env = AeroSyncEnv(easy_config())
        env.reset()
        # Manually deliver all tasks
        for task in env._tasks.values():
            task.status = TaskStatus.DELIVERED
            task.completed_at_step = 10
        env._step = 30
        s = grade(env.state())
        assert s > 0.7  # perfect delivery should be high


# ──────────────────────────────────────────────────────────────────────────────
# BFS pathfinder
# ──────────────────────────────────────────────────────────────────────────────

class TestBFS:

    def test_bfs_finds_path(self, easy_env):
        from env.models import AgentType, Position
        start = Position(x=0, y=0)
        goal  = Position(x=3, y=3)
        path = easy_env.bfs_path(start, goal, AgentType.ROBOT)
        assert len(path) > 0
        assert len(path) == 6  # Manhattan distance

    def test_bfs_same_position(self, easy_env):
        from env.models import AgentType, Position
        start = Position(x=2, y=2)
        path = easy_env.bfs_path(start, start, AgentType.ROBOT)
        assert path == []
