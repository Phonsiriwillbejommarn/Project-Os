#!/bin/bash

# =============================================
#   NutriFriend AI - Regenerate Adaptive Plans
#   Run via cron every 7 days
#   Analyzes user adherence and adjusts plans
# =============================================

# Configuration
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
API_URL="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/adaptive_plan.log"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Starting Adaptive Plan Regeneration"
log "=========================================="

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

# Process each user
SUCCESS_COUNT=0
ADJUSTED_COUNT=0
FAIL_COUNT=0

for USER_ID in $USER_IDS; do
    log "[INFO] Processing user ID: $USER_ID"
    
    # Call adaptive-plan API
    RESPONSE=$(curl -s -X POST "$API_URL/users/$USER_ID/adaptive-plan")
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    CAN_FOLLOW=$(echo "$RESPONSE" | grep -o '"can_follow":[^,}]*' | cut -d':' -f2)
    ADHERENCE=$(echo "$RESPONSE" | grep -o '"adherence_rate":[^,}]*' | cut -d':' -f2)
    
    if [ "$STATUS" = "success" ]; then
        log "[SUCCESS] User $USER_ID - Adherence: $ADHERENCE% - Can follow: $CAN_FOLLOW"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        
        if [ "$CAN_FOLLOW" = "false" ]; then
            log "[ADJUSTED] User $USER_ID plan was adjusted to be easier"
            ADJUSTED_COUNT=$((ADJUSTED_COUNT + 1))
        fi
    else
        log "[WARN] User $USER_ID failed: $RESPONSE"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Delay to avoid rate limiting
    sleep 3
done

log "=========================================="
log "Summary:"
log "  Total processed: $((SUCCESS_COUNT + FAIL_COUNT))"
log "  Success: $SUCCESS_COUNT"
log "  Plans adjusted: $ADJUSTED_COUNT"
log "  Failed: $FAIL_COUNT"
log "=========================================="
log "[DONE] Adaptive plan regeneration completed"
