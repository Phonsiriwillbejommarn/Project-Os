#!/bin/bash

# =============================================
#   NutriFriend AI - Regenerate Adaptive Plans
#   Run via cron every 7 days
#   Analyzes user adherence and adjusts plans
#   With Smart Rate Limit Detection
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

# ========================================
# Check API Rate Limit Status Before Start
# ========================================
log "[INFO] Checking API rate limit status..."

API_STATS=$(curl -s "$API_URL/api-stats")
COOLDOWN_MODELS=$(echo "$API_STATS" | grep -o '"cooldown_models":{[^}]*}' | cut -d'{' -f2 | cut -d'}' -f1)
RATE_LIMITED=$(echo "$API_STATS" | grep -o '"rate_limited_count":[0-9]*' | cut -d':' -f2)

if [ -n "$COOLDOWN_MODELS" ] && [ "$COOLDOWN_MODELS" != "" ]; then
    log "[WARN] Some models are on cooldown: $COOLDOWN_MODELS"
    log "[WARN] Will proceed but may use fallback models"
fi

if [ "${RATE_LIMITED:-0}" -gt 20 ]; then
    log "[WARN] High rate limit count ($RATE_LIMITED). Consider waiting before running."
fi

log "[INFO] API Stats - Rate limited: ${RATE_LIMITED:-0} times"

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
    
    # Check rate limit before each call
    API_CHECK=$(curl -s "$API_URL/api-stats")
    COOLDOWN_CHECK=$(echo "$API_CHECK" | grep -o '"cooldown_models":{[^}]*}')
    
    # If all models on cooldown, wait
    ALL_MODELS_DOWN=$(echo "$COOLDOWN_CHECK" | grep -c "gemini-3-flash-preview.*gemini-2.5-flash-lite.*gemini-2.5-flash.*gemma-3-27b-it")
    
    if [ "$ALL_MODELS_DOWN" -gt 0 ]; then
        log "[COOLDOWN] All models are on cooldown. Waiting 60 seconds..."
        sleep 60
    fi
    
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
    elif echo "$RESPONSE" | grep -q "cooldown"; then
        log "[SKIPPED] User $USER_ID - API on cooldown, will retry next run"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
    else
        log "[WARN] User $USER_ID failed: $RESPONSE"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Delay to avoid rate limiting (increased from 3 to 5 seconds)
    sleep 5
done

# Final API stats
FINAL_STATS=$(curl -s "$API_URL/api-stats")
FINAL_SAVED=$(echo "$FINAL_STATS" | grep -o '"saved_calls":[0-9]*' | cut -d':' -f2)
FINAL_EFFICIENCY=$(echo "$FINAL_STATS" | grep -o '"efficiency":"[^"]*"' | cut -d'"' -f4)

log "=========================================="
log "Summary:"
log "  Total users: $TOTAL_USERS"
log "  Success: $SUCCESS_COUNT"
log "  Plans adjusted: $ADJUSTED_COUNT"
log "  Skipped (cooldown): $SKIPPED_COUNT"
log "  Failed: $FAIL_COUNT"
log "=========================================="
log "API Efficiency:"
log "  Calls saved by cooldown: ${FINAL_SAVED:-0}"
log "  Efficiency: ${FINAL_EFFICIENCY:-N/A}"
log "=========================================="
log "[DONE] Adaptive plan regeneration completed"
