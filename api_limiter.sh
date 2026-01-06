#!/bin/bash

# =============================================
#   NutriFriend AI - API Rate Limit Manager
#   Shell-based cooldown tracking system
# =============================================

# Configuration
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
COOLDOWN_FILE="$PROJECT_DIR/logs/api_cooldown.txt"
COOLDOWN_DURATION=300  # 5 minutes in seconds
LOG_FILE="$PROJECT_DIR/logs/rate_limit.log"

# Models list
MODELS=("gemini-3-flash-preview" "gemini-2.5-flash-lite" "gemini-2.5-flash" "gemma-3-27b-it")

# Create directories
mkdir -p "$PROJECT_DIR/logs"
touch "$COOLDOWN_FILE"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Set cooldown for a model
set_cooldown() {
    local model=$1
    local expire_time=$(($(date +%s) + COOLDOWN_DURATION))
    
    # Remove old entry if exists
    grep -v "^$model:" "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" 2>/dev/null || true
    mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE" 2>/dev/null || true
    
    # Add new entry
    echo "$model:$expire_time" >> "$COOLDOWN_FILE"
    log "[COOLDOWN] Model $model set to cooldown until $(date -d @$expire_time '+%Y-%m-%d %H:%M:%S')"
}

# Check if model is on cooldown
is_on_cooldown() {
    local model=$1
    local now=$(date +%s)
    
    # Read cooldown file
    if [ -f "$COOLDOWN_FILE" ]; then
        local expire_time=$(grep "^$model:" "$COOLDOWN_FILE" | cut -d':' -f2)
        if [ -n "$expire_time" ] && [ "$expire_time" -gt "$now" ]; then
            local remaining=$((expire_time - now))
            log "[COOLDOWN] Model $model is on cooldown. $remaining seconds remaining."
            return 0  # true - is on cooldown
        fi
    fi
    return 1  # false - not on cooldown
}

# Get first available model
get_available_model() {
    for model in "${MODELS[@]}"; do
        if ! is_on_cooldown "$model"; then
            echo "$model"
            return 0
        fi
    done
    echo ""
    return 1
}

# Clean expired cooldowns
clean_expired() {
    local now=$(date +%s)
    local cleaned=0
    
    if [ -f "$COOLDOWN_FILE" ]; then
        while IFS=: read -r model expire_time; do
            if [ -n "$expire_time" ] && [ "$expire_time" -le "$now" ]; then
                log "[CLEANED] Cooldown expired for $model"
                cleaned=$((cleaned + 1))
            fi
        done < "$COOLDOWN_FILE"
        
        # Remove expired entries
        awk -F: -v now="$now" '$2 > now' "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" 2>/dev/null || true
        mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE" 2>/dev/null || true
    fi
    
    echo "$cleaned"
}

# Show status
show_status() {
    echo "=============================================="
    echo "   API Rate Limit Status"
    echo "   Time: $(date)"
    echo "=============================================="
    echo ""
    
    local now=$(date +%s)
    local available=0
    local cooldown=0
    
    for model in "${MODELS[@]}"; do
        if [ -f "$COOLDOWN_FILE" ]; then
            local expire_time=$(grep "^$model:" "$COOLDOWN_FILE" | cut -d':' -f2)
            if [ -n "$expire_time" ] && [ "$expire_time" -gt "$now" ]; then
                local remaining=$((expire_time - now))
                echo "  [COOLDOWN] $model - ${remaining}s remaining"
                cooldown=$((cooldown + 1))
            else
                echo "  [READY] $model"
                available=$((available + 1))
            fi
        else
            echo "  [READY] $model"
            available=$((available + 1))
        fi
    done
    
    echo ""
    echo "  Available: $available / ${#MODELS[@]}"
    echo "  On Cooldown: $cooldown"
    echo "=============================================="
}

# Check if safe to call API
can_call_api() {
    clean_expired > /dev/null
    local model=$(get_available_model)
    if [ -n "$model" ]; then
        echo "OK:$model"
        return 0
    else
        echo "BLOCKED:All models on cooldown"
        return 1
    fi
}

# Main command handler
case "${1:-status}" in
    "set")
        if [ -n "$2" ]; then
            set_cooldown "$2"
        else
            echo "Usage: $0 set <model_name>"
        fi
        ;;
    "check")
        if [ -n "$2" ]; then
            if is_on_cooldown "$2"; then
                echo "COOLDOWN"
                exit 1
            else
                echo "OK"
                exit 0
            fi
        else
            echo "Usage: $0 check <model_name>"
        fi
        ;;
    "available")
        model=$(get_available_model)
        if [ -n "$model" ]; then
            echo "$model"
            exit 0
        else
            echo "NONE"
            exit 1
        fi
        ;;
    "can-call")
        can_call_api
        ;;
    "clean")
        cleaned=$(clean_expired)
        echo "Cleaned $cleaned expired cooldowns"
        ;;
    "status"|*)
        show_status
        ;;
esac
