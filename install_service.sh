#!/bin/bash

# =============================================
#   NutriFriend AI - Install Auto-Start Service
#   Run this script to enable auto-start on boot
# =============================================

echo "=============================================="
echo "   Installing NutriFriend Auto-Start Service"
echo "=============================================="
echo ""

# Define paths
SERVICE_NAME="nutrifriend"
SERVICE_FILE="/home/pi/nutrifriend-ai-2/nutrifriend.service"
SYSTEMD_PATH="/etc/systemd/system/$SERVICE_NAME.service"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run this script with sudo"
    echo "Usage: sudo ./install_service.sh"
    exit 1
fi

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "[ERROR] Service file not found: $SERVICE_FILE"
    exit 1
fi

# Copy service file to systemd
echo "[INFO] Installing service file..."
cp "$SERVICE_FILE" "$SYSTEMD_PATH"

# Set permissions
chmod 644 "$SYSTEMD_PATH"

# Reload systemd daemon
echo "[INFO] Reloading systemd daemon..."
systemctl daemon-reload

# Enable service to start on boot
echo "[INFO] Enabling auto-start on boot..."
systemctl enable $SERVICE_NAME

# Start the service now
echo "[INFO] Starting service..."
systemctl start $SERVICE_NAME

# Check status
echo ""
echo "=============================================="
echo "   Installation Complete"
echo "=============================================="
echo ""
systemctl status $SERVICE_NAME --no-pager
echo ""
echo "[INFO] Service Commands:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "[INFO] The server will now start automatically when Pi boots!"
