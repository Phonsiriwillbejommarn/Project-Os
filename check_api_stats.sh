#!/bin/bash

# =============================================
#   NutriFriend AI - API Stats Monitor
#   Check API usage, rate limits, and cooldowns
# =============================================

# Configuration
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
API_URL="http://localhost:8000"
LOG_FILE="$PROJECT_DIR/logs/api_stats.log"

# Create log directory
mkdir -p "$PROJECT_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=============================================="
echo "   NutriFriend AI - API Stats Monitor"
echo "   Time: $(date)"
echo "=============================================="
echo ""

# Check if server is running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Server is not running at $API_URL${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Server is running${NC}"
echo ""

# Get API stats
STATS=$(curl -s "$API_URL/api-stats")

if [ -z "$STATS" ]; then
    echo -e "${RED}[ERROR] Could not get API stats${NC}"
    exit 1
fi

# Parse JSON response using grep and cut
TOTAL_CALLS=$(echo "$STATS" | grep -o '"total_api_calls":[0-9]*' | cut -d':' -f2)
RATE_LIMITED=$(echo "$STATS" | grep -o '"rate_limited_count":[0-9]*' | cut -d':' -f2)
SAVED_CALLS=$(echo "$STATS" | grep -o '"saved_calls":[0-9]*' | cut -d':' -f2)
EFFICIENCY=$(echo "$STATS" | grep -o '"efficiency":"[^"]*"' | cut -d'"' -f4)
COOLDOWN_MODELS=$(echo "$STATS" | grep -o '"cooldown_models":{[^}]*}' | cut -d'{' -f2 | cut -d'}' -f1)

echo "=============================================="
echo "   API Usage Statistics"
echo "=============================================="
echo ""
echo -e "  Total API Calls:     ${BLUE}${TOTAL_CALLS:-0}${NC}"
echo -e "  Rate Limited:        ${YELLOW}${RATE_LIMITED:-0}${NC}"
echo -e "  Saved Calls:         ${GREEN}${SAVED_CALLS:-0}${NC}"
echo -e "  Efficiency:          ${GREEN}${EFFICIENCY:-N/A}${NC}"
echo ""

# Check cooldown status
echo "=============================================="
echo "   Cooldown Status"
echo "=============================================="
echo ""

if [ -z "$COOLDOWN_MODELS" ] || [ "$COOLDOWN_MODELS" = "" ]; then
    echo -e "  ${GREEN}No models on cooldown - All systems ready${NC}"
else
    echo -e "  ${YELLOW}Models on cooldown:${NC}"
    echo "  $COOLDOWN_MODELS"
fi
echo ""

# Rate limit warning
if [ "${RATE_LIMITED:-0}" -gt 10 ]; then
    echo -e "${RED}[WARNING] High rate limit count! Consider:${NC}"
    echo "  - Increasing cache TTL"
    echo "  - Adding more fallback models"
    echo "  - Reducing API call frequency"
    echo ""
fi

# Log to file
{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API Stats: calls=$TOTAL_CALLS limited=$RATE_LIMITED saved=$SAVED_CALLS efficiency=$EFFICIENCY"
} >> "$LOG_FILE"

echo "=============================================="
echo "   Recommendations"
echo "=============================================="
echo ""

if [ "${RATE_LIMITED:-0}" -eq 0 ]; then
    echo -e "  ${GREEN}[HEALTHY] No rate limits detected${NC}"
elif [ "${RATE_LIMITED:-0}" -lt 5 ]; then
    echo -e "  ${YELLOW}[OK] Minor rate limiting - System adapting${NC}"
else
    echo -e "  ${RED}[ACTION NEEDED] Frequent rate limits${NC}"
    echo "  Consider reducing API call frequency"
fi

echo ""
echo "[DONE] Stats logged to: $LOG_FILE"
