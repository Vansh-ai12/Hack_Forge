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
    DISPATCHED = "dispatched"
    IN_FLIGHT  = "in_flight"
    DELIVERED  = "delivered"
    FAILED     = "failed"


class ActionType(str, Enum):
    MOVE        = "move"
    PICK        = "pick"
    PLACE       = "place"
    CHARGE      = "charge"
    WAIT        = "wait"
    ASSIGN_TASK = "assign_task"
    INVALID_TYPE = "INVALID_TYPE"
    HOVER       = "hover"           # NEW: drone holds position mid-air
    ASCEND      = "ascend"          # NEW: drone gains altitude
    DESCEND     = "descend"         # NEW: drone loses altitude
    RETURN_TO_BASE = "return_to_base"  # NEW: emergency low-battery return


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST  = "east"
    WEST  = "west"
    UP    = "up"
    DOWN  = "down"


class FlightMode(str, Enum):
    """Drone-only: active flight behaviour mode"""
    CRUISE      = "cruise"       # normal A-to-B movement, speed optimised
    HOVER       = "hover"        # stationary mid-air, high stability demand
    LANDING     = "landing"      # descending to deliver / dock
    TAKEOFF     = "takeoff"      # ascending from ground / dispatch pad
    RETURN      = "return"       # RTB (return-to-base) on low battery
    EMERGENCY   = "emergency"    # critical battery / collision avoidance


class WindCondition(str, Enum):
    """Environmental wind level affecting hover stability"""
    CALM        = "calm"         # 0-5 km/h — no stability cost
    LIGHT       = "light"        # 5-15 km/h — minor drift
    MODERATE    = "moderate"     # 15-30 km/h — noticeable battery drain
    STRONG      = "strong"       # 30+ km/h — high instability, may abort


# ─────────────────────────────────────────────
# Existing Core Models (unchanged)
# ─────────────────────────────────────────────

class Position(BaseModel):
    x: int = Field(..., description="X coordinate on grid")
    y: int = Field(..., description="Y coordinate on grid")
    z: int = Field(0, description="Z level: 0=ground, 1=air")


class AgentState(BaseModel):
    agent_id: str                   = Field(..., description="Unique agent identifier")
    agent_type: AgentType           = Field(..., description="robot or drone")
    position: Position              = Field(..., description="Current position")
    battery: float                  = Field(..., ge=0.0, le=100.0, description="Battery level 0-100")
    carrying_task_id: Optional[str] = Field(None, description="Task ID being carried, if any")
    is_charging: bool               = Field(False, description="Currently at charging station")
    is_idle: bool                   = Field(True, description="No current assignment")
    steps_taken: int                = Field(0, description="Steps taken this episode")


class TaskState(BaseModel):
    task_id: str                    = Field(..., description="Unique task identifier")
    status: TaskStatus              = Field(TaskStatus.PENDING)
    item_name: str                  = Field(..., description="Name of the item")
    pickup_location: Position       = Field(..., description="Warehouse shelf location")
    dispatch_location: Position     = Field(..., description="Dispatch / handoff zone")
    delivery_location: Position     = Field(..., description="Customer delivery point")
    assigned_robot: Optional[str]   = Field(None)
    assigned_drone: Optional[str]   = Field(None)
    created_at_step: int            = Field(0)
    completed_at_step: Optional[int]= Field(None)
    priority: int                   = Field(1, ge=1, le=3, description="1=normal, 2=express, 3=urgent")


class GridCell(BaseModel):
    x: int
    y: int
    z: int
    is_obstacle: bool           = False
    is_dispatch: bool           = False
    is_charging: bool           = False
    is_shelf: bool              = False
    occupant_id: Optional[str]  = None


# ─────────────────────────────────────────────
# NEW: Drone Flight Physics & Battery Models
# ─────────────────────────────────────────────


class DroneTiltState(BaseModel):
    """Pitch / Roll / Yaw of drone body frame — drives diagonal movement"""
    pitch: float = Field(0.0, ge=-45.0, le=45.0,
                         description="Nose up(+) / down(-) in degrees; negative = forward acceleration")
    roll: float  = Field(0.0, ge=-45.0, le=45.0,
                         description="Right(+) / left(-) bank in degrees; used for turning")
    yaw: float   = Field(0.0, ge=-180.0, le=180.0,
                         description="Heading rotation clockwise(+); 0=north, 90=east")

    max_pitch: float  = Field(30.0, ge=5.0,  le=45.0, description="Model safe pitch limit")
    max_roll: float   = Field(30.0, ge=5.0,  le=45.0, description="Model safe roll limit")
    tilt_rate: float  = Field(5.0,  ge=1.0,  le=20.0, description="Max deg/step pitch or roll can change")
    yaw_rate: float   = Field(10.0, ge=1.0,  le=45.0, description="Max deg/step heading can rotate")

    is_banking: bool       = Field(False, description="True when abs(roll)>10 — faster turn, less stable")
    tilt_stability_cost: float = Field(0.0, ge=0.0, le=1.0,
                                       description="How much current tilt degrades hover_stability_score")
    

class FlightWaypoint(BaseModel):
    """One leg of a multi-direction planned path"""
    position: Position              = Field(..., description="Target grid cell")
    direction: Direction            = Field(..., description="Approach direction into this waypoint")
    tilt: Optional[DroneTiltState]  = Field(None, description="Desired tilt for this leg")
    speed_factor: float             = Field(1.0, ge=0.1, le=2.0,
                                            description="Speed multiplier vs max_speed for this leg")
    hover_at_waypoint: bool         = Field(False, description="Hold hover here before next leg")
    hover_steps: int                = Field(0, ge=0, description="Steps to hold if hover_at_waypoint=True")
    estimated_battery_cost: float   = Field(0.0, ge=0.0, description="Predicted % drain for this leg")

    # ── Waypoint Outcome Tracking (stamped by env.step() on arrival) ──
    is_reached: bool                = Field(False,
                                            description="True once drone arrives at this waypoint position")
    reached_at_step: Optional[int]  = Field(None,
                                            description="Env step number when waypoint was reached")
    obstacle_dist_on_arrival: float = Field(999.0, ge=0.0,
                                            description="nearest_obstacle_dist recorded the moment drone reached this waypoint — used to compute waypoint_obstacle_clear_bonus or waypoint_obstacle_penalty")
    was_blocked: bool               = Field(False,
                                            description="True if this waypoint position was found inside or adjacent to an obstacle — triggers blocked_waypoint_penalty")
    arrival_was_clean: bool         = Field(False,
                                            description="True if obstacle_dist_on_arrival > 2.0 AND was_blocked=False — clean waypoint, earns waypoint_obstacle_clear_bonus")
    battery_cost_actual: float      = Field(0.0, ge=0.0,
                                            description="Actual % battery drained reaching this waypoint — compared against estimated_battery_cost to measure planning accuracy")
    
class DroneFlightPath(BaseModel):
    """
    Full multi-leg planned path — inference.py writes this,
    env.step() consumes it waypoint by waypoint each step.
    """
    drone_id: str                    = Field(..., description="Owner drone ID")
    waypoints: List[FlightWaypoint]  = Field(default_factory=list, description="Ordered legs")
    current_waypoint_idx: int        = Field(0, ge=0, description="Active leg index")
    total_estimated_battery: float   = Field(0.0, ge=0.0, description="Sum of all leg battery costs")
    total_estimated_steps: int       = Field(0, ge=0,    description="Total steps for full path")
    path_is_valid: bool              = Field(True, description="False if any leg busts battery/altitude")
    replanned_count: int             = Field(0, ge=0,    description="Times inference.py re-routed mid-mission")


class DroneFlightParams(BaseModel):
    """
    Per-drone flight physics — fed into inference.py to let the LLM
    policy make battery-aware, stability-aware routing decisions.
    """

    # ── Movement ──────────────────────────────────────────────────────
    max_speed: float            = Field(2.0, ge=0.1, le=10.0,
                                        description="Max cells/step in CRUISE mode")
    current_speed: float        = Field(0.0, ge=0.0, le=10.0,
                                        description="Actual speed this step")
    altitude: int               = Field(1, ge=0, le=5,
                                        description="Current altitude layer (0=ground, 5=max)")
    max_altitude: int           = Field(5, ge=1, le=10,
                                        description="Hard ceiling for this drone model")
    flight_mode: FlightMode     = Field(FlightMode.CRUISE,
                                        description="Current flight behaviour mode")

    # ── Battery Optimisation ──────────────────────────────────────────
    battery_capacity: float     = Field(100.0, ge=1.0,
                                        description="Full-charge capacity (normalised to 100)")
    battery_drain_per_move: float = Field(1.5, ge=0.0,
                                        description="% battery consumed per MOVE step")
    battery_drain_hover: float  = Field(2.5, ge=0.0,
                                        description="% battery consumed per HOVER step (higher than move)")
    battery_drain_ascend: float = Field(3.0, ge=0.0,
                                        description="% battery consumed per ASCEND step (most expensive)")
    battery_drain_idle: float   = Field(0.3, ge=0.0,
                                        description="% battery consumed while airborne-idle (motors on)")
    low_battery_threshold: float= Field(25.0, ge=5.0, le=50.0,
                                        description="% level that triggers RTB (return-to-base)")
    critical_battery_threshold: float = Field(10.0, ge=1.0, le=20.0,
                                        description="% level that forces EMERGENCY landing immediately")
    charge_rate_per_step: float = Field(5.0, ge=0.1,
                                        description="% battery recovered per step while docked")
    estimated_steps_remaining: int = Field(0, ge=0,
                                        description="Inference-computed steps left before forced RTB")

    # ── Hover Stability ───────────────────────────────────────────────
    hover_stability_score: float= Field(1.0, ge=0.0, le=1.0,
                                        description="1.0=perfectly stable, 0.0=uncontrolled; degrades with wind/payload")
    hover_drift_x: float        = Field(0.0,
                                        description="Lateral drift offset on X axis this step (cells)")
    hover_drift_y: float        = Field(0.0,
                                        description="Lateral drift offset on Y axis this step (cells)")
    hover_drift_z: float = Field(0.0,
    description="Vertical drift pressure in metres; if abs > 0.5 triggers altitude correction burn")
    
    stability_threshold: float  = Field(0.6, ge=0.0, le=1.0,
                                        description="Min stability score to attempt delivery landing")
    wind_condition: WindCondition = Field(WindCondition.CALM,
                                        description="Current wind level affecting stability & drain")
    wind_drag_factor: float     = Field(1.0, ge=1.0, le=3.0,
                                        description="Multiplier on battery drain under wind (1.0=no wind)")

    # ── Payload & Delivery ────────────────────────────────────────────
    max_payload_kg: float       = Field(2.0, ge=0.1, le=20.0,
                                        description="Max carry weight in kg")
    current_payload_kg: float   = Field(0.0, ge=0.0,
                                        description="Weight of item currently being carried")
    payload_drag_factor: float  = Field(1.0, ge=1.0, le=2.0,
                                        description="Multiplier on battery drain from payload weight")
    delivery_precision: float   = Field(1.0, ge=0.0, le=1.0,
                                        description="Landing accuracy score; <threshold = failed delivery")
    delivery_precision_threshold: float = Field(0.75, ge=0.0, le=1.0,
                                        description="Min precision needed for successful drop")
    delivery_attempts: int      = Field(0, ge=0,
                                        description="Number of drop attempts for current task")
    max_delivery_attempts: int  = Field(3, ge=1,
                                        description="Max attempts before task marked FAILED")

    # ── Routing & Path ────────────────────────────────────────────────
    planned_path: List[Position]= Field(default_factory=list,
                                        description="Waypoints planned by inference.py for current trip")
    steps_to_destination: int   = Field(0, ge=0,
                                        description="Steps remaining to reach delivery_location")
    steps_to_base: int          = Field(0, ge=0,
                                        description="Steps to nearest charging station (RTB cost)")
    can_complete_mission: bool  = Field(True,
                                        description="True if battery allows delivery + RTB without recharge")


class DroneDiagnostics(BaseModel):
    """
    Live telemetry snapshot — populated each step, used by inference.py
    to detect failures and adjust LLM policy decisions in real time.
    """
    drone_id: str               = Field(..., description="Matches AgentState.agent_id")
    motor_health: float         = Field(1.0, ge=0.0, le=1.0,
                                        description="1.0=all motors nominal; degrades on collision")
    collision_risk: float       = Field(0.0, ge=0.0, le=1.0,
                                        description="Proximity-based collision probability this step")
    obstacle_detected: bool     = Field(False,
                                        description="Obstacle in immediate path")
    nearest_obstacle_dist: float= Field(999.0, ge=0.0,
                                        description="Distance in cells to nearest obstacle")
    total_distance_flown: float = Field(0.0, ge=0.0,
                                        description="Cumulative cells flown this episode")
    total_deliveries: int       = Field(0, ge=0,
                                        description="Successful deliveries this episode")
    total_failed_deliveries: int= Field(0, ge=0,
                                        description="Failed delivery attempts this episode")
    last_recharge_step: int     = Field(0, ge=0,
                                        description="Step number of last completed charge cycle")
    forced_rtb_count: int       = Field(0, ge=0,
                                        description="How many times this drone was force-returned due to battery")


# ─────────────────────────────────────────────
# Enhanced AgentState for Drones
# ─────────────────────────────────────────────

class DroneAgentState(AgentState):
    """
    Extends AgentState with full drone-specific params.
    agent_type is locked to DRONE.
    All existing AgentState fields are inherited unchanged.
    """
    agent_type: AgentType           = Field(AgentType.DRONE, description="Always DRONE")
    flight: DroneFlightParams       = Field(default_factory=DroneFlightParams,
                                            description="Full flight physics & battery params")
    diagnostics: DroneDiagnostics  = Field(..., description="Live telemetry for this drone")


# ─────────────────────────────────────────────
# OpenEnv Core Models (unchanged + drone slot)
# ─────────────────────────────────────────────

class AeroSyncObservation(BaseModel):
    """Full observation returned by reset() and step()"""
    step: int                           = Field(..., description="Current step number")
    max_steps: int                      = Field(..., description="Max steps per episode")
    agents: Dict[str, AgentState]       = Field(..., description="All agents keyed by ID")
    drone_states: Dict[str, DroneAgentState] = Field(
                                            default_factory=dict,
                                            description="Drone-specific extended states keyed by drone ID")
    grid: Dict[str, GridCell]           = Field(
                                            default_factory=dict,
                                            description="Full grid map keyed by 'x,y,z' string — lets inference.py see all obstacles before planning waypoints")
    tasks: Dict[str, TaskState]         = Field(..., description="All tasks keyed by ID")
    dispatch_queue: List[str]           = Field(default_factory=list,
                                            description="Task IDs waiting at dispatch for drone pickup")
    charging_stations: List[Position]   = Field(default_factory=list)
    grid_width: int                     = Field(..., description="Grid width")
    grid_height: int                    = Field(..., description="Grid height")
    reward: float                       = Field(0.0, description="Reward received this step")
    done: bool                          = Field(False)
    task_name: str                      = Field("", description="Current task name: easy/medium/hard")
    metrics: Dict[str, float]           = Field(default_factory=dict,
                                            description="Live performance metrics")

    model_config = ConfigDict(use_enum_values=True)


class AeroSyncAction(BaseModel):
    """Action issued to the environment"""
    agent_id: str                   = Field(..., description="Which agent to act")
    action_type: ActionType         = Field(..., description="What action to perform")
    direction: Optional[Direction]  = Field(None, description="Direction for MOVE action")
    task_id: Optional[str]          = Field(None, description="Task ID for ASSIGN_TASK / PICK / PLACE")
    target_altitude: Optional[int]  = Field(None, ge=0, le=10,
                                            description="Drone: desired altitude for ASCEND/DESCEND")
    flight_mode_override: Optional[FlightMode] = Field(None,
                                            description="Drone: force a specific FlightMode this step")

    model_config = ConfigDict(use_enum_values=True)


class AeroSyncReward(BaseModel):
    """Detailed reward breakdown (returned inside info dict)"""

    # ── Core (unchanged) ──────────────────────────────────────────────
    total: float               = Field(0.0)
    delivery_bonus: float      = Field(0.0)
    dispatch_bonus: float      = Field(0.0)
    pickup_bonus: float        = Field(0.0)
    collision_penalty: float   = Field(0.0)
    battery_penalty: float     = Field(0.0)
    delay_penalty: float       = Field(0.0)
    idle_penalty: float        = Field(0.0)

    # ── Hover Stability ───────────────────────────────────────────────
    hover_stability_bonus: float = Field(0.0,
        description="Bonus when hover_stability_score > threshold during delivery hold")
    hover_stability_loss_penalty: float = Field(0.0,
        description="Penalty every step hover_stability_score drops below threshold while airborne")
    hover_drift_penalty: float = Field(0.0,
        description="Penalty proportional to abs(drift_x)+abs(drift_y)+abs(drift_z) while hovering — punishes sloppy holds")

    # ── Tilt / Banking ────────────────────────────────────────────────
    tilt_efficiency_bonus: float = Field(0.0,
        description="Bonus for using minimum tilt needed to complete a turn — rewards smooth flight")
    over_tilt_penalty: float = Field(0.0,
        description="Penalty when abs(pitch) or abs(roll) exceeds max_pitch/max_roll — unsafe tilt")
    unnecessary_banking_penalty: float = Field(0.0,
        description="Penalty for is_banking=True when no direction change is needed — wastes battery")
    tilt_stability_loss_penalty: float = Field(0.0,
        description="Penalty each step equal to tilt_stability_cost — directly punishes destabilising tilts")
    smooth_yaw_bonus: float = Field(0.0,
        description="Bonus for reaching target yaw within minimum yaw steps — rewards efficient heading change")

    # ── Precision Landing ─────────────────────────────────────────────
    precision_landing_bonus: float = Field(0.0,
        description="Bonus scaled to delivery_precision score on successful drop — higher precision = higher bonus")
    imprecise_drop_penalty: float = Field(0.0,
        description="Penalty when delivery_precision < delivery_precision_threshold — bad drop attempt")
    repeated_attempt_penalty: float = Field(0.0,
        description="Penalty per extra delivery attempt beyond the first — discourages trial and error")

    # ── Battery Efficiency ────────────────────────────────────────────
    efficient_rtb_bonus: float = Field(0.0,
        description="Bonus for returning before critical_battery_threshold — proactive battery management (RTB-> Return To Base)")
    forced_landing_penalty: float = Field(0.0,
        description="Penalty for emergency/forced landing mid-mission due to critical battery")
    battery_conservation_bonus: float = Field(0.0,
        description="Bonus for completing full delivery+RTB while using less than 60% battery — efficient routing")
    unnecessary_hover_penalty: float = Field(0.0,
        description="Penalty for hovering more steps than hover_steps allows at a waypoint — wastes battery")

    # ── Path & Movement Quality ───────────────────────────────────────
   
    optimal_path_bonus: float = Field(0.0,
        description="Bonus if actual steps_taken <= total_estimated_steps — drone followed plan efficiently")
    replanning_penalty: float = Field(0.0,
        description="Penalty per replanned_count increment — discourages chaotic mid-mission rerouting")
    waypoint_reached_bonus: float = Field(0.0,
        description="Small bonus each time drone successfully reaches a FlightWaypoint cleanly — encourages progress")
    speed_efficiency_bonus: float = Field(0.0,
        description="Bonus for using high speed_factor on long legs and low speed_factor near drop — smart speed control")

    # ── Obstacle Avoidance (Distance-based) ───────────────────────────
    obstacle_proximity_penalty: float = Field(0.0,
        description="Penalty when nearest_obstacle_dist < 2.0 cells regardless of speed — drone is physically too close")
    obstacle_near_miss_penalty: float = Field(0.0,
        description="Larger penalty when nearest_obstacle_dist < 1.0 cell — almost hit, severe warning regardless of speed")
    safe_clearance_bonus: float = Field(0.0,
        description="Small bonus each step drone maintains nearest_obstacle_dist > 3.0 cells — rewards clean separation")
    collision_avoidance_bonus: float = Field(0.0,
        description="Bonus when obstacle_detected=True but drone successfully reroutes without hitting — reactive avoidance rewarded")

    # ── Obstacle Avoidance (TTC — Time To Collision) ──────────────────
    # TTC = nearest_obstacle_dist / current_speed
    # Low TTC = dangerous even if dist looks ok (fast drone closing in)
    # High TTC = safe even if slightly close (slow drone, lots of time)
    
    ttc_critical_penalty: float = Field(0.0,
        description="Severe penalty when TTC < 1.0 step — drone will hit obstacle within 1 step at current speed; e.g. dist=5.0 but speed=6.0 → TTC=0.83 → critical")
    ttc_warning_penalty: float = Field(0.0,
        description="Medium penalty when TTC < 2.0 steps — closing in fast, needs to slow down or divert; e.g. dist=5.0, speed=3.0 → TTC=1.67 → warning")
    ttc_safe_bonus: float = Field(0.0,
        description="Small bonus each step TTC > 5.0 — drone is either far enough or slow enough near obstacles; safe approach rewarded")
    high_speed_near_obstacle_penalty: float = Field(0.0,
        description="Penalty when current_speed > 1.5 AND nearest_obstacle_dist < 3.0 — punishes fast flight near obstacles even if not yet critical TTC")
    speed_reduction_near_obstacle_bonus: float = Field(0.0,
        description="Bonus when drone proactively reduces speed_factor as nearest_obstacle_dist decreases — smart deceleration rewarded")

    # ── Waypoint + Obstacle Interaction ──────────────────────────────
    waypoint_obstacle_clear_bonus: float = Field(0.0,
        description="Bonus when drone reaches a FlightWaypoint AND nearest_obstacle_dist > 2.0 — arrived cleanly with safe clearance")
    waypoint_obstacle_penalty: float = Field(0.0,
        description="Penalty when drone reaches a FlightWaypoint BUT nearest_obstacle_dist < 1.5 — reached checkpoint too close to obstacle")
    blocked_waypoint_penalty: float = Field(0.0,
        description="Penalty when a planned FlightWaypoint position is found to be inside or adjacent to an obstacle — bad planning")
    obstacle_replan_penalty: float = Field(0.0,
        description="Penalty specifically when replanned_count increments due to obstacle_detected=True mid-leg — obstacle forced a replan")
    clean_path_completion_bonus: float = Field(0.0,
        description="Bonus for completing the full DroneFlightPath with zero obstacle_proximity_penalty steps — perfectly clean flight")
    

class EpisodeInfo(BaseModel):
    """Extra info returned by step()"""
    reward_breakdown: AeroSyncReward    = Field(default_factory=AeroSyncReward)
    collision_events: List[str]         = Field(default_factory=list)
    battery_failures: List[str]         = Field(default_factory=list)
    completed_tasks: List[str]          = Field(default_factory=list)
    message: str                        = Field("")

    drone_rtb_events: List[str]         = Field(default_factory=list,
                                                description="Drone IDs that triggered RTB this step")
    drone_precision_failures: List[str] = Field(default_factory=list,
                                                description="Drone IDs that failed delivery due to low precision")
    drone_stability_warnings: List[str] = Field(default_factory=list,
                                                description="Drone IDs below stability_threshold this step")

    # ── Obstacle Episode Tracking ─────────────────────────────────────
    obstacle_near_misses: List[str]     = Field(default_factory=list,
                                                description="Drone IDs that had nearest_obstacle_dist < 1.0 this step")
    obstacle_forced_replans: List[str]  = Field(default_factory=list,
                                                description="Drone IDs whose replanned_count incremented due to obstacle this step")
    blocked_waypoints: List[str]        = Field(default_factory=list,
                                                description="Waypoint positions found blocked/adjacent to obstacle this step — 'x,y,z' strings")
    clean_path_drones: List[str]        = Field(default_factory=list,
                                                description="Drone IDs that completed full path this episode with zero near-miss events")