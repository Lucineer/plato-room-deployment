# PLATO Rooms — Deployment Options

Every PLATO room is a git repo with `world/commands/` as input and bridge engines as processors. The question is: **how do commands get in and engines get triggered?**

Here are five ways to run a room, from zero-infra to fully hosted.

---

## Option 1: Local File Watcher (Zero Infra)

No server, no git remote, no cron. Just a process watching a folder.

**How it works:**
- Agent writes YAML to `world/commands/`
- `inotifywait` detects the new file immediately
- Engine runs, processes commands, updates room state
- Agent reads `world/rooms/*.yaml` for results

**Setup:**
```bash
# One-time: install inotify-tools
sudo apt install inotify-tools  # or: pip install inotify-hookable

# Run the watcher
inotifywait -m world/commands/ -e create,moved_to --format '%w%f' | \
  while read filepath; do
    sleep 0.2  # let file finish writing
    python3 bridges/study_engine.py --world-dir world
  done
```

**Pros:** Instant response, zero infrastructure, works offline
**Cons:** Process must stay alive, no git history of turns
**Best for:** Single-machine development, Jetson edge, ESP32 tethered mode

---

## Option 2: Bare Git + Post-Receive Hook (Self-Hosted)

A local bare git repo. Agents push to it, hook fires the engine. No GitHub required.

**How it works:**
- Bare repo lives on the host machine (or any SSH-accessible server)
- Agent clones, works, pushes — standard git workflow
- Post-receive hook checks out working copy, runs engine, commits state back
- Full git history preserved

**Setup:**
```bash
# On the host (Jetson, VPS, whatever)
mkdir -p /srv/plato-rooms/study.git
cd /srv/plato-rooms/study.git && git init --bare

# Create the post-receive hook
cat > hooks/post-receive << 'HOOK'
#!/bin/bash
WORK_DIR=/srv/plato-rooms/study-working
mkdir -p "$WORK_DIR"
GIT_WORK_TREE="$WORK_DIR" git checkout -f
cd "$WORK_DIR"
python3 bridges/study_engine.py --world-dir world
git add -A
git diff --staged --quiet || git commit -m "turn: $(date -u +%Y%m%d-%H%M%S)"
GIT_DIR="/srv/plato-rooms/study.git" git push
HOOK
chmod +x hooks/post-receive

# Agent clones and works
git clone /srv/plato-rooms/study.git /tmp/my-study
cd /tmp/my-study
# Write command, push → engine fires
echo "agent: ptx-researcher
action: journal
expert_id: ptx-1
type: finding
content: mul.wide.u32 is the only way to widen u32 to u64" > world/commands/001.yaml
git add -A && git commit -m "journal entry" && git push
```

**Pros:** Full git history, works over SSH, no cloud dependency, agents use standard git
**Cons:** Need SSH access to host, one bare repo per room
**Best for:** Fleet of agents on same network, air-gapped environments, development

---

## Option 3: Systemd Timer + Cron (Polling)

No file watcher, no git hooks. Just a timer that processes turns on a schedule.

**How it works:**
- Agent writes YAML to `world/commands/` (locally or via shared filesystem)
- Systemd timer or cron runs engine every N seconds
- Room state updated in-place

**Setup:**
```bash
# Systemd timer (preferred — more control than cron)
cat > ~/.config/systemd/user/plato-study.service << 'EOF'
[Unit]
Description=PLATO Study Room Turn Processor
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/srv/plato-rooms/study
ExecStart=/usr/bin/python3 bridges/study_engine.py --world-dir world
EOF

cat > ~/.config/systemd/user/plato-study.timer << 'EOF'
[Unit]
Description=Run PLATO Study turns every 30 seconds

[Install]
WantedBy=timers.target

[Timer]
OnBootSec=30sec
OnUnitActiveSec=30sec
AccuracySec=5sec
EOF

systemctl --user enable --now plato-study.timer
journalctl --user -u plato-study -f  # watch it work
```

```bash
# Cron alternative (simpler, less precise)
# Every 30 seconds via crontab trick:
* * * * * for i in 0 1; do sleep 15; cd /srv/plato-rooms/study && python3 bridges/study_engine.py --world-dir world; done
```

**Pros:** Dead simple, systemd handles restarts, works on any Linux, no git needed
**Cons:** Polling delay (up to N seconds), no push-based triggering
**Best for:** Background rooms, Jetson services, ESP32 with SD card storage

---

## Option 4: HTTP API (Any Server)

A tiny web server that accepts POST commands and returns results. Agents talk HTTP.

**How it works:**
- FastAPI/Flask server exposes endpoints per room action
- Agent POSTs command JSON → server writes YAML → runs engine → returns result
- Room state accessible via GET endpoints
- Can run behind any HTTP server (nginx, caddy, etc.)

**Setup:**
```bash
pip install fastapi uvicorn

# Server (one file, ~40 lines)
cat > plato_server.py << 'PYEOF'
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import yaml, importlib.util, tempfile, os

app = FastAPI()
ROOMS = {}  # room_name -> engine module

class Command(BaseModel):
    agent: str
    action: str
    **kwargs  # action-specific fields

def load_engine(room_dir: Path):
    engine_path = room_dir / "bridges" / f"{room_dir.name.replace('plato-','')}_engine.py"
    spec = importlib.util.spec_from_file_location("engine", engine_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@app.post("/room/{room}/command")
async def run_command(room: str, cmd: dict):
    room_dir = Path(f"/srv/plato-rooms/{room}")
    if not room_dir.exists():
        raise HTTPException(404, f"Room {room} not found")
    
    # Write command YAML
    cmd_id = f"{os.urandom(4).hex()}"
    cmd_path = room_dir / "world" / "commands" / f"{cmd_id}.yaml"
    cmd_path.parent.mkdir(parents=True, exist_ok=True)
    cmd_path.write_text(yaml.dump(cmd))
    
    # Process
    mod = load_engine(room_dir)
    mod.process_turns()
    
    # Read latest log for result
    logs = sorted((room_dir / "world" / "logs").glob("*.yaml"))
    if logs:
        return yaml.safe_load(logs[-1].read_text())
    return {"status": "processed"}

@app.get("/room/{room}/status")
async def room_status(room: str):
    room_file = Path(f"/srv/plato-rooms/{room}/world/rooms/{room}.yaml")
    if room_file.exists():
        return yaml.safe_load(room_file.read_text())
    return {"error": "room state not found"}

@app.get("/room/{room}/experts")
async def list_experts(room: str):
    experts = []
    for f in Path(f"/srv/plato-rooms/{room}/world/experts").glob("*.yaml"):
        experts.append(yaml.safe_load(f.read_text()))
    return {"experts": experts}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
PYEOF

# Run
python3 plato_server.py

# Agent usage:
# curl -X POST http://localhost:8100/room/study/command \
#   -H "Content-Type: application/json" \
#   -d '{"agent":"ptx-researcher","action":"journal","expert_id":"ptx-1","type":"finding","content":"discovery"}'
#
# curl http://localhost:8100/room/study/status
# curl http://localhost:8100/room/study/experts
```

**Pros:** Language-agnostic API, works over network, any agent can participate, web dashboard possible
**Cons:** Needs a running server process, more attack surface, needs auth for production
**Best for:** Multi-machine fleets, web UIs, non-git agents, PLATO Office integration

---

## Option 5: GitHub Actions / Codespaces (Cloud)

The default we've been using. GitHub Actions CI processes turns on push.

**How it works:**
- Room is a GitHub repo
- Agent pushes to `world/commands/`
- GitHub Actions workflow triggers, runs engine on runner
- Engine commits state back, pushes

**Setup:**
Already built into every room. The `.github/workflows/*.yml` files.

**For Codespaces specifically:**
```bash
# Create a devcontainer.json in the room repo
cat > .devcontainer/devcontainer.json << 'EOF'
{
  "name": "PLATO Study Room",
  "features": {"ghcr.io/devcontainers/features/python:1": {}},
  "forwardPorts": [8100],
  "postCreateCommand": "pip install fastapi uvicorn pyyaml && python3 plato_server.py",
  "remoteUser": "codespace"
}
EOF
# Open in Codespaces → full room server running in cloud
```

**Pros:** Free runners, automatic scaling, built-in auth, Codespaces for instant dev environments
**Cons:** Requires GitHub, runner cold-start latency (~20-60s), push delay
**Best for:** Open source rooms, distributed teams, quick prototyping

---

## Comparison Matrix

| | Latency | Infrastructure | Git History | Offline | Auth |
|---|---|---|---|---|---|
| File Watcher | ~0.1s | None | No | Yes | N/A |
| Bare Git Hook | ~1s | SSH host | Yes | No | SSH keys |
| Systemd Timer | 1-30s | None | No | Yes | N/A |
| HTTP API | ~0.1s | Server | Optional | Yes | API key |
| GitHub Actions | 20-60s | GitHub | Yes | No | GitHub auth |

---

## Hybrid Mode

The best setups combine options:

- **Jetson**: File Watcher + Systemd Timer (local processing, always on)
- **Fleet sync**: Bare Git Hook on VPS (agents push findings, central coordination)
- **Public rooms**: GitHub Actions (open contribution, CI validation)
- **Web access**: HTTP API wrapping any of the above (dashboard, PLATO Office bridge)

A room can use multiple triggers simultaneously. The engine doesn't care HOW commands arrive — it just processes YAML files in `world/commands/`.

---

## Room Engine Contract

All engines follow the same contract, making them portable across all five options:

```
Input:  world/commands/*.yaml  (agent writes these)
Output: world/rooms/*.yaml    (room state)
        world/logs/*.yaml     (turn history)
        world/{domain}/*.yaml (room-specific state)
Engine: bridges/{room}_engine.py --world-dir world
```

Any trigger mechanism that writes YAML to `world/commands/` and runs the engine works.
