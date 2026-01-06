#!/bin/bash

# =============================================
#   NutriFriend AI - Log Analyzer Script
#   Analyze API errors and rate limits
# =============================================

# Define paths
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
LOG_FILE="${1:-/var/log/syslog}"
OUTPUT_DIR="$PROJECT_DIR/logs"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Date for report
DATE=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$OUTPUT_DIR/log_report_$DATE.txt"

echo "=============================================="
echo "   NutriFriend AI - Log Analyzer"
echo "   Analysis Time: $(date)"
echo "=============================================="
echo ""

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "[ERROR] Log file not found: $LOG_FILE"
    echo "Usage: $0 [log_file_path]"
    echo "Example: $0 /var/log/syslog"
    exit 1
fi

echo "[INFO] Analyzing: $LOG_FILE"
echo ""

# Start report
{
    echo "=============================================="
    echo "   NutriFriend AI - Log Analysis Report"
    echo "   Generated: $(date)"
    echo "   Source: $LOG_FILE"
    echo "=============================================="
    echo ""

    # 1. API Rate Limit Errors (429)
    echo "=== 1. API Rate Limit Errors (429) ==="
    count_429=$(grep -c "429\|Rate Limit\|Resource has been exhausted\|Too many requests" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Total Count: $count_429"
    echo ""
    echo "Recent occurrences:"
    grep -i "429\|Rate Limit\|Resource has been exhausted\|Too many requests" "$LOG_FILE" 2>/dev/null | tail -10
    echo ""

    # 2. Server Overload Errors (503)
    echo "=== 2. Server Overload Errors (503) ==="
    count_503=$(grep -c "503\|Overloaded\|Service Unavailable" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Total Count: $count_503"
    echo ""
    echo "Recent occurrences:"
    grep -i "503\|Overloaded\|Service Unavailable" "$LOG_FILE" 2>/dev/null | tail -10
    echo ""

    # 3. Model Fallback Events
    echo "=== 3. Model Fallback Events ==="
    echo "Models attempted:"
    grep -o "Attempting AI generation with model: [^\"]*" "$LOG_FILE" 2>/dev/null | sort | uniq -c | sort -rn
    echo ""
    echo "Model failures:"
    grep -i "\[WARN\] Model.*failed" "$LOG_FILE" 2>/dev/null | tail -10
    echo ""

    # 4. All Models Failed Events
    echo "=== 4. Critical: All Models Failed ==="
    count_all_failed=$(grep -c "ALL FALLBACK MODELS FAILED" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Total Count: $count_all_failed"
    echo ""
    if [ "$count_all_failed" -gt 0 ]; then
        echo "Recent occurrences:"
        grep "ALL FALLBACK MODELS FAILED" "$LOG_FILE" 2>/dev/null | tail -5
    fi
    echo ""

    # 5. Cache Hit Analysis
    echo "=== 5. Cache Performance ==="
    cache_hits=$(grep -c "cache" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Cache-related events: $cache_hits"
    echo ""

    # 6. Request Types Summary
    echo "=== 6. Request Patterns ==="
    echo "Endpoint hits (estimated):"
    echo "  /analyze-food: $(grep -c "analyze_food\|analyze-food" "$LOG_FILE" 2>/dev/null || echo 0)"
    echo "  /chat: $(grep -c "\"chat\"\|/chat" "$LOG_FILE" 2>/dev/null || echo 0)"
    echo "  /users: $(grep -c "\"/users\"\|create_user" "$LOG_FILE" 2>/dev/null || echo 0)"
    echo ""

    # 7. DuckDuckGo Search Status
    echo "=== 7. DuckDuckGo Search Status ==="
    ddg_success=$(grep -c "Performing DuckDuckGo search" "$LOG_FILE" 2>/dev/null || echo 0)
    ddg_failed=$(grep -c "DuckDuckGo Search failed" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Search attempts: $ddg_success"
    echo "Search failures: $ddg_failed"
    echo ""

    # 8. Google Search Grounding
    echo "=== 8. Google Search Grounding ==="
    google_search=$(grep -c "Google Search used" "$LOG_FILE" 2>/dev/null || echo 0)
    echo "Google Search used: $google_search times"
    echo ""

    # 9. Error Summary
    echo "=== 9. Error Summary ==="
    echo "  429 (Rate Limit): $count_429"
    echo "  503 (Overload): $count_503"
    echo "  All Models Failed: $count_all_failed"
    echo ""
    
    # Calculate health score
    total_errors=$((count_429 + count_503 + count_all_failed))
    if [ "$total_errors" -eq 0 ]; then
        health="HEALTHY"
    elif [ "$total_errors" -lt 10 ]; then
        health="WARNING"
    else
        health="CRITICAL"
    fi
    echo "=== System Health: $health ==="
    echo ""

    # 10. Recommendations
    echo "=== 10. Recommendations ==="
    if [ "$count_429" -gt 5 ]; then
        echo "  - HIGH 429 errors: Consider reducing API call frequency"
        echo "  - Increase cache TTL in main.py (CACHE_TTL)"
        echo "  - Add more models to FALLBACK_CHAIN"
    fi
    if [ "$count_503" -gt 5 ]; then
        echo "  - HIGH 503 errors: API servers are overloaded"
        echo "  - Increase retry delay in gemini_generate_with_backoff()"
        echo "  - Consider using off-peak hours"
    fi
    if [ "$count_all_failed" -gt 0 ]; then
        echo "  - CRITICAL: All models failed $count_all_failed times"
        echo "  - Check API key validity"
        echo "  - Check network connectivity"
        echo "  - Consider adding more fallback models"
    fi
    if [ "$total_errors" -eq 0 ]; then
        echo "  - No issues detected. System running smoothly."
    fi
    echo ""
    echo "=============================================="
    echo "   End of Report"
    echo "=============================================="

} | tee "$REPORT_FILE"

echo ""
echo "[INFO] Report saved to: $REPORT_FILE"
echo "[DONE] Analysis completed at $(date)"
