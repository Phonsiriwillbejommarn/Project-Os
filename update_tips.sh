#!/bin/bash

# =============================================
#   NutriFriend AI - Update Daily Tips Script
#   Run via cron every 3 hours to refresh tips
# =============================================

# Configuration
PROJECT_DIR="/home/pi/nutrifriend-ai-2"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
API_URL="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/tips_update.log"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting tips update..."

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    log "[ERROR] Database not found: $DB_FILE"
    exit 1
fi

# Check if server is running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
    log "[ERROR] Server is not running at $API_URL"
    exit 1
fi

# Get all user IDs from database
USER_IDS=$(sqlite3 "$DB_FILE" "SELECT id FROM user_profiles;")

if [ -z "$USER_IDS" ]; then
    log "[INFO] No users found in database"
    exit 0
fi

# Update tips for each user
SUCCESS_COUNT=0
FAIL_COUNT=0

for USER_ID in $USER_IDS; do
    log "[INFO] Updating tips for user ID: $USER_ID"
    
    RESPONSE=$(curl -s -X POST "$API_URL/users/$USER_ID/refresh-tips")
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" = "success" ]; then
        log "[SUCCESS] User $USER_ID tips updated"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        log "[WARN] User $USER_ID update failed: $RESPONSE"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Small delay to avoid rate limiting
    sleep 2
done

log "[DONE] Tips update completed. Success: $SUCCESS_COUNT, Failed: $FAIL_COUNT"
