#!/bin/bash

# =============================================
#   NutriFriend AI - Update Daily Tips Script
#   Script-Controlled Model Selection
# =============================================

# Configuration
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
API_URL="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/tips_update.log"
API_LIMITER="$PROJECT_DIR/api_limiter.sh"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

# Ensure API Limiter is executable
chmod +x "$API_LIMITER"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting tips update (Smart Mode)..."

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
    log "[INFO] Processing user ID: $USER_ID"
    
    # === 1. FIND AVAILABLE MODEL ===
    SELECTED_MODEL=$("$API_LIMITER" available)
    
    if [ "$SELECTED_MODEL" = "NONE" ] || [ -z "$SELECTED_MODEL" ]; then
        log "[STOP] All models are on cooldown. Stopping update to save resources."
        break
    fi
    
    log "[INFO] Selected model: $SELECTED_MODEL"
    
    # === 2. CALL API WITH SELECTED MODEL ===
    RESPONSE=$(curl -s -X POST "$API_URL/users/$USER_ID/refresh-tips?model=$SELECTED_MODEL")
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" = "success" ]; then
        log "[SUCCESS] User $USER_ID tips updated using $SELECTED_MODEL"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        # === 3. HANDLE RATE LIMIT ===
        # If 503/429 occurs, mark this model as cooldown in local limiter
        if echo "$RESPONSE" | grep -qE "503|429|Resource has been exhausted"; then
            log "[RATE-LIMIT] Model $SELECTED_MODEL hit 429/503. Marking as cooldown."
            "$API_LIMITER" set "$SELECTED_MODEL"
            
            # Retry logic could go here, but for simplicity we skip to next user/loop
            FAIL_COUNT=$((FAIL_COUNT + 1))
        else
            log "[WARN] User $USER_ID update failed: $RESPONSE"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    # Small delay
    sleep 2
done

log "[DONE] Tips update completed. Success: $SUCCESS_COUNT, Failed: $FAIL_COUNT"
