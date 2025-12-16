#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "Starting NutriFriend AI on Raspberry Pi..."

# Navigate to backend
cd backend

# Check for virtual environment and activate it
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "WARNING: No virtual environment found. Running with system python."
fi

# Install dependencies if needed (optional, can be commented out to speed up start)
# pip install -r requirements.txt

# Run the server
# host 0.0.0.0 allows access from other devices on the network
# port 8000 is standard
echo "Server running at http://localhost:8000"
echo "To access from other devices, use http://<PI_IP_ADDRESS>:8000"
uvicorn main:app --host 0.0.0.0 --port 8000
