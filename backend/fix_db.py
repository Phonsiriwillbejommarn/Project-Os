import sqlite3
import datetime
import os

db_path = "nutrifriend.db"

if not os.path.exists(db_path):
    print(f"Database file {db_path} not found.")
    exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Attempting to add 'date' column to 'messages' table...")
    cursor.execute("ALTER TABLE messages ADD COLUMN date TEXT")
    print("Column 'date' added successfully.")
    
    # Update existing rows
    print("Updating existing rows...")
    cursor.execute("SELECT id, timestamp FROM messages")
    rows = cursor.fetchall()
    for row in rows:
        msg_id = row[0]
        ts = row[1]
        try:
            # Assuming ts is milliseconds
            dt = datetime.datetime.fromtimestamp(ts / 1000.0)
            date_str = dt.strftime('%Y-%m-%d')
            cursor.execute("UPDATE messages SET date = ? WHERE id = ?", (date_str, msg_id))
        except Exception as e:
            print(f"Skipping row {msg_id}: {e}")
            
    conn.commit()
    print("Migration complete.")

except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'date' already exists. No action needed.")
    else:
        print(f"OperationalError: {e}")
except Exception as e:
    print(f"An error occurred: {e}")

conn.close()
