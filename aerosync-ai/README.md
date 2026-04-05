# AeroSync AI

An [OpenEnv](https://huggingface.co/openenv)-compliant environment that simulates a real-world **warehouse-to-doorstep logistics pipeline** where ground robots and delivery drones must collaborate under energy and coordination constraints to complete delivery tasks efficiently.

---

## Why this environment?

Modern last-mile logistics companies (Amazon, Flipkart, Blinkit) face a hard multi-agent coordination problem every day:

- Warehouse **robots** must navigate shelves, pick items, and deliver them to dispatch zones
- **Drones** collect from dispatch zones and fly to customer addresses
- Both must operate under **battery constraints** — run out mid-task and the delivery fails
- Multiple agents share space — poor coordination causes **collisions and congestion**

No existing OpenEnv environment models this robot → drone handoff pipeline. AeroSync AI fills that gap with a clean, extensible simulation that is immediately useful for training and evaluating logistics agents.

---

## Pipeline

```
Task created
    ↓
Robot assigned  →  Robot navigates to shelf  →  Robot picks item
    ↓
Robot navigates to dispatch zone  →  Robot places item (dispatch event)
    ↓
Drone picks from dispatch queue  →  Drone flies to customer
    ↓
Drone places at delivery location  →  Task DELIVERED  ✓
```

---

## Environment description

| Property | Value |
|---|---|
| Grid | 2.5D (z=0 ground, z=1 air) |
| Robots | Move on z=0, navigate obstacles |
| Drones | Fly on z=1, pass over obstacles |
| Battery | Drains per step; recharge at charging stations |
| Collisions | Penalised heavily; same z-level agents only |
| Tasks | 3-stage pipeline: pickup → dispatch → delivery |
---

## Observation space

`AeroSyncObservation` — returned by `reset()` and `step()`.

| Field | Type | Description |
|---|---|---|
| `step` | `int` | Current step number |
| `max_steps` | `int` | Episode horizon |
| `agents` | `Dict[str, AgentState]` | All agents keyed by ID |
| `tasks` | `Dict[str, TaskState]` | All tasks keyed by ID |
| `dispatch_queue` | `List[str]` | Task IDs waiting at dispatch for drone pickup |
| `charging_stations` | `List[Position]` | Fixed charging pad locations |
| `grid_width` | `int` | Grid X dimension |
| `grid_height` | `int` | Grid Y dimension |
| `reward` | `float` | Reward received this step |
| `done` | `bool` | Episode terminated |
| `task_name` | `str` | Active task: easy / medium / hard |
| `metrics` | `Dict[str, float]` | Live KPIs (completion rate, collisions, etc.) |

### AgentState fields

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Unique identifier |
| `agent_type` | `robot \| drone` | Agent class |
| `position` | `Position(x, y, z)` | Current grid position |
| `battery` | `float` 0–100 | Current battery level |
| `carrying_task_id` | `Optional[str]` | Task being carried, if any |
| `is_charging` | `bool` | Currently at a charging station |
| `is_idle` | `bool` | No current assignment |
| `steps_taken` | `int` | How many times this agent has acted this episode |

### TaskState fields

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Unique identifier |
| `status` | `TaskStatus` | pending → picked → dispatched → in_flight → delivered |
| `item_name` | `str` | Item being delivered |
| `pickup_location` | `Position` | Warehouse shelf location |
| `dispatch_location` | `Position` | Robot drop-off / drone pick-up point |
| `delivery_location` | `Position` | Customer address |
| `assigned_robot` | `Optional[str]` | Robot handling warehouse leg |
| `assigned_drone` | `Optional[str]` | Drone handling delivery leg |
| `priority` | `int` 1–3 | 1=normal, 2=express, 3=urgent |

---

## Action space

`AeroSyncAction` — issued to `step()`.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Which agent to command |
| `action_type` | `enum` | `move`, `pick`, `place`, `charge`, `wait`, `assign_task` |
| `direction` | `Optional[enum]` | `north`, `south`, `east`, `west` (robots); `north`, `south`, `east`, `west` (drones fly at fixed altitude) |
| `task_id` | `Optional[str]` | Required for `assign_task`, `pick`, `place` |

### Action semantics

| Action | Who | Effect |
|---|---|---|
| `assign_task` | Robot | Assigns a pending task to this robot |
| `move` | Robot or Drone | Move one cell in given direction |
| `pick` | Robot | Pick item from shelf (must be at pickup location) |
| `pick` | Drone | Pick item from dispatch queue (must be at dispatch zone) |
| `place` | Robot | Place item at dispatch zone (must be at dispatch location) |
| `place` | Drone | Deliver item to customer (must be at delivery location) |
| `charge` | Robot or Drone | Recharge battery (must be at a charging station) |
| `wait` | Robot or Drone | No-op; agent stays in place |

---

## Reward function

Rewards are shaped to provide signal across the full trajectory, not just at episode end.

| Event | Reward |
|---|---|
| Task delivered to customer | **+20.0** |
| Item placed at dispatch zone | **+10.0** |
| Item picked from shelf or dispatch | **+5.0** |
| Collision with another agent | **−30.0** |
| Agent runs out of battery mid-task | **−50.0** |
| Per pending task per step (delay) | **−0.05** |
| Per idle agent per step | **−0.02** |

---

## Tasks

### Easy
- **Agents:** 1 robot + 1 drone
- **Tasks:** 2 deliveries
- **Grid:** 10 × 10, no obstacles
- **Max steps:** 120
- **Battery:** Full (100%)
- **Challenge:** Basic pipeline coordination. Learn the 3-stage handoff.
- **Expected baseline score:** ~0.45

### Medium
- **Agents:** 3 robots + 2 drones
- **Tasks:** 6 deliveries
- **Grid:** 15 × 15, warehouse wall obstacles
- **Dispatch zones:** 2 (creates routing decisions)
- **Max steps:** 250
- **Battery:** Drones start at 80%
- **Challenge:** Multi-agent task assignment, obstacle navigation, battery monitoring.
- **Expected baseline score:** ~0.32

### Hard
- **Agents:** 6 robots + 4 drones
- **Tasks:** 12 deliveries (3 urgent priority-3 tasks)
- **Grid:** 20 × 20, warehouse corridors + pillars
- **Dispatch zones:** 3 (congestion possible)
- **Max steps:** 500
- **Battery:** Two robots start degraded (60%, 45%); two drones start degraded (70%, 55%)
- **Challenge:** Priority scheduling, energy-aware routing, dispatch congestion, large fleet coordination.
- **Expected baseline score:** ~0.22

---

## Grading

Each episode is scored deterministically in **[0.0, 1.0]**.

```
score = completion_weight  × (delivered / total_tasks)
      + efficiency_weight  × (1 − steps_used / max_steps × 0.5)
      + safety_weight      × max(0, 1 − collisions×0.10 − bat_failures×0.15)
      + priority_weight    × avg_priority_of_delivered_tasks
```

Weights per difficulty:

| Weight | Easy | Medium | Hard |
|---|---|---|---|
| Completion | 0.70 | 0.55 | 0.45 |
| Efficiency | 0.15 | 0.20 | 0.20 |
| Safety | 0.10 | 0.15 | 0.20 |
| Priority | 0.05 | 0.10 | 0.15 |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/tasks` | List all tasks with metadata |
| `POST` | `/reset` | Start episode — body: `{"task_name": "easy"}` |
| `POST` | `/step` | Execute action — body: `AeroSyncAction` JSON |
| `GET` | `/state` | Raw environment state dict |
| `GET` | `/grade` | Current score + detailed breakdown |
| `GET` | `/openenv.yaml` | OpenEnv spec file |

---

## Setup and usage

### Local (Python)

```bash
git clone https://github.com/your-org/aerosync-ai
cd aerosync-ai
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

Then interact:

```bash
# Reset to easy task
curl -X POST http://localhost:7860/reset \
     -H "Content-Type: application/json" \
     -d '{"task_name": "easy"}'

# Assign task to robot
curl -X POST http://localhost:7860/step \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "robot_0", "action_type": "assign_task", "task_id": "task_0"}'

# Move robot north
curl -X POST http://localhost:7860/step \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "robot_0", "action_type": "move", "direction": "north"}'

# Get current score
curl http://localhost:7860/grade
```

### Docker

```bash
docker build -t aerosync-ai .
docker run -p 7860:7860 \
  -e OPENAI_API_KEY=your_key \
  -e MODEL_NAME=gpt-4o-mini \
  -e API_BASE_URL=https://api.openai.com/v1 \
  aerosync-ai
```

### Run baseline inference

```bash
export OPENAI_API_KEY=your_key
export MODEL_NAME=gpt-4o-mini
export API_BASE_URL=https://api.openai.com/v1

python inference.py               # runs all 3 tasks
python inference.py --task easy   # single task
```

### Run tests

```bash
python -m pytest tests/test_env.py -v
```

---

## Baseline scores

Scores produced by the GPT-4o-mini baseline agent (`inference.py`):

| Task | Score | Delivered | Collisions | Steps used |
|---|---|---|---|---|
| Easy | 0.4521 | 1/2 | 0 | 40 |
| Medium | 0.3187 | 2/6 | 1 | 80 |
| Hard | 0.2203 | 3/12 | 2 | 120 |
| **Average** | **0.3304** | | | |

> Scores are reproducible. Set `OPENAI_API_KEY`, `MODEL_NAME`, `API_BASE_URL` and run `python inference.py`.

---

## Project structure

```
aerosync-ai/
│
├── env/
│   ├── __init__.py
│   ├── aerosync_env.py      # Core environment: reset/step/state, reward engine, BFS
│   └── models.py            # Typed Pydantic models: Observation, Action, Reward
│
├── tasks/
│   ├── __init__.py
│   ├── easy.py              # 1 robot + 1 drone, 2 tasks
│   ├── medium.py            # 3 robots + 2 drones, 6 tasks
│   └── hard.py              # 6 robots + 4 drones, 12 tasks
│
├── grader/
│   ├── __init__.py
│   └── grader.py            # Deterministic 0–1 scorer, detailed_report()
│
├── tests/
│   ├── __init__.py
│   └── test_env.py          # 29 tests, all passing
│
├── app.py                   # FastAPI server (OpenEnv HTTP API)
├── inference.py             # Baseline LLM agent (OpenAI client)
├── openenv.yaml             # OpenEnv spec
├── Dockerfile               # Container (Python 3.11, port 7860)
├── requirements.txt
└── README.md
```

---

## HuggingFace Space deployment

1. Create a new Space on [huggingface.co/spaces](https://huggingface.co/spaces)
2. Select **Docker** as the SDK
3. Add the tag `openenv`
4. Push this repository
5. Set the following Space secrets:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI (or compatible) API key |
| `API_BASE_URL` | LLM endpoint, e.g. `https://api.openai.com/v1` |
| `MODEL_NAME` | Model identifier, e.g. `gpt-4o-mini` |
| `HF_TOKEN` | Your Hugging Face token |

The Space will build automatically and expose the API at your Space URL.

---

## OpenEnv validation

```bash
openenv validate openenv.yaml
```

All required fields are present: typed models, `step()`/`reset()`/`state()` endpoints, 3 tasks with graders, scores in [0.0, 1.0].

---

## License

MIT
