#!/bin/bash

# =============================================
#   NutriFriend AI - Database Backup Script
#   - Backup database (keep forever)
#   - Delete old user data (older than 7 days)
# =============================================

# Define paths
PROJECT_DIR="/home/pi/nutrifriend-ai-2"
DB_FILE="$PROJECT_DIR/backend/nutrifriend.db"
BACKUP_DIR="$PROJECT_DIR/backups"

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Define backup filename with date
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nutrifriend_backup_$DATE.db"

# Check if database file exists
if [ ! -f "$DB_FILE" ]; then
    echo "[ERROR] Database file not found at $DB_FILE"
    exit 1
fi

# ============================================
# STEP 1: Backup Database (Keep Forever)
# ============================================
echo "[INFO] Starting database backup..."
echo "[INFO] Source: $DB_FILE"
echo "[INFO] Destination: $BACKUP_FILE"

cp "$DB_FILE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Backup completed successfully!"
    echo "[INFO] File: $BACKUP_FILE"
    echo "[INFO] Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
else
    echo "[ERROR] Backup failed!"
    exit 1
fi

# ============================================
# STEP 2: Delete Old User Data (7 days old)
# ============================================
echo ""
echo "[INFO] Cleaning old user data from database..."

# Calculate date 7 days ago (YYYY-MM-DD format)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CUTOFF_DATE=$(date -v-7d +%Y-%m-%d)
else
    # Linux (Raspberry Pi)
    CUTOFF_DATE=$(date -d "7 days ago" +%Y-%m-%d)
fi

echo "[INFO] Deleting data older than: $CUTOFF_DATE"

# Delete old food_items
DELETED_FOODS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM food_items WHERE date < '$CUTOFF_DATE';")
sqlite3 "$DB_FILE" "DELETE FROM food_items WHERE date < '$CUTOFF_DATE';"
echo "[INFO] Deleted $DELETED_FOODS old food items"

# Delete old messages
DELETED_MESSAGES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM messages WHERE date < '$CUTOFF_DATE';")
sqlite3 "$DB_FILE" "DELETE FROM messages WHERE date < '$CUTOFF_DATE';"
echo "[INFO] Deleted $DELETED_MESSAGES old messages"

# Vacuum database to reclaim space
echo "[INFO] Optimizing database (VACUUM)..."
sqlite3 "$DB_FILE" "VACUUM;"

# Show database size after cleanup
echo "[INFO] Database size after cleanup: $(ls -lh "$DB_FILE" | awk '{print $5}')"

# ============================================
# STEP 3: Show Summary
# ============================================
echo ""
echo "=============================================="
echo "   Backup & Cleanup Summary"
echo "=============================================="
echo "  Backup file: $BACKUP_FILE"
echo "  Data deleted before: $CUTOFF_DATE"
echo "  Food items deleted: $DELETED_FOODS"
echo "  Messages deleted: $DELETED_MESSAGES"
echo "=============================================="
echo ""
echo "[DONE] Process finished at $(date)"
