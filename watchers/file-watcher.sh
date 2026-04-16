#!/bin/bash
# PLATO Room — Local File Watcher
# Usage: ./watchers/file-watcher.sh /path/to/room/world
# Requires: inotify-tools (apt install inotify-tools)

WORLD_DIR="${1:-world}"
COMMANDS_DIR="$WORLD_DIR/commands"
ENGINE_DIR="$(dirname "$(dirname "$0")")"

if ! command -v inotifywait &>/dev/null; then
    echo "ERROR: inotify-tools not installed. Run: sudo apt install inotify-tools"
    exit 1
fi

if [ ! -d "$COMMANDS_DIR" ]; then
    echo "Creating $COMMANDS_DIR"
    mkdir -p "$COMMANDS_DIR"
fi

echo "Watching $COMMANDS_DIR for new commands..."
echo "Press Ctrl+C to stop."

inotifywait -m "$COMMANDS_DIR" -e create,moved_to --format '%w%f' 2>/dev/null | while read filepath; do
    sleep 0.2  # Let file finish writing
    echo "[$(date -u +%Y%m%d-%H%M%S)] Processing: $(basename "$filepath")"
    python3 "$ENGINE_DIR/bridges/"*"_engine.py" --world-dir "$WORLD_DIR" 2>&1
done
