"""PLATO Room — HTTP API Server

Run any PLATO room via HTTP. Language-agnostic, works over network.

Usage:
    python3 http-api/plato_server.py --rooms-dir /srv/plato-rooms --port 8100

Endpoints:
    POST /room/{name}/command   — submit a command (JSON body)
    GET  /room/{name}/status    — room state
    GET  /room/{name}/experts   — list experts (study room)
    GET  /room/{name}/journal   — journal entries (study room)
    GET  /room/{name}/queue     — task queue (dreamcycle room)
    GET  /rooms                 — list all rooms
    GET  /health                — server health
"""

import yaml, os, sys, json, importlib.util, tempfile
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="PLATO Room Server", version="1.0.0")

ROOMS_DIR = Path(os.environ.get("PLATO_ROOMS_DIR", "/srv/plato-rooms"))
PORT = int(os.environ.get("PLATO_PORT", "8100"))

# Cache loaded engines
_engine_cache = {}


def get_engine(room_name: str):
    """Load and cache a room's engine module."""
    if room_name in _engine_cache:
        return _engine_cache[room_name]
    room_dir = ROOMS_DIR / room_name
    if not room_dir.exists():
        return None
    # Find engine script
    engine_files = list((room_dir / "bridges").glob("*_engine.py"))
    if not engine_files:
        return None
    spec = importlib.util.spec_from_file_location(f"engine_{room_name}", engine_files[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _engine_cache[room_name] = mod
    return mod


def atomic_write(path: Path, data: dict):
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    os.replace(tmp, path)


def atomic_read(path: Path) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


class Command(BaseModel):
    agent: str
    action: str
    expert_id: Optional[str] = None
    topic: Optional[str] = None
    brief: Optional[str] = None
    model: Optional[str] = None
    budget_tokens: Optional[int] = None
    max_rounds: Optional[int] = None
    name: Optional[str] = None
    content: Optional[str] = None
    entry_type: Optional[str] = None
    sha: Optional[str] = None
    checkpoint_label: Optional[str] = None
    new_expert_name: Optional[str] = None
    label: Optional[str] = None
    note: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[list] = None
    source: Optional[str] = None
    category: Optional[str] = None
    score: Optional[int] = None
    task_id: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None
    duration: Optional[int] = None
    schedule: Optional[dict] = None
    max_retries: Optional[int] = None
    timeout: Optional[int] = None
    task_action: Optional[str] = None
    needed_from: Optional[list] = None
    urgency: Optional[str] = None
    location: Optional[str] = None
    working_on: Optional[str] = None
    capacity: Optional[str] = None
    message: Optional[str] = None
    lang: Optional[str] = None
    target: Optional[str] = None
    gpu_budget: Optional[dict] = None
    limit: Optional[int] = None
    author: Optional[str] = None
    entry_id: Optional[str] = None
    hypothesis: Optional[str] = None
    prediction: Optional[str] = None
    variables: Optional[dict] = None


@app.post("/room/{room_name}/command")
async def run_command(room_name: str, cmd: dict):
    room_dir = ROOMS_DIR / room_name
    engine = get_engine(room_name)
    if not engine or not room_dir.exists():
        raise HTTPException(404, f"Room '{room_name}' not found")

    cmd_id = f"{os.urandom(4).hex()}"
    cmds_dir = room_dir / "world" / "commands"
    cmds_dir.mkdir(parents=True, exist_ok=True)
    cmd_path = cmds_dir / f"{cmd_id}.yaml"
    atomic_write(cmd_path, cmd)

    # Process turns
    engine.process_turns()

    # Read latest log
    logs_dir = room_dir / "world" / "logs"
    logs = sorted(logs_dir.glob("*.yaml")) if logs_dir.exists() else []
    if logs:
        return atomic_read(logs[-1])
    return {"status": "processed", "command_id": cmd_id}


@app.get("/room/{room_name}/status")
async def room_status(room_name: str):
    room_dir = ROOMS_DIR / room_name
    rooms_dir = room_dir / "world" / "rooms"
    if not rooms_dir.exists():
        raise HTTPException(404, f"Room '{room_name}' not found")
    results = {}
    for f in rooms_dir.glob("*.yaml"):
        results[f.stem] = atomic_read(f)
    return results


@app.get("/room/{room_name}/experts")
async def list_experts(room_name: str):
    experts_dir = ROOMS_DIR / room_name / "world" / "experts"
    if not experts_dir.exists():
        return {"experts": []}
    experts = []
    for f in experts_dir.glob("*.yaml"):
        e = atomic_read(f)
        if e.get("id"):
            experts.append(e)
    return {"experts": experts, "count": len(experts)}


@app.get("/room/{room_name}/journal")
async def get_journal(room_name: str, limit: int = 50):
    journals_dir = ROOMS_DIR / room_name / "world" / "journals"
    if not journals_dir.exists():
        return {"entries": []}
    entries = []
    for f in sorted(journals_dir.glob("*.yaml"))[-limit:]:
        entries.append(atomic_read(f))
    return {"entries": entries, "count": len(entries)}


@app.get("/room/{room_name}/queue")
async def get_queue(room_name: str):
    queue_dir = ROOMS_DIR / room_name / "world" / "queue"
    if not queue_dir.exists():
        return {"queue": []}
    results = {}
    for f in queue_dir.glob("*.yaml"):
        results[f.stem] = atomic_read(f)
    return results


@app.get("/room/{room_name}/tasks")
async def get_tasks(room_name: str):
    tasks_dir = ROOMS_DIR / room_name / "world" / "tasks"
    if not tasks_dir.exists():
        return {"tasks": []}
    tasks = []
    for f in tasks_dir.glob("*.yaml"):
        t = atomic_read(f)
        if t.get("id"):
            tasks.append(t)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/room/{room_name}/messages")
async def get_messages(room_name: str, limit: int = 50):
    msgs_dir = ROOMS_DIR / room_name / "world" / "messages"
    if not msgs_dir.exists():
        return {"messages": []}
    msgs = []
    for f in sorted(msgs_dir.glob("*.yaml"))[-limit:]:
        msgs.append(atomic_read(f))
    return {"messages": msgs, "count": len(msgs)}


@app.get("/room/{room_name}/entries")
async def get_entries(room_name: str, category: str = None, limit: int = 50):
    entries_dir = ROOMS_DIR / room_name / "world" / "entries"
    if not entries_dir.exists():
        return {"entries": []}
    entries = []
    for f in sorted(entries_dir.glob("*.yaml"))[-limit:]:
        e = atomic_read(f)
        if category and e.get("category") != category:
            continue
        entries.append(e)
    return {"entries": entries, "count": len(entries)}


@app.get("/rooms")
async def list_rooms():
    rooms = []
    for d in ROOMS_DIR.iterdir():
        if d.is_dir() and (d / "world" / "rooms").exists():
            rooms.append({"name": d.name, "path": str(d)})
    return {"rooms": rooms, "count": len(rooms)}


@app.get("/health")
async def health():
    return {"status": "ok", "rooms_dir": str(ROOMS_DIR),
            "rooms": len(list(ROOMS_DIR.iterdir())),
            "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rooms-dir", default=str(ROOMS_DIR))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    ROOMS_DIR = Path(args.rooms_dir)
    uvicorn.run(app, host=args.host, port=args.port)
