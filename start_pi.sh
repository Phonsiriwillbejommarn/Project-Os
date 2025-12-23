#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"



echo "=========================================="
echo "   🚀 NutriFriend AI - Auto Start Script"
echo "=========================================="

# 1. Build Frontend
echo "[1/3] 🏗️  Checking Frontend..."
cd frontend

# Check if build exists and --rebuild flag is NOT present
if [ -d "dist" ] && [[ "$*" != *"--rebuild"* ]]; then
    echo "✅ Build found! Skipping build process (Use --rebuild to force)."
else
    echo "⚙️  Building Frontend..."
    if [ ! -d "node_modules" ]; then
        npm install --silent
    fi
    npm run build
fi
cd ..

# 2. Setup Backend
echo "[2/3] 🐍 Setting up Python Environment..."
cd backend
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
fi
pip install -r requirements.txt --quiet

# 3. Network & Server
echo "[3/3] 🟢 Starting Services..."

# Get Local IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1)

echo ""
echo "=================================================="
echo "📲 Local Access (Wi-Fi):  http://$LOCAL_IP:8000"
echo "=================================================="

# Run Uvicorn
echo ""
echo "🚀 Server is running! (Press Ctrl+C to stop)"
echo ""
uvicorn main:app --host 0.0.0.0 --port 8000
