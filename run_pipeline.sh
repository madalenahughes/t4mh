#!/usr/bin/env bash
set -euo pipefail

cd ~/biofeedback || exit

source venv/bin/activate
echo "🧪 venv activated."

TIMESTAMP="$(date +'%Y-%m-%d_%H-%M-%S')"
SESSION_ROOT="sessions"
SESSION_DIR="${SESSION_ROOT}/session_${TIMESTAMP}"
mkdir -p "$SESSION_DIR"
echo "🗂 Using session directory: $SESSION_DIR"

echo "📡 Starting polar_run.py..."
python3 polar_run.py &
POLAR_PID=$!
sleep 2

echo "🧠 Starting controller.py (will exit at EOF)..."
python3 controller.py
CTRL_EXIT=$?
echo "🔚 controller.py exited with code $CTRL_EXIT. Cleaning up..."

kill "$POLAR_PID" 2>/dev/null || true

echo "📦 Archiving session files into $SESSION_DIR ..."
LATEST_HRV="$(ls -1t session_*.csv 2>/dev/null | head -n 1 || true)"
if [ -n "$LATEST_HRV" ]; then
  echo "  → Copying HRV file: $LATEST_HRV"
  cp "$LATEST_HRV" "$SESSION_DIR/"
else
  echo "  ⚠️ No session_*.csv found to archive."
fi

if [ -f "stress_summary.csv" ]; then
  echo "  → Copying stress_summary.csv"
  cp "stress_summary.csv" "$SESSION_DIR/"
fi

if [ -d "logs" ]; then
  echo "  → Copying logs/ directory"
  cp -r "logs" "$SESSION_DIR/logs"
fi

echo "⭐️ Session archive complete: $SESSION_DIR"
