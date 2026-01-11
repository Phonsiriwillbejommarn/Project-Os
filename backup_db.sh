#!/bin/bash

# =============================================
#   NutriFriend AI - Database Backup Script
#   - Backup database only (no data deletion)
# =============================================

# Define paths
PROJECT_DIR="/home/os/Project-Os3/Project-Os"
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
# Backup Database
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

echo ""
echo "[DONE] Backup finished at $(date)"
