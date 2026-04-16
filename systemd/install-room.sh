#!/bin/bash
# PLATO Room — Install a room as a systemd service
# Usage: ./systemd/install-room.sh study /srv/plato-rooms/study

ROOM_NAME="${1:?Usage: install-room.sh <name> <path>}"
ROOM_PATH="${2:?Usage: install-room.sh <name> <path>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ROOM_PATH/bridges" ]; then
    echo "ERROR: $ROOM_PATH/bridges/ not found. Is this a PLATO room?"
    exit 1
fi

echo "Installing PLATO room '$ROOM_NAME' from $ROOM_PATH"

# Copy service and timer files
mkdir -p ~/.config/systemd/user
cp "$SCRIPT_DIR/plato-room@.service" ~/.config/systemd/user/
cp "$SCRIPT_DIR/plato-room@.timer" ~/.config/systemd/user/

# Create a drop-in override for this specific room's path
mkdir -p ~/.config/systemd/user/plato-room@${ROOM_NAME}.service.d
cat > ~/.config/systemd/user/plato-room@${ROOM_NAME}.service.d/override.conf << EOF
[Service]
WorkingDirectory=$ROOM_PATH
ExecStart=
ExecStart=/usr/bin/python3 $ROOM_PATH/bridges/${ROOM_NAME}_engine.py --world-dir world
EOF

# Reload and enable
systemctl --user daemon-reload
systemctl --user enable --now "plato-room@${ROOM_NAME}.timer"

echo "✓ Room '$ROOM_NAME' installed and running"
echo "  Timer: plato-room@${ROOM_NAME}.timer (every 30s)"
echo "  Logs:  journalctl --user -u plato-room@${ROOM_NAME} -f"
echo "  Stop:  systemctl --user stop plato-room@${ROOM_NAME}.timer"
echo "  Status: systemctl --user status plato-room@${ROOM_NAME}"
