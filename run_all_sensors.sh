#!/bin/bash

set -e

cd ~/t4mh
source venv/bin/activate

mkdir -p logs

echo "Starting all sensor pipelines..."

python polar_run.py > logs/polar.log 2>&1 &
POLAR_PID=$!

python muse_notify.py > logs/muse.log 2>&1 &
MUSE_PID=$!

python respiration.py > logs/respiration.log 2>&1 &
RESP_PID=$!

python emotibit.py > logs/emotibit.log 2>&1 &
EMOTIBIT_PID=$!

echo
echo "Polar PID:       $POLAR_PID"
echo "Muse PID:        $MUSE_PID"
echo "Respiration PID: $RESP_PID"
echo "EmotiBit PID:    $EMOTIBIT_PID"
echo
echo "All sensors running."
echo "Logs are in ~/t4mh/logs/"
echo "Press Ctrl+C to stop everything."

cleanup() {
    echo
    echo "Stopping sensor pipelines..."

    kill $POLAR_PID 2>/dev/null || true
    kill $MUSE_PID 2>/dev/null || true
    kill $RESP_PID 2>/dev/null || true
    kill $EMOTIBIT_PID 2>/dev/null || true

    wait 2>/dev/null || true

    echo "Stopped."
}

trap cleanup INT TERM EXIT

wait
