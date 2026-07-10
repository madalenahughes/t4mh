#!/bin/bash

echo "=== Starting Biofeedback System ==="

# Move to project directory
cd ~/biofeedback || exit

# Activate virtual environment
echo "→ Activating virtual environment..."
source venv/bin/activate

# Kill any previous instances cleanly
echo "→ Killing old processes..."
pkill -f polar_run.py 2>/dev/null || true
pkill -f polar_baseline.py 2>/dev/null || true

# Optional: restart Bluetooth if desired
# echo "→ Restarting Bluetooth..."
# sudo systemctl restart bluetooth

# Start the pipeline
echo "→ Running polar_run.py..."
python3 polar_run.py
