#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Run main_process.py in the background with output redirected to a log file
nohup python src/main_process.py data/download --archive-dir data/archive --use-openai > processing.log 2>&1 &

# Get the process ID
PID=$!

# Save the PID to a file
echo $PID > process.pid

echo "Process started with PID: $PID"
echo "Output is being logged to: processing.log"
echo "To check the progress, use: tail -f processing.log"
echo "To stop the process, use: kill $(cat process.pid)"
