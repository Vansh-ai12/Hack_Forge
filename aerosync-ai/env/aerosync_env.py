"""
AeroSync AI — Core Environment
OpenEnv-compliant: reset() / step() / state()

Grid layout (z=0 ground, z=1 air):
  - Robots move on z=0 only
  - Drones move on z=1 only (over obstacles)
  - Dispatch zones are at fixed ground positions
  - Charging stations on ground for robots, elevated pads for drones
"""
from __future__ import annotations
import copy
import random
from typing import Any, Dict, List, Optional, Tuple

from env.models import (
    AgentState, AgentType, AeroSyncAction, AeroSyncObservation,
    AeroSyncReward, ActionType, Direction, EpisodeInfo,
    Position, TaskState, TaskStatus,
)


R_DELIVERY   =  20.0
R_DISPATCH   =  10.0
R_PICKUP     =   5.0
P_COLLISION  = -30.0
P_BATTERY    = -50.0
P_DELAY      =  -0.05   # per step while tasks are pending
P_IDLE       =  -0.02   # per idle agent per step



class AeroSyncEnv:
    """
    AeroSync AI logistics environment.

    Pipeline:
        Task created → Robot picks item → Robot carries to dispatch →
        Drone picks from dispatch → Drone delivers to customer → Done
    """

    def __init__(self, task_config: Dict[str, Any]):
        """
        task_config keys:
          grid_width, grid_height, max_steps, task_name,
          robots: [{id, start_x, start_y, battery}]
          drones: [{id, start_x, start_y, battery}]
          tasks:  [{id, item, pickup, dispatch, delivery, priority}]
          obstacles: [(x,y)]
          dispatch_zones: [(x,y)]
          charging_stations: [(x,y)]
        """
        self.config = task_config
        self._initial_config = copy.deepcopy(task_config)

        # Grid dimensions
        self.W = task_config["grid_width"]
        self.H = task_config["grid_height"]
        self.max_steps = task_config["max_steps"]
        self.task_name = task_config.get("task_name", "unknown")

        # Immutable geometry
        self.obstacles: set = set(tuple(o) for o in task_config.get("obstacles", []))
        self.dispatch_zones: set = set(tuple(d) for d in task_config.get("dispatch_zones", []))
        self.charging_positions: List[Position] = [
            Position(x=c[0], y=c[1], z=0)
            for c in task_config.get("charging_stations", [])
        ]

        # Mutable state (initialised in reset)
        self._step: int = 0
        self._agents: Dict[str, AgentState] = {}
        self._tasks: Dict[str, TaskState] = {}
        self._dispatch_queue: List[str] = []
        self._episode_rewards: List[float] = []
        self._collision_count: int = 0
        self._battery_failures: int = 0

    # ─────────────────────────────────────────────
    # OpenEnv API
    # ─────────────────────────────────────────────

    def reset(self) -> AeroSyncObservation:
        """Reset environment to initial state. Returns first observation."""
        cfg = copy.deepcopy(self._initial_config)
        self._step = 0
        self._dispatch_queue = []
        self._episode_rewards = []
        self._collision_count = 0
        self._battery_failures = 0

        # Initialise agents
        self._agents = {}
        for r in cfg.get("robots", []):
            self._agents[r["id"]] = AgentState(
                agent_id=r["id"],
                agent_type=AgentType.ROBOT,
                position=Position(x=r["start_x"], y=r["start_y"], z=0),
                battery=r.get("battery", 100.0),
            )
        for d in cfg.get("drones", []):
            self._agents[d["id"]] = AgentState(
                agent_id=d["id"],
                agent_type=AgentType.DRONE,
                position=Position(x=d["start_x"], y=d["start_y"], z=1),
                battery=d.get("battery", 100.0),
            )

        # Initialise tasks
        self._tasks = {}
        for t in cfg.get("tasks", []):
            self._tasks[t["id"]] = TaskState(
                task_id=t["id"],
                item_name=t["item"],
                pickup_location=Position(**t["pickup"]),
                dispatch_location=Position(**t["dispatch"]),
                delivery_location=Position(**t["delivery"]),
                priority=t.get("priority", 1),
            )

        return self._build_observation(reward=0.0)

    def step(self, action: AeroSyncAction) -> Tuple[AeroSyncObservation, float, bool, EpisodeInfo]:
        """
        Execute one action for one agent.
        Returns (observation, reward, done, info)
        """
        reward_breakdown = AeroSyncReward()
        info = EpisodeInfo()

        self._step += 1

        # ── Validate agent ──────────────────────────────
        agent = self._agents.get(action.agent_id)
        if agent is None:
            info.message = f"Unknown agent: {action.agent_id}"
            obs = self._build_observation(reward=0.0)
            return obs, 0.0, self._is_done(), info

        # ── Increment personal step counter ───────────
        agent.steps_taken += 1

        # ── Battery failure check ─────────────────────
        if agent.battery <= 15.0 and action.action_type != ActionType.CHARGE:
            reward_breakdown.battery_penalty += P_BATTERY
            info.battery_failures.append(action.agent_id)
            self._battery_failures += 1
            agent.is_idle = True
            agent.carrying_task_id = None
            total = reward_breakdown.total + P_BATTERY
            self._episode_rewards.append(total)
            obs = self._build_observation(reward=total)
            return obs, total, self._is_done(), info

        # ── Execute action ────────────────────────────
        act = action.action_type

        if act == ActionType.MOVE:
            r, col = self._do_move(agent, action.direction, reward_breakdown, info)
            reward_breakdown = r
            info = col

        elif act == ActionType.PICK:
            reward_breakdown = self._do_pick(agent, action.task_id, reward_breakdown, info)

        elif act == ActionType.PLACE:
            reward_breakdown = self._do_place(agent, reward_breakdown, info)

        elif act == ActionType.CHARGE:
            self._do_charge(agent)

        elif act == ActionType.ASSIGN_TASK:
            self._do_assign(agent, action.task_id)

        elif act == ActionType.WAIT:
            pass  # intentional no-op

        # ── Passive decay ─────────────────────────────
        if not agent.is_charging:
            drain = 0.5 if agent.agent_type == AgentType.DRONE else 0.3
            agent.battery = max(0.0, agent.battery - drain)

        # ── Delay penalty ─────────────────────────────
        pending = sum(1 for t in self._tasks.values()
                      if t.status not in (TaskStatus.DELIVERED, TaskStatus.FAILED))
        reward_breakdown.delay_penalty += P_DELAY * pending

        # ── Idle penalty ──────────────────────────────
        idle_agents = sum(1 for a in self._agents.values() if a.is_idle and a.battery > 0)
        reward_breakdown.idle_penalty += P_IDLE * idle_agents

        # ── Total reward ──────────────────────────────
        total_reward = (
            reward_breakdown.delivery_bonus
            + reward_breakdown.dispatch_bonus
            + reward_breakdown.pickup_bonus
            + reward_breakdown.collision_penalty
            + reward_breakdown.battery_penalty
            + reward_breakdown.delay_penalty
            + reward_breakdown.idle_penalty
        )
        reward_breakdown.total = total_reward
        info.reward_breakdown = reward_breakdown

        self._episode_rewards.append(total_reward)
        done = self._is_done()
        obs = self._build_observation(reward=total_reward)
        return obs, total_reward, done, info

    def state(self) -> Dict[str, Any]:
        """Return raw environment state as a plain dict."""
        return {
            "step": self._step,
            "max_steps": self.max_steps,
            "task_name": self.task_name,
            "agents": {k: v.model_dump() for k, v in self._agents.items()},
            "tasks": {k: v.model_dump() for k, v in self._tasks.items()},
            "dispatch_queue": list(self._dispatch_queue),
            "collision_count": self._collision_count,
            "battery_failures": self._battery_failures,
            "episode_rewards": list(self._episode_rewards),
            "grid": {"width": self.W, "height": self.H},
        }



    def _do_move(self, agent: AgentState, direction: Optional[str],
                 rb: AeroSyncReward, info: EpisodeInfo
                 ) -> Tuple[AeroSyncReward, EpisodeInfo]:
        if direction is None:
            return rb, info

        dx, dy, dz = 0, 0, 0
        if direction == Direction.NORTH or direction == "north": dy = -1
        elif direction == Direction.SOUTH or direction == "south": dy = 1
        elif direction == Direction.EAST or direction == "east":  dx = 1
        elif direction == Direction.WEST or direction == "west":  dx = -1
        elif direction == Direction.UP or direction == "up":      dz = 1
        elif direction == Direction.DOWN or direction == "down":  dz = -1

        nx = agent.position.x + dx
        ny = agent.position.y + dy
        nz = agent.position.z + dz

        # Boundary check
        if not (0 <= nx < self.W and 0 <= ny < self.H):
            return rb, info  # blocked by boundary, no penalty

        # Robots stay on z=0, drones on z=1
        if agent.agent_type == AgentType.ROBOT and nz != 0:
            return rb, info
        if agent.agent_type == AgentType.DRONE and nz not in (1,):
            nz = 1  # drones always stay at altitude 1

        # Obstacle check (ground level only — drones fly over)

        if agent.agent_type == AgentType.ROBOT and (nx, ny) in self.obstacles:
            rb.collision_penalty += P_COLLISION          
            info.collision_events.append(
        f"{agent.agent_id} collided with obstacle at ({nx},{ny},{nz})"
    )                                            
            self._collision_count += 1                
            return rb, info                             

        # Collision check with other agents at same type layer
        for other_id, other in self._agents.items():
            if other_id == agent.agent_id:
                continue
            if (other.position.x == nx and other.position.y == ny and
                    other.position.z == nz):
                # Collision!
                rb.collision_penalty += P_COLLISION
                info.collision_events.append(
                    f"{agent.agent_id} collided with {other_id} at ({nx},{ny},{nz})"
                )
                self._collision_count += 1
                return rb, info

        agent.position = Position(x=nx, y=ny, z=nz)
        agent.is_idle = False
        return rb, info

    def _do_pick(self, agent: AgentState, task_id: Optional[str],
                 rb: AeroSyncReward, info: EpisodeInfo) -> AeroSyncReward:
        if task_id is None or agent.carrying_task_id is not None:
            return rb

        task = self._tasks.get(task_id)
        if task is None:
            return rb

        ax, ay = agent.position.x, agent.position.y

        if agent.agent_type == AgentType.ROBOT:
            # Robot picks from warehouse shelf
            if (task.status == TaskStatus.PENDING and
                    task.assigned_robot == agent.agent_id and
                    ax == task.pickup_location.x and
                    ay == task.pickup_location.y):
                task.status = TaskStatus.PICKED
                agent.carrying_task_id = task_id
                agent.is_idle = False
                rb.pickup_bonus += R_PICKUP
                info.message = f"{agent.agent_id} picked task {task_id}"

        elif agent.agent_type == AgentType.DRONE:
            # Drone picks from dispatch zone
            if (task.status == TaskStatus.DISPATCHED and
                    task_id in self._dispatch_queue and
                    (ax, ay) in self.dispatch_zones):
                task.status = TaskStatus.IN_FLIGHT
                task.assigned_drone = agent.agent_id
                agent.carrying_task_id = task_id
                agent.is_idle = False
                self._dispatch_queue.remove(task_id)
                rb.pickup_bonus += R_PICKUP

        return rb

    def _do_place(self, agent: AgentState,
                  rb: AeroSyncReward, info: EpisodeInfo) -> AeroSyncReward:
        if agent.carrying_task_id is None:
            return rb

        task = self._tasks.get(agent.carrying_task_id)
        if task is None:
            return rb

        ax, ay = agent.position.x, agent.position.y

        if agent.agent_type == AgentType.ROBOT:
            # Robot places at dispatch
            if (task.status == TaskStatus.PICKED and
                    (ax, ay) in self.dispatch_zones):
                task.status = TaskStatus.DISPATCHED
                self._dispatch_queue.append(agent.carrying_task_id)
                agent.carrying_task_id = None
                agent.is_idle = True
                rb.dispatch_bonus += R_DISPATCH
                info.message = f"Task {task.task_id} dispatched"

        elif agent.agent_type == AgentType.DRONE:
            # Drone delivers to customer
            if (task.status == TaskStatus.IN_FLIGHT and
                    ax == task.delivery_location.x and
                    ay == task.delivery_location.y):
                task.status = TaskStatus.DELIVERED
                task.completed_at_step = self._step
                agent.carrying_task_id = None
                agent.is_idle = True
                rb.delivery_bonus += R_DELIVERY
                info.completed_tasks.append(task.task_id)
                info.message = f"Task {task.task_id} delivered!"

        return rb

    def _do_charge(self, agent: AgentState):
        """Charge agent if at a charging station position."""
        ax, ay = agent.position.x, agent.position.y
        at_station = any(
            c.x == ax and c.y == ay for c in self.charging_positions
        )
        if at_station:
            charge_rate = 15.0 if agent.agent_type == AgentType.DRONE else 20.0
            agent.battery = min(100.0, agent.battery + charge_rate)
            agent.is_charging = True
            agent.is_idle = True
        else:
            agent.is_charging = False

    def _do_assign(self, agent: AgentState, task_id: Optional[str]):
        """Assign a pending task to a robot."""
        if task_id is None or agent.agent_type != AgentType.ROBOT:
            return
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING and task.assigned_robot is None:
            task.assigned_robot = agent.agent_id
            agent.is_idle = False

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _is_done(self) -> bool:
        if self._step >= self.max_steps:
            return True
        all_done = all(
            t.status in (TaskStatus.DELIVERED, TaskStatus.FAILED)
            for t in self._tasks.values()
        )
        return all_done

    def _build_observation(self, reward: float) -> AeroSyncObservation:
        delivered = sum(1 for t in self._tasks.values() if t.status == TaskStatus.DELIVERED)
        total_tasks = len(self._tasks)
        completion = delivered / total_tasks if total_tasks > 0 else 0.0

        metrics = {
            "completion_rate": round(completion, 3),
            "collisions": float(self._collision_count),
            "battery_failures": float(self._battery_failures),
            "steps_used": float(self._step),
            "tasks_delivered": float(delivered),
            "tasks_total": float(total_tasks),
        }

        return AeroSyncObservation(
            step=self._step,
            max_steps=self.max_steps,
            agents=copy.deepcopy(self._agents),
            tasks=copy.deepcopy(self._tasks),
            dispatch_queue=list(self._dispatch_queue),
            charging_stations=list(self.charging_positions),
            grid_width=self.W,
            grid_height=self.H,
            reward=reward,
            done=self._is_done(),
            task_name=self.task_name,
            metrics=metrics,
        )

    # ─────────────────────────────────────────────
    # Utility: shortest path (BFS, ground or air)
    # ─────────────────────────────────────────────

    def bfs_path(self, start: Position, goal: Position,
                 agent_type: AgentType) -> List[str]:
        """Return list of direction strings for shortest path."""
        from collections import deque

        if start.x == goal.x and start.y == goal.y:
            return []

        visited = {(start.x, start.y)}
        queue: deque = deque([((start.x, start.y), [])])

        dirs = [("north", 0, -1), ("south", 0, 1),
                ("east", 1, 0), ("west", -1, 0)]

        while queue:
            (cx, cy), path = queue.popleft()
            for d_name, dx, dy in dirs:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < self.W and 0 <= ny < self.H):
                    continue
                if (nx, ny) in visited:
                    continue
                if agent_type == AgentType.ROBOT and (nx, ny) in self.obstacles:
                    continue
                new_path = path + [d_name]
                if nx == goal.x and ny == goal.y:
                    return new_path
                visited.add((nx, ny))
                queue.append(((nx, ny), new_path))
        return []  # no path found
