#!/bin/bash

# =============================================
#   NutriFriend AI - Weekly Food Report
#   Generate food intake summary for all users
# =============================================

# Define paths
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
REPORT_DIR="$PROJECT_DIR/reports"

# Create report directory
mkdir -p "$REPORT_DIR"

# Date for report
DATE=$(date +%Y%m%d)
REPORT_FILE="$REPORT_DIR/weekly_report_$DATE.txt"

# Calculate date range (last 7 days)
if [[ "$OSTYPE" == "darwin"* ]]; then
    START_DATE=$(date -v-7d +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)
else
    START_DATE=$(date -d "7 days ago" +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)
fi

# Check database
if [ ! -f "$DB_FILE" ]; then
    echo "[ERROR] Database not found: $DB_FILE"
    exit 1
fi

echo "[INFO] Generating Weekly Food Report..."
echo "[INFO] Period: $START_DATE to $END_DATE"

# Generate report
{
    echo "=============================================="
    echo "   NutriFriend AI - Weekly Food Report"
    echo "   Period: $START_DATE to $END_DATE"
    echo "   Generated: $(date)"
    echo "=============================================="
    echo ""

    # Get all users
    USERS=$(sqlite3 "$DB_FILE" "SELECT id, name, target_calories FROM user_profiles;")

    if [ -z "$USERS" ]; then
        echo "[INFO] No users found in database."
    else
        echo "$USERS" | while IFS='|' read -r USER_ID USER_NAME TARGET_CAL; do
            echo "----------------------------------------------"
            echo "User: $USER_NAME (ID: $USER_ID)"
            echo "Target Calories: ${TARGET_CAL:-N/A} kcal/day"
            echo "----------------------------------------------"
            echo ""

            # Get food stats for this user in last 7 days
            STATS=$(sqlite3 "$DB_FILE" "
                SELECT 
                    date,
                    COUNT(*) as meals,
                    ROUND(SUM(calories), 0) as total_cal,
                    ROUND(SUM(protein), 1) as total_protein,
                    ROUND(SUM(carbs), 1) as total_carbs,
                    ROUND(SUM(fat), 1) as total_fat
                FROM food_items 
                WHERE user_id = $USER_ID 
                AND date >= '$START_DATE' 
                AND date <= '$END_DATE'
                GROUP BY date
                ORDER BY date;
            ")

            if [ -z "$STATS" ]; then
                echo "  No food records found for this period."
                echo ""
            else
                echo "  Date       | Meals | Calories | Protein | Carbs  | Fat"
                echo "  -----------|-------|----------|---------|--------|------"
                
                TOTAL_CAL=0
                TOTAL_PROTEIN=0
                TOTAL_CARBS=0
                TOTAL_FAT=0
                DAYS=0

                echo "$STATS" | while IFS='|' read -r F_DATE MEALS CAL PROTEIN CARBS FAT; do
                    printf "  %-10s | %5s | %8s | %7s | %6s | %s\n" "$F_DATE" "$MEALS" "${CAL:-0}" "${PROTEIN:-0}" "${CARBS:-0}" "${FAT:-0}"
                done

                echo ""

                # Weekly totals
                WEEKLY=$(sqlite3 "$DB_FILE" "
                    SELECT 
                        COUNT(DISTINCT date) as days,
                        ROUND(SUM(calories), 0) as total_cal,
                        ROUND(AVG(calories), 0) as avg_cal,
                        ROUND(SUM(protein), 1) as total_protein,
                        ROUND(SUM(carbs), 1) as total_carbs,
                        ROUND(SUM(fat), 1) as total_fat
                    FROM food_items 
                    WHERE user_id = $USER_ID 
                    AND date >= '$START_DATE' 
                    AND date <= '$END_DATE';
                ")

                echo "$WEEKLY" | IFS='|' read -r DAYS TOTAL_CAL AVG_CAL TOTAL_PROTEIN TOTAL_CARBS TOTAL_FAT

                echo "  Weekly Summary:"
                echo "  - Days with records: $DAYS"
                echo "  - Total Calories: $TOTAL_CAL kcal"
                echo "  - Average per day: $AVG_CAL kcal"
                echo "  - Total Protein: $TOTAL_PROTEIN g"
                echo "  - Total Carbs: $TOTAL_CARBS g"
                echo "  - Total Fat: $TOTAL_FAT g"

                # Compare with target
                if [ -n "$TARGET_CAL" ] && [ "$TARGET_CAL" != "NULL" ]; then
                    TARGET_WEEKLY=$((TARGET_CAL * 7))
                    if [ "$TOTAL_CAL" -lt "$TARGET_WEEKLY" ]; then
                        DIFF=$((TARGET_WEEKLY - TOTAL_CAL))
                        echo "  - Status: Under target by $DIFF kcal this week"
                    else
                        DIFF=$((TOTAL_CAL - TARGET_WEEKLY))
                        echo "  - Status: Over target by $DIFF kcal this week"
                    fi
                fi
                echo ""
            fi
        done
    fi

    echo ""
    echo "=============================================="
    echo "   End of Report"
    echo "=============================================="

} | tee "$REPORT_FILE"

echo ""
echo "[INFO] Report saved to: $REPORT_FILE"
echo "[DONE] Report generated at $(date)"
