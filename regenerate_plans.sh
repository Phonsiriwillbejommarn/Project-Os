#!/bin/bash

# =============================================
#   NutriFriend AI - Regenerate Adaptive Plans
#   Script-Controlled Model Selection
# =============================================

# Configuration
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
API_URL="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/adaptive_plan.log"
API_LIMITER="$PROJECT_DIR/api_limiter.sh"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

# Ensure API Limiter is executable
chmod +x "$API_LIMITER"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting Adaptive Plan Regeneration (Smart Mode)..."

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

# Count total users
TOTAL_USERS=$(echo "$USER_IDS" | wc -l | tr -d ' ')
log "[INFO] Found $TOTAL_USERS users to process"

# Process each user
SUCCESS_COUNT=0
ADJUSTED_COUNT=0
FAIL_COUNT=0
SKIPPED_COUNT=0
CURRENT=0

for USER_ID in $USER_IDS; do
    CURRENT=$((CURRENT + 1))
    log "[INFO] Processing user $CURRENT/$TOTAL_USERS (ID: $USER_ID)"
    
    # === 1. FIND AVAILABLE MODEL ===
    SELECTED_MODEL=$("$API_LIMITER" available)
    
    if [ "$SELECTED_MODEL" = "NONE" ] || [ -z "$SELECTED_MODEL" ]; then
        log "[STOP] All models are on cooldown. Waiting 60 seconds..."
        sleep 60
        # Try again after sleep
        SELECTED_MODEL=$("$API_LIMITER" available)
        if [ "$SELECTED_MODEL" = "NONE" ] || [ -z "$SELECTED_MODEL" ]; then
            log "[STOP] Still no models available. Skipping this run."
            break
        fi
    fi
    
    log "[INFO] Selected model: $SELECTED_MODEL"
    
    # === 2. CALL API WITH SELECTED MODEL ===
    RESPONSE=$(curl -s -X POST "$API_URL/users/$USER_ID/adaptive-plan?model=$SELECTED_MODEL")
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    CAN_FOLLOW=$(echo "$RESPONSE" | grep -o '"can_follow":[^,}]*' | cut -d':' -f2)
    ADHERENCE=$(echo "$RESPONSE" | grep -o '"adherence_rate":[^,}]*' | cut -d':' -f2)
    
    if [ "$STATUS" = "success" ]; then
        log "[SUCCESS] User $USER_ID - Adherence: $ADHERENCE% - Can follow: $CAN_FOLLOW (Model: $SELECTED_MODEL)"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        
        if [ "$CAN_FOLLOW" = "false" ]; then
            log "[ADJUSTED] User $USER_ID plan was adjusted to be easier"
            ADJUSTED_COUNT=$((ADJUSTED_COUNT + 1))
        fi
    else
        # === 3. HANDLE RATE LIMIT ===
        if echo "$RESPONSE" | grep -qE "503|429|Resource has been exhausted"; then
            log "[RATE-LIMIT] Model $SELECTED_MODEL hit 429/503. Marking as cooldown."
            "$API_LIMITER" set "$SELECTED_MODEL"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            log "[WARN] User $USER_ID failed: $RESPONSE"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    # Delay to avoid rate limiting
    sleep 5
done

log "=========================================="
log "Summary:"
log "  Total users: $TOTAL_USERS"
log "  Success: $SUCCESS_COUNT"
log "  Plans adjusted: $ADJUSTED_COUNT"
log "  Skipped/RateLimited: $SKIPPED_COUNT"
log "  Failed: $FAIL_COUNT"
log "=========================================="
log "[DONE] Adaptive plan regeneration completed"
