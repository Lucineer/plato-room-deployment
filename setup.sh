#!/bin/bash
# PLATO Room — Quick Setup Script
# Sets up a room with any deployment option
# Usage: ./setup.sh <room-name> <option> [path]
# Options: watcher | git-hook | systemd | http | github

set -e

ROOM_NAME="${1:?Usage: setup.sh <room-name> <option> [path]}"
OPTION="${2:?Options: watcher | git-hook | systemd | http | github}"
ROOM_PATH="${3:-$(pwd)/../$ROOM_NAME}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== PLATO Room Setup ==="
echo "Room: $ROOM_NAME"
echo "Option: $OPTION"
echo "Path: $ROOM_PATH"
echo ""

case "$OPTION" in
    watcher)
        echo "→ Installing file watcher..."
        chmod +x "$SCRIPT_DIR/watchers/file-watcher.sh"
        echo "  Run: $SCRIPT_DIR/watchers/file-watcher.sh $ROOM_PATH/world"
        echo "  Requires: sudo apt install inotify-tools"
        ;;
    git-hook)
        BARE="${ROOM_PATH}.git"
        echo "→ Setting up bare git repo..."
        mkdir -p "$BARE"
        cd "$BARE" && git init --bare
        cp "$SCRIPT_DIR/git-hooks/post-receive" "$BARE/hooks/post-receive"
        chmod +x "$BARE/hooks/post-receive"
        echo "  Bare repo: $BARE"
        echo "  Clone: git clone $BARE /tmp/$ROOM_NAME"
        echo "  Push commands → engine fires automatically"
        ;;
    systemd)
        echo "→ Installing systemd timer..."
        chmod +x "$SCRIPT_DIR/systemd/install-room.sh"
        bash "$SCRIPT_DIR/systemd/install-room.sh" "$ROOM_NAME" "$ROOM_PATH"
        ;;
    http)
        echo "→ Setting up HTTP API server..."
        pip install fastapi uvicorn pyyaml 2>/dev/null || pip3 install fastapi uvicorn pyyaml
        echo "  Run: python3 $SCRIPT_DIR/http-api/plato_server.py --rooms-dir $(dirname $ROOM_PATH) --port 8100"
        echo "  Or: docker compose -f $SCRIPT_DIR/docker-compose.yml up"
        ;;
    github)
        echo "→ Room already configured for GitHub Actions."
        echo "  The .github/workflows/*.yml in the room repo handles everything."
        echo "  Just push to GitHub and it works."
        ;;
    *)
        echo "Unknown option: $OPTION"
        echo "Options: watcher | git-hook | systemd | http | github"
        exit 1
        ;;
esac

echo ""
echo "✓ Done."
