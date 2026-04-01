"""
AeroSync AI — FastAPI Server
Exposes OpenEnv-compliant HTTP endpoints.

Endpoints:
    POST /reset          → AeroSyncObservation
    POST /step           → {observation, reward, done, info}
    GET  /state          → raw state dict
    GET  /tasks          → list available tasks
    GET  /health         → liveness check
    GET  /openenv.yaml   → spec file
"""
from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from env.aerosync_env import AeroSyncEnv
from env.models import AeroSyncAction, AeroSyncObservation
from grader.grader import grade, detailed_report
from tasks.easy   import get_config as easy_config
from tasks.medium import get_config as medium_config
from tasks.hard   import get_config as hard_config


# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AeroSync AI",
    description="OpenEnv-compliant logistics simulation with robots and drones.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TASK_CONFIGS = {
    "easy":   easy_config,
    "medium": medium_config,
    "hard":   hard_config,
}

# Global environment instance (stateful per-session)
_env: Optional[AeroSyncEnv] = None


def _get_env() -> AeroSyncEnv:
    global _env
    if _env is None:
        raise HTTPException(status_code=400, detail="Environment not initialised. Call /reset first.")
    return _env


# ──────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ──────────────────────────────────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_name: str = "easy"   # easy | medium | hard


class StepResponse(BaseModel):
    observation: AeroSyncObservation
    reward: float
    done: bool
    info: Dict[str, Any]


class GradeResponse(BaseModel):
    score: float
    report: Dict[str, Any]


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "env": "aerosync-ai", "version": "1.0.0"}


@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {
                "name": "easy",
                "description": "1 robot + 1 drone, 2 deliveries. Introductory coordination.",
                "difficulty": 1,
                "agents": {"robots": 1, "drones": 1},
                "task_count": 2,
                "max_steps": 120,
            },
            {
                "name": "medium",
                "description": "3 robots + 2 drones, 6 deliveries. Battery pressure + dual dispatch zones.",
                "difficulty": 2,
                "agents": {"robots": 3, "drones": 2},
                "task_count": 6,
                "max_steps": 250,
            },
            {
                "name": "hard",
                "description": "6 robots + 4 drones, 12 deliveries. Degraded batteries, congestion, obstacles.",
                "difficulty": 3,
                "agents": {"robots": 6, "drones": 4},
                "task_count": 12,
                "max_steps": 500,
            },
        ]
    }


@app.post("/reset", response_model=AeroSyncObservation)
def reset(request: ResetRequest):
    global _env
    task_name = request.task_name.lower()
    if task_name not in TASK_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task '{task_name}'. Choose from: {list(TASK_CONFIGS.keys())}"
        )
    config = TASK_CONFIGS[task_name]()
    _env = AeroSyncEnv(config)
    obs = _env.reset()
    return obs


@app.post("/step", response_model=StepResponse)
def step(action: AeroSyncAction):
    env = _get_env()
    obs, reward, done, info = env.step(action)
    return StepResponse(
        observation=obs,
        reward=reward,
        done=done,
        info=info.dict(),
    )


@app.get("/state")
def state():
    env = _get_env()
    return env.state()


@app.get("/grade", response_model=GradeResponse)
def get_grade():
    env = _get_env()
    s = env.state()
    return GradeResponse(
        score=grade(s),
        report=detailed_report(s),
    )


@app.get("/openenv.yaml", response_class=PlainTextResponse)
def get_openenv_yaml():
    yaml_path = Path(__file__).parent / "openenv.yaml"
    if yaml_path.exists():
        return yaml_path.read_text()
    raise HTTPException(status_code=404, detail="openenv.yaml not found")


# ──────────────────────────────────────────────────────────────────────────────
# Dev entry-point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
