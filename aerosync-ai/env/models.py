"""
AeroSync AI - Typed Pydantic Models
OpenEnv compliant: Observation, Action, Reward
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class AgentType(str, Enum):
    ROBOT = "robot"
    DRONE = "drone"


class TaskStatus(str, Enum):
    PENDING    = "pending"
    PICKED     = "picked"         
    DISPATCHED = "dispatched"     # Robot delivered item to dispatch zone
    IN_FLIGHT  = "in_flight"      # Drone carrying item to customer
    DELIVERED  = "delivered"      # Final delivery complete
    FAILED     = "failed"


class ActionType(str, Enum):
    MOVE        = "move"
    PICK        = "pick"
    PLACE       = "place"
    CHARGE      = "charge"
    WAIT        = "wait"
    ASSIGN_TASK = "assign_task"


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST  = "east"
    WEST  = "west"
    UP    = "up"     # drones only
    DOWN  = "down"   # drones only


# ─────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────

class Position(BaseModel):
    x: int = Field(..., description="X coordinate on grid")
    y: int = Field(..., description="Y coordinate on grid")
    z: int = Field(0, description="Z level: 0=ground, 1=air")


class AgentState(BaseModel):
    agent_id: str              = Field(..., description="Unique agent identifier")
    agent_type: AgentType      = Field(..., description="robot or drone")
    position: Position         = Field(..., description="Current position")
    battery: float             = Field(..., ge=0.0, le=100.0, description="Battery level 0-100")
    carrying_task_id: Optional[str] = Field(None, description="Task ID being carried, if any")
    is_charging: bool          = Field(False, description="Currently at charging station")
    is_idle: bool              = Field(True, description="No current assignment")
    steps_taken: int           = Field(0, description="Steps taken this episode")


class TaskState(BaseModel):
    task_id: str               = Field(..., description="Unique task identifier")
    status: TaskStatus         = Field(TaskStatus.PENDING)
    item_name: str             = Field(..., description="Name of the item")
    pickup_location: Position  = Field(..., description="Warehouse shelf location")
    dispatch_location: Position= Field(..., description="Dispatch / handoff zone")
    delivery_location: Position= Field(..., description="Customer delivery point")
    assigned_robot: Optional[str] = Field(None)
    assigned_drone: Optional[str] = Field(None)
    created_at_step: int       = Field(0)
    completed_at_step: Optional[int] = Field(None)
    priority: int              = Field(1, ge=1, le=3, description="1=normal, 2=express, 3=urgent")


class GridCell(BaseModel):
    x: int
    y: int
    z: int
    is_obstacle: bool   = False
    is_dispatch: bool   = False
    is_charging: bool   = False
    is_shelf: bool      = False
    occupant_id: Optional[str] = None   # agent currently on this cell


# ─────────────────────────────────────────────
# OpenEnv Core Models
# ─────────────────────────────────────────────

class AeroSyncObservation(BaseModel):
    """Full observation returned by reset() and step()"""
    step: int                             = Field(..., description="Current step number")
    max_steps: int                        = Field(..., description="Max steps per episode")
    agents: Dict[str, AgentState]         = Field(..., description="All agents keyed by ID")
    tasks: Dict[str, TaskState]           = Field(..., description="All tasks keyed by ID")
    dispatch_queue: List[str]             = Field(default_factory=list, description="Task IDs waiting at dispatch for drone pickup")
    charging_stations: List[Position]     = Field(default_factory=list)
    grid_width: int                       = Field(..., description="Grid width")
    grid_height: int                      = Field(..., description="Grid height")
    reward: float                         = Field(0.0, description="Reward received this step")
    done: bool                            = Field(False)
    task_name: str                        = Field("", description="Current task name: easy/medium/hard")
    metrics: Dict[str, float]             = Field(default_factory=dict, description="Live performance metrics")

    model_config = ConfigDict(use_enum_values=True)


class AeroSyncAction(BaseModel):
    """Action issued to the environment"""
    agent_id: str              = Field(..., description="Which agent to act")
    action_type: ActionType    = Field(..., description="What action to perform")
    direction: Optional[Direction] = Field(None, description="Direction for MOVE action")
    task_id: Optional[str]     = Field(None, description="Task ID for ASSIGN_TASK / PICK / PLACE")

    model_config = ConfigDict(use_enum_values=True)


class AeroSyncReward(BaseModel):
    """Detailed reward breakdown (returned inside info dict)"""
    total: float                    = Field(0.0)
    delivery_bonus: float           = Field(0.0)
    dispatch_bonus: float           = Field(0.0)
    pickup_bonus: float             = Field(0.0)
    collision_penalty: float        = Field(0.0)
    battery_penalty: float          = Field(0.0)
    delay_penalty: float            = Field(0.0)
    idle_penalty: float             = Field(0.0)


class EpisodeInfo(BaseModel):
    """Extra info returned by step()"""
    reward_breakdown: AeroSyncReward = Field(default_factory=AeroSyncReward)
    collision_events: List[str]      = Field(default_factory=list)
    battery_failures: List[str]      = Field(default_factory=list)
    completed_tasks: List[str]       = Field(default_factory=list)
    message: str                     = Field("")
